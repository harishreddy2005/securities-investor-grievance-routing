import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

from app.config import Settings
from app.rag.corpus import DOCUMENTS, SECTIONS
from app.rag.embeddings import LocalEmbeddings


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_corpus(corpus_dir: Path) -> list[dict]:
    chunks = []
    for filename, (doc_id, title, expected_hash) in DOCUMENTS.items():
        path = corpus_dir / filename
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected_hash:
            raise ValueError(f"Corpus checksum mismatch: {filename}; review SOURCES.md before indexing")
        pages = [normalize(page.extract_text() or "") for page in PdfReader(path).pages]
        if any(len(page) < 20 for page in pages):
            raise ValueError(f"Missing text layer: {filename}")

        def add(text, page, section, suffix):
            metadata = dict(document_id=doc_id, document_title=title, filename=filename,
                            page=page, section=section, sha256=digest)
            chunks.append(dict(id=f"{doc_id}:p{page}:{suffix}", text=text, metadata=metadata))

        for page, text in enumerate(pages, 1):
            for offset in range(0, len(text), 1150):
                add(text[offset:offset+1400], page, "page passage", f"c{offset}")
        for section_doc, section, first, last, start_pattern, end_pattern in SECTIONS:
            if section_doc != doc_id:
                continue
            combined = " ".join(pages[first-1:last])
            start = re.search(start_pattern, combined, re.I)
            if not start:
                raise ValueError(f"Reviewed section missing: {doc_id} {section}")
            end = re.search(end_pattern, combined[start.end():], re.I)
            if not end:
                raise ValueError(f"Reviewed section end missing: {doc_id} {section}")
            stop = start.end() + end.start()
            page = first + sum(start.start() >= len(" ".join(pages[first-1:i])) + 1 for i in range(first, last))
            add(combined[start.start():stop].strip(), page, section, f"s{section}")
    return chunks


def ingest(settings: Settings, re_embed_only=False) -> dict:
    import chromadb

    started = time.monotonic()
    settings.index_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = settings.index_dir / "chunks.json"
    chunks = json.loads(chunks_path.read_text(encoding="utf-8")) if re_embed_only else parse_corpus(settings.corpus_dir)
    fingerprint = hashlib.sha256(json.dumps(chunks, sort_keys=True).encode() + settings.embedding_provider.encode()).hexdigest()
    manifest_path = settings.index_dir / "manifest.json"
    client = chromadb.PersistentClient(path=str(settings.index_dir / "chroma"),
                                       settings=chromadb.Settings(anonymized_telemetry=False))
    collection_name = "regulations-" + fingerprint[:16]
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if previous["fingerprint"] == fingerprint and not re_embed_only:
            if client.get_collection(collection_name).count() == len(chunks):
                return {**previous, "unchanged": True}
    collection = client.get_or_create_collection(collection_name, metadata={"hnsw:space": "cosine"}, embedding_function=None)
    embedding = LocalEmbeddings(settings.embedding_provider, settings.embedding_cache_dir)
    for offset in range(0, len(chunks), 64):
        batch = chunks[offset:offset+64]
        collection.upsert(ids=[c["id"] for c in batch], documents=[c["text"] for c in batch],
                          metadatas=[c["metadata"] for c in batch],
                          embeddings=embedding.embed_documents([c["text"] for c in batch]))
    chunks_path.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    elapsed = time.monotonic() - started
    manifest = dict(fingerprint=fingerprint, collection=collection_name,
                    embedding_provider=settings.embedding_provider, chunks=len(chunks),
                    built_at=datetime.now(timezone.utc).isoformat(), seconds=elapsed,
                    chunks_per_second=len(chunks)/elapsed,
                    documents={name: data[2] for name, data in DOCUMENTS.items()})
    temporary = manifest_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    temporary.replace(manifest_path)
    return manifest
