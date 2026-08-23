"""
Phase 8 tests — Validation Engine (Grounding, Calculation, Schema, Replan).

Covers:
  - Validator: extract_claims, verify_claim_against_sources, calculate_grounding_score,
    detect_unsupported_claims (RAG grounding), detect_hallucination_risk (vision grounding),
    validate_calculations (independent sandbox re-check).
  - validation/artifact_validators.py: format validators + file-integrity gate, reusing
    Phase 7's real writers.
  - Planner.replan(): regenerates a plan with the failure reason injected.
  - Executor: a failed artifact-format check fails the step (no bad artifact reaches DB).
  - Full agent-loop integration: forced low-grounding RAG answer triggers the replan
    loop and either recovers or escalates to human review after 3 attempts (DoD).
"""
import json
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import app
from database.session import Base, engine, get_db
from database.models import Task, TaskStep, ToolCall, ModelRoute, Artifact, AuditLog
from api.auth import get_current_user, UserInfo
from sqlalchemy.orm import sessionmaker

from orchestrator.validator import Validator
from orchestrator.planner import Planner
from artifacts.docx_writer import DocxWriter
from artifacts.xlsx_writer import XlsxWriter
from artifacts.pdf_writer import PdfWriter
from validation.artifact_validators import (
    validate_artifact, validate_docx, validate_xlsx, validate_pdf,
    validate_file_integrity, validate_required_sections,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def override_get_current_user():
    return UserInfo(username="test-operator", role="operator")


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user
client = TestClient(app)

TEST_TASK_ID = "phase8-test"


@pytest.fixture(autouse=True)
def setup_db():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    if not db.query(Task).filter(Task.id == TEST_TASK_ID).first():
        db.add(Task(id=TEST_TASK_ID, description="Phase 8 test fixture task", status="COMPLETED"))
        db.commit()
    db.close()

    yield

    db = TestingSessionLocal()
    db.query(Artifact).delete()
    db.query(TaskStep).delete()
    db.query(ToolCall).delete()
    db.query(ModelRoute).delete()
    db.query(AuditLog).delete()
    db.query(Task).delete()
    db.commit()
    db.close()
    app.dependency_overrides.clear()


# ── Claim extraction & grounding ─────────────────────────────────────────────

def test_extract_claims_filters_short_fragments():
    v = Validator()
    claims = v.extract_claims("Findings. The valve pressure reached 450 PSI during the test run. OK.")
    assert "The valve pressure reached 450 PSI during the test run." in claims
    assert "Findings." not in claims
    assert "OK." not in claims


def test_extract_claims_empty_input():
    v = Validator()
    assert v.extract_claims("") == []
    assert v.extract_claims(None) == []


def test_verify_claim_against_sources_supported_vs_unsupported():
    v = Validator()
    sources = "The valve pressure limit is 450 PSI according to SOP-14."
    supported = v.verify_claim_against_sources("The valve pressure limit is 450 PSI.", sources)
    unsupported = v.verify_claim_against_sources("The reactor temperature exceeded 900 degrees.", sources)
    assert supported > unsupported
    assert supported >= 0.5
    assert unsupported < 0.3


def test_verify_claim_against_sources_accepts_chunk_dicts():
    v = Validator()
    sources = [{"doc_id": "sop-1", "text": "Depressurize the line to 450 PSI before maintenance."}]
    score = v.verify_claim_against_sources("Depressurize the line to 450 PSI.", sources)
    assert score > 0.5


def test_verify_claim_against_sources_no_sources_returns_zero():
    v = Validator()
    assert v.verify_claim_against_sources("Anything at all.", None) == 0.0
    assert v.verify_claim_against_sources("Anything at all.", "") == 0.0


def test_calculate_grounding_score_no_claims_is_trivially_grounded():
    v = Validator()
    assert v.calculate_grounding_score([], "some source text") == 1.0


def test_calculate_grounding_score_aggregates():
    v = Validator()
    sources = "The valve pressure limit is 450 PSI."
    claims = ["The valve pressure limit is 450 PSI.", "The reactor melted down completely."]
    score = v.calculate_grounding_score(claims, sources)
    assert 0.0 < score < 1.0


def test_detect_unsupported_claims():
    v = Validator()
    sources = "The valve pressure limit is 450 PSI."
    claims = ["The valve pressure limit is 450 PSI.", "The reactor melted down completely."]
    unsupported = v.detect_unsupported_claims(claims, sources)
    assert "The reactor melted down completely." in unsupported
    assert "The valve pressure limit is 450 PSI." not in unsupported


# ── Vision hallucination detection ───────────────────────────────────────────

def test_detect_hallucination_risk_flags_unseen_tags():
    v = Validator()
    extraction = {
        "full_text": "PT-101 reading nominal.",
        "key_values": {"Inspector": "J. Doe"},
        "components": [{"tag": "V-101"}],
        "instruments": [{"tag": "PT-101"}],
    }
    claims = ["PT-101 shows a nominal reading.", "Valve V-999 was found leaking at 999 PSI."]
    flagged = v.detect_hallucination_risk(claims, extraction)
    assert "Valve V-999 was found leaking at 999 PSI." in flagged
    assert "PT-101 shows a nominal reading." not in flagged


def test_detect_hallucination_risk_no_extraction_flags_everything():
    v = Validator()
    claims = ["Something with a number 42 in it."]
    assert v.detect_hallucination_risk(claims, None) == claims


# ── Calculation re-checking ──────────────────────────────────────────────────

def test_validate_calculations_correct_result():
    v = Validator()
    result = v.validate_calculations(code="print(5 + 5)", stated_result="10")
    assert result["valid"] is True
    assert result["actual_output"] == "10"


def test_validate_calculations_wrong_result():
    v = Validator()
    result = v.validate_calculations(code="print(5 + 5)", stated_result="42")
    assert result["valid"] is False
    assert result["actual_output"] == "10"
    assert result["stated_result"] == "42"


def test_validate_calculations_numeric_tolerance():
    v = Validator()
    result = v.validate_calculations(code="print(1/3)", stated_result="The answer is approximately 0.3333333333333333.")
    assert result["valid"] is True


# ── Artifact-format validators (Phase 7 writers → Phase 8 gate) ──────────────

def test_validate_docx_passes_on_real_writer_output():
    result = DocxWriter().create_docx(task_id=TEST_TASK_ID, title="Report", content="Body text here.")
    check = validate_artifact(result)
    assert check["valid"] is True


def test_validate_docx_fails_on_corrupt_file(tmp_path):
    bad_path = tmp_path / "broken.docx"
    bad_path.write_bytes(b"not a real docx file")
    check = validate_docx(str(bad_path))
    assert check["valid"] is False


def test_validate_xlsx_detects_formula_error_string():
    result = XlsxWriter().create_xlsx(task_id=TEST_TASK_ID, title="Data", headers=["A"], rows=[["ok"]])
    from openpyxl import load_workbook
    wb = load_workbook(result["path"])
    wb.active["A2"] = "#REF!"
    wb.save(result["path"])
    check = validate_xlsx(result["path"])
    assert check["valid"] is False
    assert any("#REF!" in e for e in check["errors"])


def test_validate_pdf_passes_on_real_writer_output():
    result = PdfWriter().create_pdf(task_id=TEST_TASK_ID, title="Report", content="Body text here.")
    check = validate_pdf(result["path"])
    assert check["valid"] is True


def test_validate_pdf_fails_on_non_pdf_bytes(tmp_path):
    bad_path = tmp_path / "fake.pdf"
    bad_path.write_bytes(b"definitely not a pdf")
    check = validate_pdf(str(bad_path))
    assert check["valid"] is False


def test_validate_file_integrity_detects_tamper():
    result = DocxWriter().create_docx(task_id=TEST_TASK_ID, title="Tamper", content="Original.")
    ok = validate_file_integrity(result["path"], result["file_hash"])
    assert ok["valid"] is True
    with open(result["path"], "ab") as f:
        f.write(b"TAMPERED")
    tampered = validate_file_integrity(result["path"], result["file_hash"])
    assert tampered["valid"] is False


def test_validate_required_sections():
    ok = validate_required_sections("Introduction\n\nReferences\n\nConclusion", ["Introduction", "References"])
    assert ok["valid"] is True
    missing = validate_required_sections("Introduction only", ["Introduction", "References"])
    assert missing["valid"] is False
    assert "References" in missing["missing"]


def test_validate_artifact_full_gate_end_to_end():
    result = DocxWriter().create_docx(
        task_id=TEST_TASK_ID, title="Compliance Report", content="All checks passed."
    )
    check = validate_artifact(result, required_sections=["Compliance Report"])
    assert check["valid"] is True


# ── Planner.replan() ──────────────────────────────────────────────────────────

def test_replan_injects_failure_reason(monkeypatch):
    from models.registry import registry
    captured_prompts = []

    def mock_execute_prompt(model_id, prompt):
        captured_prompts.append(prompt)
        return json.dumps({"steps": [{"step_id": "step_1", "action": "Retry", "tool": "direct_llm", "depends_on": [], "params": {}}]}), 10.0

    monkeypatch.setattr(registry, "execute_prompt", mock_execute_prompt)
    p = Planner()
    plan = p.replan("task-z", "Summarize the SOP", failure_reason="Grounding score 0.1 below threshold")
    assert len(plan.steps) >= 1
    assert any("Grounding score 0.1 below threshold" in prompt for prompt in captured_prompts)


# ── Executor: bad artifact fails its step ────────────────────────────────────

def test_executor_rejects_invalid_artifact_and_retries(monkeypatch):
    """A generate_docx call that produces an artifact failing validation must
    fail the step (not silently persist a bad artifact) — Phase 8 DoD."""
    from orchestrator.executor import Executor
    from orchestrator.planner import ExecutionPlan, PlanStep
    from orchestrator import validator as validator_module

    call_count = {"n": 0}
    original_validate = validator_module.Validator.validate_artifact

    def flaky_validate(self, artifact_meta, required_sections=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"valid": False, "errors": ["simulated corruption on first attempt"]}
        return original_validate(self, artifact_meta, required_sections=required_sections)

    monkeypatch.setattr(validator_module.Validator, "validate_artifact", flaky_validate)

    plan = ExecutionPlan(task_id=TEST_TASK_ID, steps=[
        PlanStep(step_id="step_1", action="Generate report", tool="generate_docx",
                 depends_on=[], params={"title": "Flaky Report", "content": "Body"}),
    ])
    ex = Executor(db_session=None)
    result = ex.execute_plan(plan)

    assert call_count["n"] >= 2  # first attempt rejected, retried, second attempt accepted
    assert result["status"] == "COMPLETED"


# ── Full agent-loop integration: replan-until-resolved / escalation ─────────

def test_agent_replans_and_recovers_when_grounding_improves(monkeypatch):
    """First attempt returns an ungrounded claim with no supporting source found
    (rag_search returns nothing); second attempt (after replan) is grounded."""
    from models.registry import registry

    attempt = {"n": 0}

    def mock_execute_prompt(model_id, prompt):
        # Check the corrective-note marker BEFORE the planner-prompt check — a
        # replan's prompt is the system planner prompt PLUS the corrective note,
        # so both substrings are present at once and order matters here.
        if "IMPORTANT: a previous attempt" in prompt:
            attempt["n"] += 1
        if "You are a task planner." in prompt:
            plan = {"steps": [
                {"step_id": "s1", "action": "Search SOP", "tool": "rag_search", "depends_on": [], "params": {"query": "pressure limit"}},
                {"step_id": "s2", "action": "Answer", "tool": "direct_llm", "depends_on": ["s1"], "params": {"prompt": "Answer using retrieved SOP"}},
            ]}
            return json.dumps(plan), 10.0
        # direct_llm steps and rag_search go through this branch too (rag_search
        # calls _get_query_embedding/_search_qdrant directly, not execute_prompt,
        # so this only affects direct_llm's answer).
        if attempt["n"] >= 1:
            return "The valve pressure limit is 450 PSI as stated in the SOP.", 10.0
        return "The reactor achieved cold fusion at zero cost.", 10.0

    def mock_rag_search(query=None, prompt=None, **kwargs):
        return "[1] (Doc: sop-1): The valve pressure limit is 450 PSI."

    monkeypatch.setattr(registry, "execute_prompt", mock_execute_prompt)
    monkeypatch.setattr("rag.retrieval.rag_search", lambda q, filters=None: mock_rag_search(query=q))

    response = client.post("/api/agent", json={"prompt": "What does the SOP say about valve pressure limits?"})
    assert response.status_code == 200
    data = response.json()
    assert data["retry_count"] >= 1
    assert data["status"] == "COMPLETED"
    assert data["validation_passed"] is True
    assert data["grounding_score"] >= 0.5


def test_agent_escalates_to_human_review_after_max_replans(monkeypatch):
    """An answer that never grounds against its sources exhausts all replan
    attempts and ends FAILED with an ESCALATED_TO_HUMAN_REVIEW audit entry."""
    from models.registry import registry

    def mock_execute_prompt(model_id, prompt):
        if "You are a task planner." in prompt:
            plan = {"steps": [
                {"step_id": "s1", "action": "Search SOP", "tool": "rag_search", "depends_on": [], "params": {"query": "pressure limit"}},
                {"step_id": "s2", "action": "Answer", "tool": "direct_llm", "depends_on": ["s1"], "params": {"prompt": "Answer"}},
            ]}
            return json.dumps(plan), 10.0
        # Always hallucinates, regardless of replan attempt.
        return "The reactor achieved cold fusion and produced infinite energy.", 10.0

    def mock_rag_search(query=None, prompt=None, **kwargs):
        return "[1] (Doc: sop-1): The valve pressure limit is 450 PSI."

    monkeypatch.setattr(registry, "execute_prompt", mock_execute_prompt)
    monkeypatch.setattr("rag.retrieval.rag_search", lambda q, filters=None: mock_rag_search(query=q))

    response = client.post("/api/agent", json={"prompt": "What does the SOP say about valve pressure limits?"})
    assert response.status_code == 200
    data = response.json()

    assert data["retry_count"] >= 3
    assert data["status"] == "FAILED"
    assert data["validation_passed"] is False
    assert data["validation_report"]["escalated"] is True

    db = TestingSessionLocal()
    escalation = db.query(AuditLog).filter(AuditLog.action == "ESCALATED_TO_HUMAN_REVIEW").first()
    db.close()
    assert escalation is not None
    assert data["task_id"] in escalation.details


def test_agent_persists_grounding_score_and_report_on_task(monkeypatch):
    from models.registry import registry

    def mock_execute_prompt(model_id, prompt):
        if "You are a task planner." in prompt:
            return json.dumps({"steps": [
                {"step_id": "s1", "action": "Explain", "tool": "direct_llm", "depends_on": [], "params": {"prompt": "Explain gravity"}}
            ]}), 10.0
        return "Gravity is a fundamental force that attracts masses toward each other.", 10.0

    monkeypatch.setattr(registry, "execute_prompt", mock_execute_prompt)
    response = client.post("/api/agent", json={"prompt": "Explain gravity"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["grounding_score"] == 1.0  # no RAG/vision source used -> trivially grounded

    db = TestingSessionLocal()
    task = db.query(Task).filter(Task.id == data["task_id"]).first()
    db.close()
    assert task.grounding_score == 1.0
    assert task.retry_count == 0
    report = json.loads(task.validation_report)
    assert report["grounding_score"] == 1.0
