"""
Planner ΓÇö Phase 3/5 implementation (M1).

generate_plan() calls the reasoning model with a structured prompt,
parses the JSON plan response into a DAG of PlanSteps.
detect_required_modalities() extracts multimodal requirements (OCR, Vision, P&ID).
decompose_task() breaks a description into sub-tasks.
create_execution_graph() topologically orders steps using Kahn's algorithm.
"""
from __future__ import annotations
import json
import uuid
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    step_id: str
    action: str
    tool: str | None = None
    depends_on: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    status: str = "PENDING"   # PENDING | RUNNING | DONE | FAILED


@dataclass
class ExecutionPlan:
    task_id: str
    steps: list[PlanStep] = field(default_factory=list)


# System prompt used to instruct the reasoning model to produce a structured plan
_PLAN_SYSTEM_PROMPT = """
You are a task planner. Given a user task description, produce a JSON execution plan.
The plan must be a JSON object with a key "steps" containing a list of step objects.
Each step object must have:
  - "step_id": a short unique ID like "step_1"
  - "action": a brief description of what to do
  - "tool": tool to use. Available options:
      * "direct_llm": Use for summarization, checklists, reasoning, writing, and text analysis (Default for general steps).
      * "analyze_scanned_document": Use FIRST if analyzing a scanned report, form, inspection sheet, or document image.
      * "analyze_engineering_drawing": Use FIRST if analyzing a P&ID, schematic, blueprint, or engineering drawing.
      * "run_ocr": Use for low-level OCR text extraction on images.
      * "execute_python": Use ONLY if the step requires executing actual Python code or calculations.
      * "rag_search": Use ONLY if searching stored SOPs, manuals, or documents (params: query).
      * "generate_docx": Use LAST if the user wants a downloadable report/document/approval note (params: title, content, optional table, optional citations).
      * "generate_xlsx": Use LAST if the user wants a downloadable spreadsheet/table export (params: title, headers, rows).
      * "generate_pdf": Use LAST if the user explicitly wants a PDF file (params: title, content, optional table).
      * "generate_csv"/"generate_json": Use LAST for a downloadable CSV or JSON data export (params: title, headers/rows or data).
  - "depends_on": list of step_ids this step depends on (can be empty list)
  - "params": dict of parameters for the tool call (can be empty dict)

Anti-Hallucination Rule: Whenever an image, scan, or drawing is involved, you MUST insert the appropriate vision extraction step before any reasoning or summarization step.
Deliverable Rule: Whenever the user asks for a downloadable file/report/document/spreadsheet, the LAST step MUST use one of the generate_* artifact tools, depending on the step(s) whose output it should contain.

Only output valid JSON, no extra text.
Example for multimodal document task:
{
  "steps": [
    {"step_id": "step_1", "action": "Extract structured fields from scanned report", "tool": "analyze_scanned_document", "depends_on": [], "params": {}},
    {"step_id": "step_2", "action": "Summarize findings and flag any low-confidence areas", "tool": "direct_llm", "depends_on": ["step_1"], "params": {}}
  ]
}
"""


