"""
Phase 1 backend smoke tests.

Run with: pytest backend/tests/ -v
"""
import sys
import os
from unittest.mock import patch

# Ensure backend package is on the path when running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── RAG ingest tests ─────────────────────────────────────────────────────────
from rag.ingest import chunk_document


class TestChunkDocument:
    def test_empty_string_returns_empty_list(self):
        assert chunk_document("") == []

    def test_single_sentence(self):
        chunks = chunk_document("Hello world.", chunk_size=512)
        assert len(chunks) == 1
        assert "Hello world." in chunks[0]["text"]

    def test_multiple_chunks_produced(self):
        # 10 long sentences that together exceed the default chunk_size
        doc = " ".join([f"This is sentence number {i} which is quite long indeed." for i in range(30)])
        chunks = chunk_document(doc, chunk_size=200, chunk_overlap=20)
        assert len(chunks) > 1

    def test_chunk_schema(self):
        chunks = chunk_document("First sentence. Second sentence. Third sentence.")
        for chunk in chunks:
            assert "chunk_index" in chunk
            assert "text" in chunk
            assert "char_start" in chunk
            assert "char_end" in chunk

    def test_whitespace_only_returns_empty(self):
        assert chunk_document("   \n\t  ") == []


# ── OCR preprocess tests ──────────────────────────────────────────────────────
from ocr.preprocess import preprocess_image, preprocess_pdf_page


class TestPreprocessImage:
    def test_missing_file_returns_error(self):
        result = preprocess_image("/nonexistent/path/image.jpg")
        assert result["status"] == "error"

    def test_pdf_missing_pdf2image_returns_error(self, tmp_path):
        # Create a dummy (non-PDF) file — pdf2image will fail gracefully
        dummy = tmp_path / "fake.pdf"
        dummy.write_bytes(b"%PDF-1.4 dummy content")
        result = preprocess_pdf_page(str(dummy), page_index=0)
        # Either pdf2image not installed (error) or parse error — both are "error"
        assert result["status"] == "error"


# ── State machine tests ───────────────────────────────────────────────────────
from orchestrator.state_machine import TaskStateMachine, TaskStatus


class TestTaskStateMachine:
    def test_initial_state(self):
        sm = TaskStateMachine("task-001")
        assert sm.status == TaskStatus.CREATED

    def test_valid_transition(self):
        sm = TaskStateMachine("task-001")
        sm.transition(TaskStatus.CLASSIFIED)
        assert sm.status == TaskStatus.CLASSIFIED

    def test_invalid_transition_raises(self):
        sm = TaskStateMachine("task-001")
        import pytest
        with pytest.raises(ValueError, match="Illegal transition"):
            sm.transition(TaskStatus.COMPLETED)  # CREATED → COMPLETED is illegal

    def test_full_happy_path(self):
        sm = TaskStateMachine("task-002")
        for state in [
            TaskStatus.CLASSIFIED,
            TaskStatus.PLANNED,
            TaskStatus.EXECUTING,
            TaskStatus.VALIDATING,
            TaskStatus.COMPLETED,
        ]:
            sm.transition(state)
        assert sm.status == TaskStatus.COMPLETED


# ── Model registry tests ──────────────────────────────────────────────────────
from models.registry import ModelRegistry


class TestModelRegistry:
    def test_route_task_returns_string(self):
        reg = ModelRegistry()
        model_id = reg.route_task("What is the capital of France?")
        assert isinstance(model_id, str)
        assert len(model_id) > 0

    @patch.dict('os.environ', {'OLLAMA_MOCK_FALLBACK': 'true'})
    def test_execute_prompt_returns_tuple(self):
        """Ollama won't be running in CI; mock fallback must still return a tuple."""
        reg = ModelRegistry()
        result = reg.execute_prompt("test-model", "Hello")
        assert isinstance(result, tuple)
        assert len(result) == 2
        text, latency = result
        assert isinstance(text, str)
        assert isinstance(latency, float)
        assert latency >= 0
