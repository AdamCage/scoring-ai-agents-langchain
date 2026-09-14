class LangfuseObservability:
    name = "langfuse"

    def __init__(self) -> None:
        raise RuntimeError(
            "Langfuse adapter is intentionally NotConfigured. "
            "CreditLens runs local observability only."
        )


def available() -> bool:
    return False
