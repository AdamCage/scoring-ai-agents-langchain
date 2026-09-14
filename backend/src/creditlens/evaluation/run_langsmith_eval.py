from __future__ import annotations

from creditlens.observability.langsmith import available, configure_env


def main() -> None:
    if not available():
        print("LangSmith adapter ready_no_key — set LANGSMITH_API_KEY to upload experiments")
        return
    configure_env()
    try:
        from langsmith import Client

        client = Client()
        print("langsmith project ready", client.info())
    except Exception as exc:
        print("langsmith client error", exc)


if __name__ == "__main__":
    main()
