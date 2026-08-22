"""
Phase 5: Orchestration & Multimodal Planner DAG Tests.
"""
import pytest
from orchestrator.planner import Planner, PlanStep
from orchestrator.executor import Executor
from orchestrator.state_machine import TaskStateMachine, TaskStatus


def test_planner_detect_required_modalities():
    """Verify modality detection identifies multimodal requirements."""
    planner = Planner()

    # Document / Invoice
    mod_doc = planner.detect_required_modalities("Please read this scanned inspection report and check pressure values")
    assert "scanned_document" in mod_doc

    # P&ID / Drawing
    mod_dwg = planner.detect_required_modalities("Inspect the P&ID diagram schematic for valve V-101 connections")
    assert "engineering_drawing" in mod_dwg

    # Attachments detection
    mod_att = planner.detect_required_modalities("Review the attached file", file_attachments=["dwg_pid_sample.png"])
    assert "vision" in mod_att
    assert "engineering_drawing" in mod_att


def test_planner_multimodal_dag_generation():
    """Anti-hallucination verification: vision extraction MUST precede reasoning step."""
    planner = Planner()
    plan = planner.generate_plan("task_123", "Analyze the scanned document for compliance violations")

    assert len(plan.steps) >= 2
    step_1 = plan.steps[0]
    step_2 = plan.steps[1]

    # Step 1 should be structured visual extraction
    assert step_1.tool in ["analyze_scanned_document", "run_ocr", "analyze_engineering_drawing"]
    # Step 2 should depend on Step 1
    assert step_1.step_id in step_2.depends_on


def test_executor_multimodal_execution_flow():
    """Verify Executor properly executes a multimodal plan DAG."""
    planner = Planner()
    plan = planner.generate_plan("task_456", "Analyze the P&ID drawing for valve V-101")
    ordered_plan = planner.create_execution_graph(plan.steps)

    executor = Executor()
    result = executor.execute_plan(ordered_plan)

    assert result["status"] == "COMPLETED"
    assert len(result["results"]) >= 2
    # Verify events were collected
    assert any(ev["type"] == "plan_started" for ev in result["events"])
    assert any(ev["type"] == "plan_completed" for ev in result["events"])
