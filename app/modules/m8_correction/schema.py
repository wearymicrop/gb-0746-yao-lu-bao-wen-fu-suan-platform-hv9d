"""迟到更正记录的校验、应用与差异核对。

更正只允许追加或替换校准行；炉单和读数按摘要锁定，必须与原凭证逐字节
一致。正式结论由原炉单加全部生效更正重新计算，绝不在旧结论上累加。
"""

from copy import deepcopy

from app.config import RULE_VERSION
from app.errors import BusinessError
from app.manifest import canonical, digest
from app.quality import instant, integer, token, utc

MAX_CORRECTIONS = 32

REPLACE_KEYS = (
    "replaces_row",
    "supersedes_row",
    "correction_of_row",
    "original_row",
    "calibration_row",
    "replaces",
)
RECEIVED_KEYS = ("received_at", "arrived_at", "late_at")
REASON_KEYS = ("reason", "note", "cause")
DOCUMENT_KEYS = ("document", "evidence", "source_doc", "doc")


def _first(item, keys):
    for key in keys:
        if key in item and item[key] not in (None, ""):
            return item[key]
    return None


def _option(item, keys):
    value = _first(item, keys)
    if value in (None, ""):
        return None
    return token(value)


def parse_corrections(raw, original, plan):
    """校验迟到更正记录，只留下可重算的校准证据。"""
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_CORRECTIONS:
        raise BusinessError(
            "BAD_CORRECTION", f"更正记录须为 1 至 {MAX_CORRECTIONS} 项"
        )
    calibrations = original.get("calibrations")
    if not isinstance(calibrations, list):
        raise BusinessError("BAD_CORRECTION", "原炉单缺少校准段，无法更正")
    zones = set(plan["zones"])
    entries = []
    for index, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise BusinessError("BAD_CORRECTION", f"第 {index} 项更正须为对象")
        try:
            zone = token(item["zone"])
            start, end = instant(item["start"]), instant(item["end"])
            offset = integer(item["offset_mc"], -100000, 100000)
            if zone not in zones or start >= end:
                raise ValueError
            replaces = None
            target = _first(item, REPLACE_KEYS)
            if target is not None:
                replaces = integer(target, 1, len(calibrations))
                row = calibrations[replaces - 1]
                # 原行本身无效时允许整行补正；能读出热区时必须对得上。
                if isinstance(row, dict) and row.get("zone") not in (None, ""):
                    if token(row["zone"]) != zone:
                        raise ValueError
            received = _first(item, RECEIVED_KEYS)
            if received is not None:
                received = instant(received)
            reason = _option(item, REASON_KEYS)
            document = _option(item, DOCUMENT_KEYS)
        except (KeyError, TypeError, ValueError):
            raise BusinessError("BAD_CORRECTION", f"第 {index} 项更正无效") from None
        entries.append(
            {
                "index": index,
                "zone": zone,
                "start": start,
                "end": end,
                "offset_mc": offset,
                "replaces_row": replaces,
                "received_at": received,
                "reason": reason,
                "document": document,
            }
        )
    targets = [entry["replaces_row"] for entry in entries if entry["replaces_row"]]
    if len(targets) != len(set(targets)):
        raise BusinessError("CORRECTION_CONFLICT", "同一次更正不能重复替换同一校准行")
    return entries


def core(entry):
    """幂等身份只采信可重算字段；换依据重复投递不另生成结论。"""
    return {
        "zone": entry["zone"],
        "start": entry["start"],
        "end": entry["end"],
        "offset_mc": entry["offset_mc"],
        "replaces_row": entry["replaces_row"],
    }


def _key(entry):
    if entry["replaces_row"] is not None:
        return ("row", entry["replaces_row"])
    return ("append", entry["zone"], entry["start"], entry["end"])


def merge_applied(parent, entries):
    """替换按原行归并，追加窗口按热区与起止归并；后到的更正覆盖先到的。"""
    merged = {}
    for entry in list(parent or []) + list(entries):
        merged[_key(entry)] = entry
    return sorted(
        merged.values(),
        key=lambda entry: (
            entry["replaces_row"] is None,
            entry["replaces_row"] or 0,
            entry["zone"],
            entry["start"],
            entry["end"],
            entry["offset_mc"],
        ),
    )


def apply_corrections(original, applied):
    """沿用原炉单与同批读数，只改受影响的校准行。"""
    data = deepcopy(original)
    calibrations = data.get("calibrations")
    if not isinstance(calibrations, list):
        raise BusinessError("BAD_CORRECTION", "原炉单缺少校准段，无法更正")
    for entry in applied:
        record = {
            "zone": entry["zone"],
            "start": utc(entry["start"]),
            "end": utc(entry["end"]),
            "offset_mc": entry["offset_mc"],
        }
        if entry["replaces_row"] is not None:
            calibrations[entry["replaces_row"] - 1] = record
        else:
            calibrations.append(record)
    if canonical(data["plan"]) != canonical(original["plan"]):
        raise BusinessError("CORRECTION_SCOPE", "更正不得改动原炉单", 409)
    if canonical(data["readings"]) != canonical(original["readings"]):
        raise BusinessError("CORRECTION_SCOPE", "更正不得改动同批读数", 409)
    return data


def identity(original, applied):
    """正式结论的身份：原输入摘要、规则版本与生效更正集合的纯函数。

    同一炉单、同一组生效更正无论从哪张签核凭证送入，都落到同一条结论。
    """
    return {
        "base_input_sha256": digest(original),
        "rules": RULE_VERSION,
        "applied": [core(entry) for entry in applied],
    }


