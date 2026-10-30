from langchain_core.tools import tool


def make_tools(retriever, request, events):
    calls = 0

    def record(action, detail):
        nonlocal calls
        calls += 1
        if calls > 12:
            raise RuntimeError("Investigator tool budget exceeded")
        events.append(dict(agent="investigator", action=action, detail=detail))

    @tool
    def inspect_request_fields() -> dict:
        """Read validated product, entity and prior-complaint fields."""
        record("inspect_request_fields", "Read complaint and prior approach details")
        return request.model_dump(mode="json")

    @tool
    def search_regulatory_corpus(query: str, document_id: str = "") -> list[dict]:
        """Search active regulatory passages semantically, optionally within a document."""
        record("search_regulatory_corpus", query)
        return [c.model_dump() for c in retriever.search(query, document_id or None)]

    @tool
    def lookup_clause(document_id: str, section: str) -> list[dict]:
        """Retrieve an exact reviewed section, retaining PDF provenance."""
        record("lookup_clause", document_id + " section " + section)
        return [c.model_dump() for c in retriever.lookup(document_id, section)]

    return inspect_request_fields, search_regulatory_corpus, lookup_clause
