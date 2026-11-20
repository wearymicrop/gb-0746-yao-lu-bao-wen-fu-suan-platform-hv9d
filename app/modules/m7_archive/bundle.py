from app.manifest import digest


def consistent(record):
    try:
        proof = dict(record["manifest"])
        checksum = proof.pop("digest")
        return (
            record["id"] == "run-" + checksum
            and checksum == digest(proof)
            and proof["input_sha256"] == digest(record["input"])
            and proof["result_sha256"] == digest(record["result"])
            and proof["approval_sha256"] == digest(record["approval"])
        )
    except (KeyError, TypeError, ValueError):
        return False
