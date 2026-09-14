from creditlens.agents.graph import get_graph
from creditlens.config import ROOT


def main() -> None:
    graph = get_graph()
    mermaid = graph.get_graph().draw_mermaid()
    out = ROOT / "docs" / "architecture" / "langgraph-exported.mmd"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(mermaid, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
