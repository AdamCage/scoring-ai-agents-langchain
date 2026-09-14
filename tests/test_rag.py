from creditlens.presets import presets
from creditlens.rag.documents import load_documents
from creditlens.rag.retrieve import retrieve_policy


def test_knowledge_base_has_enough_docs():
    assert len(load_documents()) >= 12


def test_hybrid_retrieval_returns_citations():
    docs, debug = retrieve_policy(presets()[0].application)
    assert docs
    assert all(doc.citation for doc in docs)
    assert debug.vector_ids
    assert debug.bm25_ids
    assert debug.reranked_ids
