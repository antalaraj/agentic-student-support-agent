"""Policy and handbook retrieval tools (RAG)."""
from config import settings
from rag.retrieval import retrieve
from tools.base import err, safe_tool


def _search(query: str, category: str, what: str) -> dict:
    if not isinstance(query, str) or not query.strip():
        return err("invalid_input", "A non-empty search query is required.")
    hits = retrieve(query.strip(), category=category)
    if not hits:
        return {
            "status": "no_evidence",
            "query": query,
            "message": f"The handbook does not contain enough information about this {what}.",
            "recommendation": f"Please contact the {settings.CONTACT_OFFICE}.",
        }
    return {
        "status": "ok",
        "query": query,
        "results": [
            {
                "chunk_id": h["chunk_id"],
                "section": h["section"],
                "source": h["source"],
                "relevance": h["relevance"],
                "text": h["text"],
            }
            for h in hits
        ],
    }


@safe_tool
def search_policy(query: str) -> dict:
    """Search the student handbook for rules and procedures (fees, late fees, scholarships, course change,
    attendance, examinations, support). Returns relevant passages with section names.
    """
    return _search(query, "policy", "policy question")


@safe_tool
def search_academic_information(query: str) -> dict:
    """Search the handbook for academic information: programmes, courses, electives, credits,
    placements, internships and general administration.
    """
    return _search(query, "academic", "academic question")
