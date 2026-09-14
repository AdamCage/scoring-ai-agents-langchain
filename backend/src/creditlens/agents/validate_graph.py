from creditlens.agents.graph import get_graph


def main() -> None:
    graph = get_graph()
    print("nodes", list(graph.get_graph().nodes))
    print("ok")


if __name__ == "__main__":
    main()
