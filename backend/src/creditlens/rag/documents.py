from __future__ import annotations

from dataclasses import dataclass

import yaml

from creditlens.config import ROOT

KB_DIR = ROOT / "knowledge_base"


@dataclass
class KnowledgeDoc:
    doc_id: str
    title: str
    section: str
    version: str
    segment: str
    effective_from: str
    text: str
    source_path: str
    citation: str


def load_documents() -> list[KnowledgeDoc]:
    docs: list[KnowledgeDoc] = []
    for path in sorted(KB_DIR.rglob("*.md")):
        raw = path.read_text(encoding="utf-8")
        if raw.startswith("---"):
            _, fm, body = raw.split("---", 2)
            meta = yaml.safe_load(fm) or {}
        else:
            meta, body = {}, raw
        rel = path.relative_to(KB_DIR).as_posix()
        section = str(meta.get("section", "n/a"))
        title = str(meta.get("title", path.stem))
        docs.append(
            KnowledgeDoc(
                doc_id=str(meta.get("document", path.stem)),
                title=title,
                section=section,
                version=str(meta.get("version", "1.0")),
                segment=str(meta.get("segment", "all")),
                effective_from=str(meta.get("effective_from", "")),
                text=body.strip(),
                source_path=rel,
                citation=f"{title} → {section}",
            )
        )
    return docs
