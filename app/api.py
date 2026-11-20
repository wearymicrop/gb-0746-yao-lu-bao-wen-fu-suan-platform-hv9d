from functools import lru_cache
import json

from app.catalog import source_data
from app.manifest import canonical
from app.pipeline import calculate


@lru_cache(maxsize=4)
def snapshot(serialized):
    return calculate(json.loads(serialized))


def preview(request, source):
    return snapshot(canonical(source_data(request.app.state.ledger, source)))
