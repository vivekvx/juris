"""Manual retrieval unit test — no external services required.

Tests the full M3 pipeline up to (but not including) external API calls:
  chunking → cosine similarity → citation building
"""
from datetime import datetime, timezone

import pytest

from app.models.chunk import Chunk, CURRENT_CHUNK_VERSION, EMBEDDING_MODEL
from app.repositories.chunk_repo import cosine_top_k, build_citation
from app.services.chunking import chunk_document, _estimate_tokens


LEGAL_TEXT = """
AGREEMENT FOR LEGAL SERVICES

This Agreement is entered into as of the date last signed below between the Client
and the Law Firm. The Law Firm agrees to provide legal representation in connection
with the matter described herein.

SECTION 1: SCOPE OF REPRESENTATION

The Law Firm shall represent the Client in all matters related to the dispute
described in Schedule A. This representation includes drafting pleadings, attending
hearings, and advising on settlement options.

SECTION 2: FEES AND BILLING

The Law Firm shall bill at an hourly rate as set forth in Schedule B. Client agrees
to maintain a retainer of five thousand dollars at all times during the representation.
Invoices are due within thirty days of issuance.

SECTION 3: CONFIDENTIALITY

All communications between Client and Law Firm are protected by attorney-client
privilege. The Law Firm shall not disclose any confidential information without
the prior written consent of the Client.
""".strip()

HINDI_TEXT = "यह एक कानूनी दस्तावेज़ है। " * 50  # Indic stress test


def _make_chunk(doc_id: str, idx: int, embedding: list[float], content: str = "test") -> Chunk:
    return Chunk(
        id=f"chunk-{idx}",
        doc_id=doc_id,
        owner_uid="user-123",
        content=content,
        embedding=embedding,
        chunk_index=idx,
        page_number=1,
        token_count=len(content.encode()) // 2,
        chunk_version=CURRENT_CHUNK_VERSION,
        embedding_model=EMBEDDING_MODEL,
        created_at=datetime.now(tz=timezone.utc),
    )


def _unit(dim: int, hot: int) -> list[float]:
    v = [0.0] * dim
    v[hot] = 1.0
    return v


class TestChunking:
    def test_english_text_produces_chunks(self):
        chunks = chunk_document(LEGAL_TEXT, mime_type="text/plain", size_tokens=512, overlap_tokens=50, max_chunks=1000)
        assert len(chunks) > 0
        for page_num, content, token_count in chunks:
            assert page_num is None  # TXT has no pages
            assert len(content) > 0
            assert token_count > 0

    def test_no_chunk_exceeds_embedding_limit(self):
        chunks = chunk_document(LEGAL_TEXT, mime_type="text/plain", size_tokens=512, overlap_tokens=50, max_chunks=1000)
        for _, _, token_count in chunks:
            assert token_count <= 2048, f"Chunk exceeds 2048-token embedding limit: {token_count}"

    def test_pdf_mime_assigns_page_numbers(self):
        pdf_text = "Page one content.\x0cPage two content.\x0cPage three content."
        chunks = chunk_document(pdf_text, mime_type="application/pdf", size_tokens=512, overlap_tokens=50, max_chunks=1000)
        assert len(chunks) > 0
        page_numbers = {pn for pn, _, _ in chunks}
        assert page_numbers == {1, 2, 3}

    def test_indic_chunks_safe_for_embedding(self):
        chunks = chunk_document(HINDI_TEXT, mime_type="text/plain", size_tokens=512, overlap_tokens=50, max_chunks=1000)
        assert len(chunks) > 0
        for _, _, token_count in chunks:
            assert token_count <= 2048

    def test_max_chunks_truncation(self):
        long_text = " ".join(f"Clause {i} states the following legal obligation." for i in range(5000))
        chunks = chunk_document(long_text, mime_type="text/plain", size_tokens=512, overlap_tokens=50, max_chunks=10)
        assert len(chunks) <= 10

    def test_empty_text_returns_empty(self):
        assert chunk_document("   ", mime_type="text/plain", size_tokens=512, overlap_tokens=50, max_chunks=1000) == []

    def test_token_estimate_conservative_for_indic(self):
        # Hindi 'क' = 3 bytes UTF-8 → estimate = 3 // 2 = 1 per char
        text = "क" * 100  # 300 bytes → 150 token estimate
        assert _estimate_tokens(text) == 150


class TestCosineRetrieval:
    def test_top_match_returned_first(self):
        dim = 8
        chunks = [_make_chunk("doc1", i, _unit(dim, i)) for i in range(dim)]
        results = cosine_top_k(_unit(dim, 3), chunks, top_k=3, doc_ids=None, score_threshold=0.0)
        assert len(results) == 3
        top_chunk, top_score = results[0]
        assert top_chunk.chunk_index == 3
        assert abs(top_score - 1.0) < 1e-5

    def test_score_threshold_filters(self):
        dim = 4
        chunks = [_make_chunk("doc1", i, _unit(dim, i)) for i in range(dim)]
        results = cosine_top_k(_unit(dim, 0), chunks, top_k=4, doc_ids=None, score_threshold=0.5)
        assert len(results) == 1
        assert results[0][0].chunk_index == 0

    def test_doc_id_scoping(self):
        dim = 4
        all_chunks = [_make_chunk("doc-a", i, _unit(dim, i)) for i in range(2)] + \
                     [_make_chunk("doc-b", i, _unit(dim, i)) for i in range(2)]
        results = cosine_top_k(_unit(dim, 1), all_chunks, top_k=4, doc_ids=["doc-a"], score_threshold=0.0)
        assert all(c.doc_id == "doc-a" for c, _ in results)

    def test_empty_chunks_returns_empty(self):
        assert cosine_top_k([1.0, 0.0], [], top_k=5, doc_ids=None, score_threshold=0.0) == []

    def test_citation_built_correctly(self):
        chunk = _make_chunk("doc1", 0, [1.0, 0.0], content="The indemnification clause states...")
        citation = build_citation(chunk, "contract.pdf", score=0.92)
        assert citation.doc_id == "doc1"
        assert citation.original_filename == "contract.pdf"
        assert citation.score == 0.92
        assert "indemnification" in citation.content
