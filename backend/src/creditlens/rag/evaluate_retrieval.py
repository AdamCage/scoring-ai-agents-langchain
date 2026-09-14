from __future__ import annotations

from creditlens.presets import presets
from creditlens.rag.retrieve import retrieve_policy


def main() -> None:
    hits = 0
    for preset in presets():
        docs, debug = retrieve_policy(preset.application)
        ok = any("4.2" in doc.section or "7.1" in doc.section or "8.1" in doc.section for doc in docs)
        hits += int(ok)
        print(preset.id, [doc.citation for doc in docs], "hit" if ok else "miss", debug.reranked_ids)
    print(f"preset_hits={hits}/{len(presets())}")


if __name__ == "__main__":
    main()
