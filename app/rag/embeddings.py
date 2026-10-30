"""Semantic embeddings in normal operation; explicit offline test embedding."""
import hashlib
import math
import re
from pathlib import Path

from langchain_core.embeddings import Embeddings


class LocalEmbeddings(Embeddings):
    def __init__(self, provider="chroma", cache_dir=Path("data/models")):
        self.provider = provider
        if provider == "chroma":
            from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2
            self.model = ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])
            self.model.DOWNLOAD_PATH = Path(cache_dir)
        elif provider != "test_hash":
            raise ValueError("EMBEDDING_PROVIDER must be chroma or test_hash")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if self.provider == "chroma":
            return [list(map(float, row)) for row in self.model(texts)]
        vectors = []
        for text in texts:
            vector = [0.0] * 256
            for token in re.findall(r"\w+", text.lower()):
                vector[int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % 256] += 1
            norm = math.sqrt(sum(x*x for x in vector)) or 1
            vectors.append([x / norm for x in vector])
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]
