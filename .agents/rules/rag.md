# RAG

- Knowledge base documents use YAML frontmatter: document, version, effective_from, segment, section.
- Retrieval is hybrid: metadata filter → vector + BM25 → RRF → local rerank → top 4.
- Log every stage into the local tracer so Architecture Explorer can bind spans to the mermaid nodes.
- Offline fallback embeddings must stay deterministic for tests.