def evidence(entries):
    return [
        dict(
            entry,
            received_at=utc(entry["received_at"])
            if entry["received_at"] is not None
            else None,
        )
        for entry in entries
    ]


def seal(record):
    body = dict(record)
    body.pop("digest", None)
    body.pop("reused", None)
    body["digest"] = digest(body)
    return body


def consistent_correction(record):
    try:
        stored = record["digest"]
        body = dict(record)
        body.pop("digest", None)
        body.pop("reused", None)
        body.pop("repeated", None)
        prefix = "corr-" if record["status"] == "FORMAL" else "pend-"
        return (
            stored == digest(body)
            and record["id"] == prefix + record["identity_sha256"]
            and record["identity_sha256"] == digest(record["identity"])
            and record["base_input_sha256"] == record["identity"]["base_input_sha256"]
            and record["rules"] == record["identity"]["rules"]
            and record["result_sha256"] == digest(record["result"])
        )
    except (KeyError, TypeError, ValueError):
        return False


def _window(row):
    return {
        "start": row["start"],
        "end": row["end"],
        "value_mc": row.get("value_mc"),
        "code": row.get("code"),
        "reading_rows": row.get("reading_rows") or [],
        "calibration_row": row.get("calibration_row"),
    }


def _keyed(before, after, key, view):
    """按起点对齐前后两版，避免中间插入导致整体错位误报。"""
    old = {item[key]: view(item) for item in before}
    new = {item[key]: view(item) for item in after}
    changes = []
    for edge in sorted(set(old) | set(new)):
        if old.get(edge) != new.get(edge):
            changes.append({"before": old.get(edge), "after": new.get(edge)})
    return changes


def _compare_windows(before, after):
    return _keyed(before, after, "start", _window)


def _compare_sections(before, after):
    fields = ("start", "end", "state", "seconds", "version", "codes")

    def view(item):
        return dict({field: item[field] for field in fields}, time=item["time"])

    return _keyed(before, after, "start", view)


def _compare_gaps(before, after):
    def view(gap):
        return {
            "start": gap["start"],
            "end": gap["end"],
            "time": gap.get("time"),
            "seconds": gap["seconds"],
            "codes": gap["codes"],
            "zones": gap["zones"],
            "decision": gap["decision"],
            "next_proven": gap["next_proven"],
        }

    return _keyed(before, after, "start", view)


def _compare_soak(before, after):
    keys = {
        "longest_s": (before["soak"]["longest_s"], after["soak"]["longest_s"]),
        "goal_s": (before["soak"]["goal_s"], after["soak"]["goal_s"]),
        "goal_met": (before["soak"]["goal_met"], after["soak"]["goal_met"]),
    }
    streaks_before = [
        {key: item[key] for key in ("start", "end", "seconds", "version")}
        for item in before["soak"]["streaks"]
    ]
    streaks_after = [
        {key: item[key] for key in ("start", "end", "seconds", "version")}
        for item in after["soak"]["streaks"]
    ]
    return {
        "sections": _compare_sections(
            before["soak"]["sections"], after["soak"]["sections"]
        ),
        "streaks": {
            "before": streaks_before,
            "after": streaks_after,
            "changed": streaks_before != streaks_after,
        },
        "totals": {
            field: {"before": pair[0], "after": pair[1], "changed": pair[0] != pair[1]}
            for field, pair in keys.items()
        },
    }


def _summary(result, signoff):
    balance = result["reconcile"]
    return {
        "proven_s": balance["proven_s"],
        "cold_s": balance["cold_s"],
        "unproven_s": balance["unproven_s"],
        "longest_s": balance["longest_s"],
        "goal_met": balance["goal_met"],
        "status": balance["status"],
        "gap_count": result["gaps"]["gap_count"],
        "approval": signoff["status"] if signoff else None,
    }


def _offsets(result):
    offsets = {}
    for items in (result.get("calibration", {}).get("register") or {}).values():
        for item in items:
            offsets[item["row"]] = item["offset_mc"]
    return offsets


def compare(before, after, signoff_before, signoff_after, entries):
    before_cal = _offsets(before)
    calibration = {
        "replaced": [
            {
                "row": entry["replaces_row"],
                "zone": entry["zone"],
                "before_mc": before_cal.get(entry["replaces_row"]),
                "after_mc": entry["offset_mc"],
            }
            for entry in entries
            if entry["replaces_row"] is not None
        ],
        "appended": [
            {
                "zone": entry["zone"],
                "start": entry["start"],
                "end": entry["end"],
                "offset_mc": entry["offset_mc"],
            }
            for entry in entries
            if entry["replaces_row"] is None
        ],
    }
    zones = {}
    before_zones = before["alignment"]["zones"]
    after_zones = after["alignment"]["zones"]
    for zone in sorted(set(before_zones) | set(after_zones)):
        changes = _compare_windows(before_zones.get(zone, []), after_zones.get(zone, []))
        if changes:
            zones[zone] = changes
    return {
        "before": _summary(before, signoff_before),
        "after": _summary(after, signoff_after),
        "calibration": calibration,
        "alignment": zones,
        "soak": _compare_soak(before, after),
        "gaps": _compare_gaps(before["gaps"]["gaps"], after["gaps"]["gaps"]),
        "reconcile": {
            field: {
                "before": before["reconcile"].get(field),
                "after": after["reconcile"].get(field),
            }
            for field in (
                "status",
                "planned_s",
                "proven_s",
                "cold_s",
                "unproven_s",
                "difference_s",
                "reading_difference",
                "longest_s",
                "goal_met",
                "continuous_partition",
            )
        },
    }
