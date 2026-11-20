from app.api import snapshot
from app.errors import BusinessError
from app.manifest import canonical, manifest
from app.modules.m7_archive.signoff import approval
from app.quality import token
from app.catalog import source_data


def prepare(ledger, source, operator):
    if not source:
        raise BusinessError("CHOOSE_SOURCE", "请选择数据来源")
    try:
        operator = token(operator)
        if len(operator) > 32:
            raise ValueError
    except ValueError as error:
        raise BusinessError("OPERATOR_REQUIRED", "请输入 1 至 32 字的签核人") from error
    data = source_data(ledger, source)
    result = snapshot(canonical(data))
    check = approval(result)
    proof = manifest(source, data, operator, result, check)
    return {
        "id": "run-" + proof["digest"],
        "manifest": proof,
        "approval": check,
        "result": result,
        "input": data,
    }


def archive(ledger, source, operator):
    record = prepare(ledger, source, operator)
    return dict(record, reused=ledger.put_run(record))


def rerun(ledger, run_id):
    record = ledger.run(run_id)
    manifest_data = record["manifest"]
    fresh = prepare(ledger, manifest_data["source"], manifest_data["operator"])
    if fresh != record:
        raise BusinessError(
            "MANIFEST_CHANGED", "来源或规则版本发生变化，请另行归档", 409
        )
    return dict(record, reused=True)
