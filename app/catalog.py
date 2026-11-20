import json

from app.config import ROOT, SAMPLES


def source_data(ledger, source):
    if source in SAMPLES:
        return json.loads(
            (ROOT / "sample_data" / f"{source}.json").read_text(encoding="utf-8-sig")
        )
    return ledger.source(source)
