from creditlens.observability.base import Observability


class LangSmithObservability:
    name = "langsmith"

    def __init__(self) -> None:
        raise RuntimeError(
            "LangSmith adapter is intentionally NotConfigured. "
            "CreditLens runs local observability only."
        )


def available() -> bool:
    return False


# Protocol leftover so imports stay stable.
_: type[Observability] | None = None
