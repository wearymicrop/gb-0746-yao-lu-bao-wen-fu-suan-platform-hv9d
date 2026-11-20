"""迟到更正记录：追加式新结论，原凭证保持只读。

- 沿用原炉单与同批读数，只在校准段替换或追加窗口，整链重算。
- 结论身份由「原输入摘要 + 规则版本 + 生效更正集合」决定，
  重复投递命中同一身份，不会生成第二条结论，也不会叠加计时。
- 未对平的结果只登记为待核，不成为生效结论，也不签发凭证。
"""

from app.api import snapshot
from app.errors import BusinessError
from app.manifest import canonical, digest
from app.modules.m7_archive.bundle import consistent
from app.modules.m7_archive.signoff import approval
from app.modules.m8_correction.schema import (
    apply_corrections,
    compare,
    core,
    evidence,
    identity,
    merge_applied,
    parse_corrections,
    seal,
)
from app.quality import token


def _recorder(value):
    try:
        value = token(value)
        if len(value) > 32:
            raise ValueError
        return value
    except ValueError as error:
        raise BusinessError("RECORDER_REQUIRED", "请输入 1 至 32 字的登记人") from error


def _base(ledger, base_run):
    if not base_run:
        raise BusinessError("CHOOSE_RUN", "请选择已签核的原始凭证")
    base = ledger.run(base_run)
    if not consistent(base):
        raise BusinessError("BUNDLE_MISMATCH", "原始凭证摘要不一致", 409)
    return base


def _formal(chain):
    """生效结论只认已对平且签核的 FORMAL 记录。"""
    for record in reversed(chain):
        if record["status"] == "FORMAL":
            return record
    return None


def _evidence_marks(entries):
    return {
        (entry["zone"], entry["start"], entry["end"], entry["offset_mc"],
         entry["replaces_row"]): (entry["document"], entry["reason"])
        for entry in entries
    }


def _repeat(record, entries):
    """重复投递的返回：结论沿用，但换过依据要明示，不静默吞掉。"""
    stored = _evidence_marks(record["applied"])
    changed = [
        entry["index"]
        for entry in entries
        if stored.get(
            (
                entry["zone"],
                entry["start"],
                entry["end"],
                entry["offset_mc"],
                entry["replaces_row"],
            )
        )
        != (entry["document"], entry["reason"])
    ]
    return dict(
        record,
        reused=True,
        repeated=True,
        evidence_changed=bool(changed),
        evidence_note=(
            f"更正内容一致，沿用原结论；第 {'、'.join(map(str, changed))} 条依据与已存记录不同，未另立结论"
            if changed
            else "更正内容一致，沿用原结论"
        ),
    )


def submit(ledger, base_run, corrections, recorder):
    """提交一份更正。重复投递返回同一结论，不叠加时长、不重写原凭证。"""
    recorder = _recorder(recorder)
    base = _base(ledger, base_run)
    original = base["input"]
    plan = base["result"]["intake"]["plan"]
    entries = parse_corrections(corrections, original, plan)
    base_sha = digest(original)

    with ledger.transaction() as conn:
        chain = ledger.chain_in(conn, base_sha)
        latest = chain[-1] if chain else None
        formal = _formal(chain)

        # 更正按到达顺序叠加；未对平的尝试也留在链上，后到的更正可以补正它。
        parent = latest["applied"] if latest else []
        applied = merge_applied(parent, entries)

        # 生效字段（热区、窗口、偏移、替换行）没变即视为同一份更正；
        # 只有依据文号或到达时间变化时沿用原结论并在响应中标记。
        unchanged = latest is not None and [core(entry) for entry in applied] == [
            core(entry) for entry in parent
        ]
        if unchanged and latest["status"] == "FORMAL":
            # 同一份更正重复送入或中断后重试：已有正式结论，直接返回。
            return _repeat(latest, entries)

        anchor = formal if formal else base
        before = anchor["result"]
        before_signoff = anchor["approval"]
        supersedes = formal["id"] if formal else base["id"]
        supersedes_kind = "correction" if formal else "run"

        revised = apply_corrections(original, applied)
        result = snapshot(canonical(revised))
        balance = result["reconcile"]
        try:
            # 是否可发布由签核口径裁决：未对平就不签发。
            check = approval(result)
            status = "FORMAL"
            pending = None
        except BusinessError as error:
            if error.code != "UNBALANCED":
                raise
            check = None
            status = "PENDING"
            pending = {
                "code": "UNBALANCED",
                "message": "炉批尚未对平，暂不构成正式结论",
                "difference_s": balance.get("difference_s"),
                "reading_difference": balance.get("reading_difference"),
                "continuous_partition": balance.get("continuous_partition"),
            }

        proof = identity(original, applied)
        proof_sha256 = digest(proof)
        record_id = ("corr-" if status == "FORMAL" else "pend-") + proof_sha256
        body = {
            "base_run": base["id"],
            "base_source": base["manifest"]["source"],
            "base_input_sha256": base_sha,
            "base_approval": base["approval"],
            "base_result_sha256": base["manifest"]["result_sha256"],
            "supersedes": supersedes,
            "supersedes_kind": supersedes_kind,
            "previous_attempt": (
                latest["id"] if latest and latest["id"] != record_id else None
            ),
            "recorder": recorder,
            "corrections": evidence(entries),
            "applied": applied,
            "identity": proof,
            "identity_sha256": proof_sha256,
            "rules": proof["rules"],
            "plan_sha256": digest(original["plan"]),
            "readings_sha256": digest(original["readings"]),
            "input_sha256": digest(revised),
            "result_sha256": digest(result),
            "result": result,
            "approval": check,
            "status": status,
            "pending": pending,
            "diff": compare(before, result, before_signoff, check, entries),
        }
        # 正式结论与待核尝试分属两个身份空间：待核升级为正式不会撞号。
        body["id"] = record_id
        record = seal(body)

        if not ledger.insert_in(conn, record):
            stored = ledger.correction_in(conn, record["id"])
            if status == "PENDING" or unchanged:
                return _repeat(stored, entries)
            return dict(stored, reused=True)

    return dict(record, reused=False)


def inspect(ledger, base_run):
    """查看更正链：原凭证、每次落库结论、当前生效结论。"""
    base = _base(ledger, base_run)
    chain = ledger.correction_chain(digest(base["input"]))
    current = _formal(chain)
    return {
        "base": {
            "id": base["id"],
            "approval": base["approval"],
            "status": base["result"]["reconcile"]["status"],
            "result_sha256": base["manifest"]["result_sha256"],
        },
        "corrections": [
            {
                "id": record["id"],
                "status": record["status"],
                "supersedes": record["supersedes"],
                "approval": record["approval"],
                "pending": record["pending"],
                "recorder": record["recorder"],
                "received_at": [
                    entry["received_at"]
                    for entry in record["corrections"]
                    if entry["received_at"]
                ],
                "correction_rows": [
                    entry["replaces_row"]
                    for entry in record["corrections"]
                    if entry["replaces_row"] is not None
                ],
                "diff": record["diff"]["before"],
                "result": {
                    "proven_s": record["result"]["reconcile"]["proven_s"],
                    "unproven_s": record["result"]["reconcile"]["unproven_s"],
                    "longest_s": record["result"]["reconcile"]["longest_s"],
                    "goal_met": record["result"]["reconcile"]["goal_met"],
                },
                "digest": record["digest"],
            }
            for record in chain
        ],
        "current": (current or base)["id"],
        "current_kind": "correction" if current else "run",
    }


def detail(ledger, correction_id):
    return ledger.correction(correction_id)
