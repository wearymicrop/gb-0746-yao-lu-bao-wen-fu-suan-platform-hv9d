import hashlib
import json

from app.config import PROJECT, RULE_VERSION


def canonical(data):
    return json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def digest(data):
    return hashlib.sha256(canonical(data).encode("utf-8")).hexdigest()


def manifest(source, input_data, operator, result, approval):
    record = {
        "project": PROJECT,
        "source": source,
        "input_sha256": digest(input_data),
        "rules": RULE_VERSION,
        "operator": operator,
        "result_sha256": digest(result),
        "approval_sha256": digest(approval),
    }
    return dict(record, digest=digest(record))
