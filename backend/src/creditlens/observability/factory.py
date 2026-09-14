from creditlens.config import get_settings
from creditlens.observability.local import LocalObservability

_local = LocalObservability()


def get_observability() -> LocalObservability:
    mode = get_settings().observability
    if mode not in {"local", "both"}:
        return _local
    return _local
