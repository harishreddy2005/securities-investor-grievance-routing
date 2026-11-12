import json

from app.config import Settings
from app.rag.embeddings import LocalEmbeddings
from app.schemas import Citation


class Retriever:
    def __init__(self, settings: Settings):
        self.settings = settings
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
        return self._bounded(lambda: self._search(query,document_id,limit), "search")

    def _bounded(self, function, operation):
        from app.reliability import retry_call
        from app.observability.runtime import span, record_tool
        if operation == "verify":
            record_tool()
        with span("retrieval", operation=operation):
            return retry_call(function,"retrieval",self.settings,self.settings.retrieval_timeout)

    def _search(self, query, document_id, limit):
        from app.eval.cache import global_query_cache
        cache_enabled = getattr(self.settings, "enable_query_cache", True)
        cache_key = f"{self.manifest['fingerprint']}:{self.manifest['embedding_provider']}:{document_id or '*'}:{limit}:{query}"
        if cache_enabled:
            cached = global_query_cache.get("search", cache_key)
            if cached is not None:
                return [Citation.model_validate(c) for c in cached]
        kwargs = {"where": {"document_id": document_id}} if document_id else {}
        result = self.collection.query(query_embeddings=[self.embedding.embed_query(query)], n_results=limit, **kwargs)
        citations = [self.citation(i, d, m) for i, d, m in zip(result["ids"][0], result["documents"][0], result["metadatas"][0])]
        if cache_enabled:
            global_query_cache.set("search", cache_key, [c.model_dump(mode="json") for c in citations])
        return citations

    def lookup(self, document_id: str, section: str) -> list[Citation]:
        return self._bounded(lambda: self._lookup(document_id,section), "lookup")

    def _lookup(self, document_id, section):
        from app.eval.cache import global_query_cache
        cache_enabled = getattr(self.settings, "enable_query_cache", True)
        cache_key = f"{self.manifest['fingerprint']}:{self.manifest['embedding_provider']}:{document_id}:{section}"
        if cache_enabled:
            cached = global_query_cache.get("lookup", cache_key)
            if cached is not None:
                return [Citation.model_validate(c) for c in cached]
        result = self.collection.get(where={"$and": [{"document_id": document_id}, {"section": section}]})
        citations = [self.citation(i, d, m) for i, d, m in zip(result["ids"], result["documents"], result["metadatas"])]
        if cache_enabled:
            global_query_cache.set("lookup", cache_key, [c.model_dump(mode="json") for c in citations])
        return citations

    def verify(self, citation: Citation) -> bool:
        return self._bounded(lambda: self._verify(citation), "verify")

    def _verify(self, citation):
        result = self.collection.get(ids=[citation.chunk_id])
        return bool(result["ids"]) and citation == self.citation(result["ids"][0], result["documents"][0], result["metadatas"][0])
