from pathlib import Path

import pytest

from app.config import Settings
from app.rag.ingest import ingest
from app.rag.retriever import Retriever


@pytest.fixture(scope="session")
def settings(tmp_path_factory):
    return Settings(_env_file=None, index_dir=tmp_path_factory.mktemp("index"),
                    corpus_dir=Path(__file__).resolve().parents[1] / "corpus/raw",
                    embedding_provider="test_hash", llm_stub_url="")


@pytest.fixture(scope="session")
def retriever(settings):
    ingest(settings)
    return Retriever(settings)


@pytest.fixture
def reference():
    return {"complaint_text": "I invested in a fixed deposit through my bank's app. The interest credited is lower than what I was promised. I want to complain to SEBI.",
            "entity_name": "Example Bank Ltd", "named_regulator": "SEBI", "approached_entity_first": False}
