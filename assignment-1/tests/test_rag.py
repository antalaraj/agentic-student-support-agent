import pymupdf
import pytest

from config import settings
from rag import ingestion
from rag.embeddings import HashingEmbedder, backend_name
from rag.retrieval import retrieve


def test_chunking_follows_sections_and_is_reasonable():
    chunks = ingestion.split_into_chunks(ingestion.load_text(settings.handbook_path()))
    assert 15 <= len(chunks) <= 40
    assert all(len(c["text"]) <= 900 for c in chunks)
    assert {c["category"] for c in chunks} == {"policy", "academic"}
    assert len({c["id"] for c in chunks}) == len(chunks)
    assert any("Late Fee" in c["section"] for c in chunks)


def test_ingestion_is_idempotent():
    assert ingestion.ingest()["status"] == "ingested"
    assert ingestion.ingest()["status"] == "up_to_date"
    assert ingestion.ingest(force=True)["status"] == "ingested"


def test_reingests_when_handbook_changes(tmp_path, monkeypatch):
    ingestion.ingest()
    new = tmp_path / "hb.txt"
    new.write_text("## 1. Fee Payment Rules [policy]\nClause 1.1 Fees are due on Fridays.\n", encoding="utf-8")
    monkeypatch.setenv("HANDBOOK_PATH", str(new))
    assert ingestion.ingest()["status"] == "ingested"


@pytest.mark.parametrize("query,expected_prefix", [
    ("What is the late fee policy?", "hb-2"),
    ("The payment portal failed. Can I pay on the next working day?", "hb-1"),
    ("Can I change my programme?", "hb-5"),
    ("What is the attendance requirement?", "hb-6"),
    ("What is the eligibility for the Merit Excellence Award?", "hb-4"),
    ("How do I raise a support ticket?", "hb-8"),
])
def test_retrieval_finds_the_right_section(query, expected_prefix):
    hits = retrieve(query)
    assert hits and any(h["chunk_id"].startswith(expected_prefix) for h in hits[:2])


def test_only_top_k_chunks_not_whole_document():
    assert len(retrieve("late fee")) <= settings.RAG_TOP_K
    total = len(ingestion.split_into_chunks(ingestion.load_text(settings.handbook_path())))
    assert len(retrieve("late fee")) < total


@pytest.mark.parametrize("query", ["hostel accommodation rules", "visa process for exchange students", "cafeteria menu", "parking permit for my car"])
def test_unrelated_questions_return_no_evidence(query):
    assert retrieve(query) == []


def test_category_filter():
    assert all(h["chunk_id"].startswith(("hb-9", "hb-10")) for h in retrieve("Which electives are offered in AI?", category="academic"))


def test_pdf_loading_with_pymupdf(tmp_path):
    pdf = tmp_path / "t.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "## 1. Test Section [policy]\nClause 1.1 Hello PDF world.")
    doc.save(str(pdf))
    assert "Hello PDF world" in ingestion.load_text(pdf)


def test_embedder_is_deterministic_and_normalised():
    e = HashingEmbedder()
    a, b = e.embed(["late fee"])[0], e.embed(["late fee"])[0]
    assert a == b and abs(sum(x * x for x in a) - 1) < 1e-6 and len(a) == 384
    assert backend_name() == "hashing-fallback-384"
