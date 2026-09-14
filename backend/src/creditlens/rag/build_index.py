from creditlens.rag.retrieve import _index, knowledge_stats


def main() -> None:
    _index.cache_clear()
    _index()
    print(knowledge_stats())


if __name__ == "__main__":
    main()
