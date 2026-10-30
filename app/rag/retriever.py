import json

from app.config import Settings
from app.rag.embeddings import LocalEmbeddings
from app.schemas import Citation


class Retriever:
    def __init__(self, settings: Settings):
        import chromadb
        self.manifest = json.loads((settings.index_dir / "manifest.json").read_text(encoding="utf-8"))
        if self.manifest["embedding_provider"] != settings.embedding_provider:
            raise ValueError("Index embedding provider differs; re-ingest with the configured provider")
        self.client = chromadb.PersistentClient(path=str(settings.index_dir / "chroma"),
                                               settings=chromadb.Settings(anonymized_telemetry=False))
        self.collection = self.client.get_collection(self.manifest["collection"], embedding_function=None)
        if self.collection.count() != self.manifest["chunks"]:
            raise ValueError("Index incomplete; re-run ingestion")
        self.embedding = LocalEmbeddings(settings.embedding_provider, settings.embedding_cache_dir)

    @staticmethod
    def citation(chunk_id, document, metadata):
        return Citation(chunk_id=chunk_id, quote=document, **metadata)

    def search(self, query: str, document_id: str | None = None, limit=5) -> list[Citation]:
        kwargs = {"where": {"document_id": document_id}} if document_id else {}
        result = self.collection.query(query_embeddings=[self.embedding.embed_query(query)], n_results=limit, **kwargs)
        return [self.citation(i, d, m) for i, d, m in zip(result["ids"][0], result["documents"][0], result["metadatas"][0])]

    def lookup(self, document_id: str, section: str) -> list[Citation]:
        result = self.collection.get(where={"$and": [{"document_id": document_id}, {"section": section}]})
        return [self.citation(i, d, m) for i, d, m in zip(result["ids"], result["documents"], result["metadatas"])]

    def verify(self, citation: Citation) -> bool:
        result = self.collection.get(ids=[citation.chunk_id])
        return bool(result["ids"]) and citation == self.citation(result["ids"][0], result["documents"][0], result["metadatas"][0])