class Planner:
    """
    Converts a task description into an ExecutionPlan (DAG of steps).
    """

    def detect_required_modalities(self, description: str, file_attachments: list[str] | None = None) -> list[str]:
        """
        Phase 5 (M1): Detects required input/output modalities.
        Returns a subset of ['text', 'scanned_document', 'engineering_drawing', 'ocr', 'code', 'rag'].
        """
        modalities = ["text"]
        desc_lower = description.lower()

        # Check file attachments if present
        if file_attachments:
            for f in file_attachments:
                f_lower = f.lower()
                if any(f_lower.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]):
                    modalities.append("vision")
                    # Any image attachment is presumed to be a scanned document
                    # unless the filename/prompt explicitly indicates a P&ID/drawing
                    if not ("pid" in f_lower or "drawing" in f_lower or "schematic" in f_lower or "dwg" in f_lower):
                        modalities.append("scanned_document")
                elif f_lower.endswith(".pdf"):
                    modalities.append("pdf")
                if "pid" in f_lower or "drawing" in f_lower or "schematic" in f_lower or "dwg" in f_lower:
                    modalities.append("engineering_drawing")


        # Check description keywords
        if any(kw in desc_lower for kw in ["p&id", "drawing", "schematic", "blueprint", "valve", "instrumentation", "pipe"]):
            modalities.append("engineering_drawing")
        elif any(kw in desc_lower for kw in ["scan", "scanned", "invoice", "receipt", "inspection report", "form"]):
            modalities.append("scanned_document")
        elif any(kw in desc_lower for kw in ["ocr", "image", "photo", "picture"]):
            modalities.append("ocr")

        if any(kw in desc_lower for kw in ["python", "code", "calculate", "script", "compute"]):
            modalities.append("code")

        if any(kw in desc_lower for kw in ["sop", "manual", "handbook", "retrieve", "knowledge"]):
            modalities.append("rag")

        return list(dict.fromkeys(modalities))

    def determine_required_outputs(self, description: str) -> str | None:
        """
        Phase 7 (M1): detects whether the user is asking for a downloadable
        deliverable file, and if so, which artifact type to produce.
        Returns one of 'docx', 'xlsx', 'pdf', 'csv', 'json', or None.
        """
        desc_lower = description.lower()
        if any(kw in desc_lower for kw in ["excel", "spreadsheet", "xlsx"]):
            return "xlsx"
        if "csv" in desc_lower:
            return "csv"
        if "pdf" in desc_lower:
            return "pdf"
        if any(kw in desc_lower for kw in ["json file", "json output", "export as json", "export to json"]):
            return "json"
        if any(kw in desc_lower for kw in [
            "docx", "word document", "draft a report", "generate a report", "write a report",
            "draft an approval note", "generate a document", "create a document", "downloadable",
            "generate a docx", "export as a document",
        ]):
            return "docx"
        return None

    def _build_artifact_step_params(self, output_type: str, description: str) -> tuple[str, dict]:
        """Best-effort artifact tool + params when auto-appending a deliverable
        step the LLM's own plan omitted. Tabular formats (xlsx/csv) start with
        empty headers/rows here — a real LLM-authored plan step supplies those
        directly from the task's data; this is only the safety-net fallback."""
        title = (description.strip()[:80] or "Report")
        if output_type == "xlsx":
            return "generate_xlsx", {"title": title, "headers": [], "rows": []}
        if output_type == "csv":
            return "generate_csv", {"title": title, "headers": [], "rows": []}
        if output_type == "pdf":
            return "generate_pdf", {"title": title}
        if output_type == "json":
            return "generate_json", {"title": title, "data": {}}
        return "generate_docx", {"title": title}

    def classify_task(self, description: str, file_attachments: list[str] | None = None) -> str:
        """
        Returns the primary task category: 'CODING', 'VISION', 'RAG', or 'REASONING'.
        """
        modalities = self.detect_required_modalities(description, file_attachments=file_attachments)
        if "engineering_drawing" in modalities or "scanned_document" in modalities or "ocr" in modalities or "vision" in modalities:
            return "VISION"
        if "code" in modalities:
            return "CODING"
        if "rag" in modalities:
            return "RAG"
        return "REASONING"

    def _generate_fallback_plan(self, description: str, file_attachments: list[str] | None = None) -> list[PlanStep]:
        """
        Intelligent multi-step fallback plan when LLM is unavailable.
        Respects multimodal anti-hallucination dependencies.
        """
        modalities = self.detect_required_modalities(description, file_attachments=file_attachments)

        if "engineering_drawing" in modalities:
            return [
                PlanStep(
                    step_id="step_1",
                    action="Analyze engineering drawing / P&ID for component tags, instruments, and connections",
                    tool="analyze_engineering_drawing",
                    depends_on=[],
                    params={"prompt": description, "image_path": file_attachments[0] if file_attachments else None},
                ),
                PlanStep(
                    step_id="step_2",
                    action="Synthesize engineering findings with confidence grounding",
                    tool="direct_llm",
                    depends_on=["step_1"],
                    params={"prompt": f"Based on the engineering drawing extraction, address the user request: {description}"},
                )
            ]
        elif "pdf" in modalities:
            return [
                PlanStep(
                    step_id="step_1",
                    action="Read text from attached PDF document",
                    tool="read_file",
                    depends_on=[],
                    params={"prompt": description, "path": file_attachments[0] if file_attachments else None},
                ),
                PlanStep(
                    step_id="step_2",
                    action="Analyze extracted PDF text",
                    tool="direct_llm",
                    depends_on=["step_1"],
                    params={"prompt": f"Based on the PDF text, address the user request: {description}"},
                )
            ]
        elif "scanned_document" in modalities or "ocr" in modalities:
            return [
                PlanStep(
                    step_id="step_1",
                    action="Extract structured text and key-value fields from scanned document",
                    tool="analyze_scanned_document",
                    depends_on=[],
                    params={"prompt": description, "image_path": file_attachments[0] if file_attachments else None},
                ),
                PlanStep(
                    step_id="step_2",
                    action="Summarize report findings and verify extracted claims",
                    tool="direct_llm",
                    depends_on=["step_1"],
                    params={"prompt": f"Based on the scanned document extraction, address the user request: {description}"},
                )
            ]
        elif "code" in modalities:
            return [
                PlanStep(
                    step_id="step_1",
                    action="Execute Python computation or script",
                    tool="execute_python",
                    depends_on=[],
                    params={"action": description},
                ),
                PlanStep(
                    step_id="step_2",
                    action="Format final result and explanation",
                    tool="direct_llm",
                    depends_on=["step_1"],
                    params={"prompt": f"Explain the execution results for: {description}"},
                )
            ]

        elif "rag" in modalities:
            return [
                PlanStep(
                    step_id="step_1",
                    action="Search SOPs and manuals for relevant information",
                    tool="rag_search",
                    depends_on=[],
                    params={"query": description},
                ),
                PlanStep(
                    step_id="step_2",
                    action="Formulate final answer using citations",
                    tool="direct_llm",
                    depends_on=["step_1"],
                    params={"prompt": f"Based on the retrieved RAG documents, address the user request: {description}"},
                )
            ]

        # Standard reasoning single-step
        return [
            PlanStep(
                step_id="step_1",
                action=description,
                tool="direct_llm",
                depends_on=[],
                params={"prompt": description},
            )
        ]

    def generate_plan(self, task_id: str, description: str, file_attachments: list[str] | None = None) -> ExecutionPlan:
        """
        Phase 3/5: call reasoning model to produce a structured step plan DAG.
        Falls back to intelligent rule-based multi-step plan if model is unavailable.
        """
        from models.registry import registry

        attachment_ctx = f"\n\nAttached files for reference: {', '.join(file_attachments)}\n" if file_attachments else ""
        prompt = f"{_PLAN_SYSTEM_PROMPT}{attachment_ctx}\n\nUser task:\n{description}"
        model_id = registry.route_task(description)

        try:
            response_text, _ = registry.execute_prompt(model_id, prompt)
            cleaned = response_text.strip()
            if cleaned.startswith("```"):
                cleaned = "\n".join(cleaned.split("\n")[1:])
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3].strip()

            plan_data = json.loads(cleaned)
            steps = [
                PlanStep(
                    step_id=s.get("step_id", f"step_{i+1}"),
                    action=s.get("action", ""),
                    tool=s.get("tool"),
                    depends_on=s.get("depends_on", []),
                    params=s.get("params", {}),
                )
                for i, s in enumerate(plan_data.get("steps", []))
            ]
            if not steps:
                raise ValueError("Empty steps list from model")

            # Anti-hallucination tool validation: ensure vision tools are only assigned when visual modality is detected
            detected_modalities = self.detect_required_modalities(description, file_attachments=file_attachments)
            has_vision = any(m in detected_modalities for m in ["scanned_document", "engineering_drawing", "ocr", "vision"])
            is_pdf = "pdf" in detected_modalities
            for s in steps:
                if s.tool in ["run_ocr", "analyze_scanned_document", "analyze_engineering_drawing"]:
                    if is_pdf:
                        s.tool = "read_file"
                    elif not has_vision:
                        s.tool = "direct_llm"
        except Exception as exc:
            logger.info("Plan generation using intelligent fallback (%s)", exc)
            steps = self._generate_fallback_plan(description, file_attachments=file_attachments)

        # Auto-Injection Safeguard
        if file_attachments:
            for s in steps:
                if s.tool in ["run_ocr", "analyze_scanned_document", "analyze_engineering_drawing"]:
                    if "image_path" not in s.params:
                        s.params["image_path"] = file_attachments[0]
                elif s.tool == "read_file":
                    if "path" not in s.params:
                        s.params["path"] = file_attachments[0]
            if "pdf" in self.detect_required_modalities(description, file_attachments=file_attachments) and not any(s.tool == "read_file" for s in steps):
                steps.insert(0, PlanStep(
                    step_id="step_0_pdf",
                    action="Read attached PDF document",
                    tool="read_file",
                    depends_on=[],
                    params={"path": file_attachments[0]}
                ))
                for s in steps[1:]:
                    if not s.depends_on:
                        s.depends_on.append("step_0_pdf")

        # Phase 7 Deliverable Safeguard: if the user asked for a downloadable
        # artifact but the plan (LLM or fallback) didn't end with a generate_*
        # step, append one depending on every existing step so its content
        # falls back to the accumulated context (see Executor.execute_step).
        from tools.registry import ARTIFACT_TOOL_NAMES

        required_output = self.determine_required_outputs(description)
        if required_output and not any(s.tool in ARTIFACT_TOOL_NAMES for s in steps):
            tool_name, params = self._build_artifact_step_params(required_output, description)
            steps.append(PlanStep(
                step_id=f"step_{len(steps) + 1}",
                action=f"Generate downloadable {required_output.upper()} artifact",
                tool=tool_name,
                depends_on=[s.step_id for s in steps],
                params=params,
            ))

        return ExecutionPlan(task_id=task_id, steps=steps)

    def replan(
        self,
        task_id: str,
        description: str,
        failure_reason: str,
        file_attachments: list[str] | None = None,
    ) -> ExecutionPlan:
        """
        Phase 8 (M1): regenerate a plan after a validation failure (low grounding
        score, unsupported claims, a failed calculation re-check, or a rejected
        artifact), injecting the specific failure as a corrective instruction so
        the model addresses it directly instead of repeating the same mistake.
        Reuses generate_plan() end-to-end — no duplicated planning logic.
        """
        corrective_note = (
            "\n\nIMPORTANT: a previous attempt at this task FAILED validation for this reason:\n"
            f"{failure_reason}\n"
            "Correct this specific issue in your new plan — e.g. re-verify claims against retrieved "
            "sources with rag_search, re-run/fix the calculation, or regenerate the artifact — before "
            "producing your answer again."
        )
        logger.info("Replanning task %s due to: %s", task_id, failure_reason)
        return self.generate_plan(task_id, f"{description}{corrective_note}", file_attachments=file_attachments)

    def decompose_task(self, description: str) -> list[str]:
        """
        Breaks a task into a list of sub-task descriptions.
        """
        from models.registry import registry
        model_id = registry.route_task(description)
        prompt = (
            f"Break the following task into 2-5 concise sub-tasks. "
            f"Output them as a JSON list of strings.\nTask: {description}"
        )
        try:
            response_text, _ = registry.execute_prompt(model_id, prompt)
            cleaned = response_text.strip().strip("```json").strip("```")
            sub_tasks = json.loads(cleaned)
            if isinstance(sub_tasks, list) and sub_tasks:
                return sub_tasks
        except Exception as exc:
            logger.warning("decompose_task failed (%s). Returning original.", exc)
        return [description]

    def create_execution_graph(self, steps: list[PlanStep]) -> ExecutionPlan:
        """
        Topologically sorts steps into an executable DAG using Kahn's algorithm.
        """
        task_id = str(uuid.uuid4())
        step_map = {s.step_id: s for s in steps}
        in_degree = {s.step_id: 0 for s in steps}
        for step in steps:
            for dep in step.depends_on:
                if dep in in_degree:
                    in_degree[step.step_id] += 1

        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        sorted_steps: list[PlanStep] = []
        visited: set[str] = set()

        while queue:
            current_id = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)
            sorted_steps.append(step_map[current_id])
            for step in steps:
                if current_id in step.depends_on:
                    in_degree[step.step_id] -= 1
                    if in_degree[step.step_id] == 0:
                        queue.append(step.step_id)

        for step in steps:
            if step.step_id not in visited:
                sorted_steps.append(step)

        return ExecutionPlan(task_id=task_id, steps=sorted_steps)