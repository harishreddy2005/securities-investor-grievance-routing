import hashlib

import pytest

from app.rag.corpus import DOCUMENTS
from app.rag.ingest import ingest, normalize


def test_documents_and_hashes(settings):
    for filename, (_, _, digest) in DOCUMENTS.items():
        assert hashlib.sha256((settings.corpus_dir / filename).read_bytes()).hexdigest() == digest


def test_ingest_and_metadata(retriever, settings):
    assert retriever.manifest["chunks"] > 100
    assert set(retriever.manifest["documents"]) == set(DOCUMENTS)
    assert ingest(settings)["unchanged"]
    assert ingest(settings, re_embed_only=True)["chunks"] == retriever.manifest["chunks"]
    for doc, section, expected in [
        ("SEBI-SCORES-2023", "5.3", "Reserve Bank of India"),
        ("RBI-IOS-2021", "3(1)(j)", "means a bank"),
        ("RBI-IOS-2021", "9", "deficiency in service"),
        ("RBI-IOS-2021", "10(2)(a)", "30 days"),
        ("SEBI-MF-1996", "60A", "twenty-one calendar days"),
    ]:
        hits = retriever.lookup(doc, section)
        assert len(hits) == 1
        assert expected in hits[0].quote
        assert retriever.verify(hits[0])
    current_53 = retriever.lookup("SEBI-MF-1996", "53")[0]
    assert current_53.page == 80
    assert "specified by the Board" in current_53.quote
    assert "10 working days" not in current_53.quote


def test_retrieval_and_tamper_detection(retriever):
    hits = retriever.search("bank deficiency in service", "RBI-IOS-2021")
    assert hits and all(c.document_id == "RBI-IOS-2021" for c in hits)
    assert all(retriever.verify(c) for c in hits)
    assert not retriever.verify(hits[0].model_copy(update={"quote": "invented provision"}))


def test_checksum_failure(settings, tmp_path):
    from app.rag.ingest import parse_corpus
    first = next(iter(DOCUMENTS))
    (tmp_path / first).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        parse_corpus(tmp_path)
