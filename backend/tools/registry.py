"""
Tool Registry ΓÇö Phase 3 full implementation (M5).

Formalizes register_tool(), check_tool_permission(), execute_tool(),
log_tool_call() (writes to tool_calls table), and registers the first
two real tools: execute_python and rag_search.
"""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    risk_level: str = "LOW"          # LOW | MEDIUM | HIGH
    allowed_roles: list[str] = field(default_factory=lambda: ["admin", "operator"])
    sandbox_required: bool = False
    network_required: bool = False
    handler: Callable | None = None  # the actual Python callable


class ToolRegistry:
    """
    Central registry for all tools available to the Executor.

    Phase 3: register_tool, check_tool_permission, execute_tool, log_tool_call.
    Phase 4: full sandbox routing, validate_tool_arguments.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register_tool(self, tool: ToolDefinition) -> None:
        """Register a new tool. Raises ValueError if already registered."""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered.")
        self._tools[tool.name] = tool
        logger.info("Registered tool: %s (risk=%s)", tool.name, tool.risk_level)

    def list_tools(self) -> list[str]:
        """Return names of all registered tools."""
        return list(self._tools.keys())

    def get_tool(self, name: str) -> ToolDefinition:
        """Retrieve a tool by name. Raises KeyError if not found."""
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered.")
        return self._tools[name]

    def check_tool_permission(self, tool_name: str, user_role: str) -> bool:
        """
        Returns True if user_role is allowed to call tool_name.
        Phase 4 will wire to full RBAC engine (M6).
        """
        tool = self.get_tool(tool_name)
        return user_role in tool.allowed_roles

    def execute_tool(self, tool_name: str, user_role: str, arguments: dict[str, Any], db=None) -> Any:
        """
        Phase 3: Permission-check ΓåÆ invoke handler ΓåÆ log to DB.
        """
        if not self.check_tool_permission(tool_name, user_role):
            raise PermissionError(
                f"Role '{user_role}' is not allowed to call tool '{tool_name}'."
            )
        tool = self.get_tool(tool_name)
        if tool.handler is None:
            raise NotImplementedError(f"Tool '{tool_name}' has no handler registered yet.")

        try:
            result = tool.handler(**arguments)
            if db:
                self.log_tool_call(
                    db=db,
                    task_id=arguments.get("task_id", "unknown"),
                    tool_name=tool_name,
                    arguments=arguments,
                    result=result,
                    status="COMPLETED",
                )
            return result
        except Exception as exc:
            if db:
                self.log_tool_call(
                    db=db,
                    task_id=arguments.get("task_id", "unknown"),
                    tool_name=tool_name,
                    arguments=arguments,
                    result=None,
                    status="FAILED",
                )
            raise

    def log_tool_call(
        self,
        db,
        task_id: str,
        tool_name: str,
        arguments: dict,
        result: Any,
        status: str = "COMPLETED",
    ) -> None:
        """
        Phase 3 (M5): Write a tool call record to the tool_calls table.
        """
        try:
            from database.models import ToolCall
            record = ToolCall(
                task_id=task_id,
                tool_name=tool_name,
                arguments=json.dumps(arguments, default=str)[:2000],
                result=json.dumps({"output": str(result)[:2000]}),
                status=status,
            )
            db.add(record)
            db.commit()
        except Exception as exc:
            logger.warning("log_tool_call DB write failed: %s", exc)

    def validate_tool_arguments(self, tool_name: str, arguments: dict) -> bool:
        """
        Phase 4: validate arguments against the tool's input_schema.
        Phase 3 stub: always returns True.
        """
        tool = self.get_tool(tool_name)
        required = tool.input_schema.get("required", [])
        for key in required:
            if key not in arguments:
                logger.warning("Missing required argument '%s' for tool '%s'", key, tool_name)
                return False
        return True


# ΓöÇΓöÇ Module-level singleton ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
tool_registry = ToolRegistry()


# ΓöÇΓöÇ Register built-in Phase 3 tools ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

def _execute_python_handler(code: str = None, script: str = None, prompt: str = None, timeout_seconds: int = 10, **kwargs) -> dict:
    c = code or script
    if not c:
        p = prompt or kwargs.get("action") or "Write a python script."
        # Auto-generate the code using the coding model
        from models.registry import registry, OLLAMA_CODING_MODEL
        model_id = OLLAMA_CODING_MODEL
        sys_prompt = "You are a Python expert. Output ONLY valid Python code inside a ```python block. Do not include explanations. Ensure the code prints its final output so it can be captured."
        full_prompt = f"{sys_prompt}\n\nTask: {p}"
        output, _ = registry.execute_prompt(model_id, full_prompt)
        
        # Extract python code from markdown block
        import re
        match = re.search(r"```python\s*(.*?)\s*```", output, re.DOTALL | re.IGNORECASE)
        if match:
            c = match.group(1)
        else:
            c = output.replace("```", "").strip()

    from sandbox.manager import sandbox_manager
    res = sandbox_manager.execute_python(c, timeout_seconds=timeout_seconds)
    # If Python executed successfully but produced empty output (no print statements), generate a textual response
    if res.get("exit_code") == 0 and not (res.get("stdout") or "").strip() and not (res.get("stderr") or "").strip():
        res["stdout"] = "<Execution finished with no output. Did you forget to print() your result?>"
    return res


def _rag_search_handler(query: str = None, prompt: str = None, top_k: int = 5, collection: str = "kavach_docs", **kwargs) -> list[dict]:
    q = query or prompt or kwargs.get("text") or ""
    from api.rag import _get_query_embedding, _search_qdrant
    vec = _get_query_embedding(q)
    return _search_qdrant(vec, collection, top_k)


def _direct_llm_handler(prompt: str = None, query: str = None, **kwargs) -> str:
    p = prompt or query or ""
    from models.registry import registry
    model_id = registry.route_task(p)
    output, _ = registry.execute_prompt(model_id, p)
    return output


tool_registry.register_tool(ToolDefinition(
    name="execute_python",
    description="Execute Python code in a subprocess sandbox.",
    input_schema={"type": "object", "properties": {"code": {"type": "string"}, "script": {"type": "string"}, "prompt": {"type": "string"}}},
    output_schema={"type": "object"},
    risk_level="HIGH",
    allowed_roles=["admin", "operator"],
    sandbox_required=True,
    network_required=False,
    handler=_execute_python_handler,
))

tool_registry.register_tool(ToolDefinition(
    name="rag_search",
    description="Retrieve relevant document chunks from Qdrant using semantic search.",
    input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    output_schema={"type": "array"},
    risk_level="LOW",
    allowed_roles=["admin", "operator", "viewer"],
    sandbox_required=False,
    network_required=False,
    handler=_rag_search_handler,
))

tool_registry.register_tool(ToolDefinition(
    name="direct_llm",
    description="Call the routing LLM directly with a prompt.",
    input_schema={"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]},
    output_schema={"type": "string"},
    risk_level="LOW",
    allowed_roles=["admin", "operator", "viewer"],
    sandbox_required=False,
    network_required=False,
    handler=_direct_llm_handler,
))


# ── Register Phase 4 Tools ────────────────────────────────────────────────────

def _read_file_handler(path: str, **kwargs) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return str(e)

def _write_file_handler(path: str, content: str, **kwargs) -> str:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"File written to {path}"
    except Exception as e:
        return str(e)

def _calculator_handler(expression: str, **kwargs) -> float:
    import ast
    import operator
    allowed_ops = {
        ast.Add: operator.add, ast.Sub: operator.sub,
        ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.BitXor: operator.xor,
        ast.USub: operator.neg
    }
    def eval_node(node):
        if isinstance(node, ast.Constant):
            return node.n
        elif isinstance(node, ast.BinOp):
            return allowed_ops[type(node.op)](eval_node(node.left), eval_node(node.right))
        elif isinstance(node, ast.UnaryOp):
            return allowed_ops[type(node.op)](eval_node(node.operand))
        else:
            raise TypeError('Unsupported math expression')
    try:
        return eval_node(ast.parse(expression, mode='eval').body)
    except Exception:
        return float('nan')

def _query_db_handler(query: str, **kwargs) -> str:
    return f"Stub DB result for {query}"

tool_registry.register_tool(ToolDefinition(
    name="read_file",
    description="Read contents of a file.",
    input_schema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    output_schema={"type": "string"},
    risk_level="LOW",
    allowed_roles=["admin", "operator", "viewer"],
    sandbox_required=False,
    network_required=False,
    handler=_read_file_handler
))

tool_registry.register_tool(ToolDefinition(
    name="write_file",
    description="Write content to a file.",
    input_schema={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
    output_schema={"type": "string"},
    risk_level="HIGH",
    allowed_roles=["admin", "operator"],
    sandbox_required=False,
    network_required=False,
    handler=_write_file_handler
))

tool_registry.register_tool(ToolDefinition(
    name="calculator",
    description="Evaluate a math expression safely.",
    input_schema={"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]},
    output_schema={"type": "number"},
    risk_level="LOW",
    allowed_roles=["admin", "operator", "viewer"],
    sandbox_required=False,
    network_required=False,
    handler=_calculator_handler
))

tool_registry.register_tool(ToolDefinition(
    name="query_db",
    description="Stub database query tool.",
    input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    output_schema={"type": "string"},
    risk_level="HIGH",
    allowed_roles=["admin", "operator"],
    sandbox_required=False,
    network_required=True,
    handler=_query_db_handler
))


# ── Register Phase 5 Multimodal / Vision Tools ───────────────────────────────

def _run_ocr_handler(image_bytes: bytes = None, image_path: str = None, **kwargs) -> dict:
    from ocr.processor import run_ocr
    from ocr.preprocess import preprocess_image
    if image_path:
        res = preprocess_image(image_path)
        if res.get("status") == "ok":
            image_bytes = res.get("image_bytes")
    if not image_bytes:
        return {"status": "error", "message": "No image_bytes or image_path provided."}
    return run_ocr(image_bytes)


def _analyze_scanned_document_handler(image_bytes: bytes = None, image_path: str = None, **kwargs) -> dict:
    from vision.multimodal_processor import analyze_scanned_document
    target = image_bytes or image_path
    if not target:
        return {"status": "error", "message": "No image provided for document analysis."}
    return analyze_scanned_document(target)


def _analyze_engineering_drawing_handler(image_bytes: bytes = None, image_path: str = None, **kwargs) -> dict:
    from vision.multimodal_processor import analyze_engineering_drawing
    target = image_bytes or image_path
    if not target:
        return {"status": "error", "message": "No image provided for engineering drawing analysis."}
    return analyze_engineering_drawing(target)


def _generate_visual_evidence_handler(image_bytes: bytes = None, image_path: str = None, bbox: dict = None, label: str = "", **kwargs) -> dict:
    from vision.multimodal_processor import generate_visual_evidence
    target = image_bytes or image_path
    if not target or not bbox:
        return {"status": "error", "message": "image and bbox are required to generate visual evidence."}
    return generate_visual_evidence(target, bbox, label=label)


tool_registry.register_tool(ToolDefinition(
    name="run_ocr",
    description="Run OCR text and word-level bounding box extraction on an image.",
    input_schema={"type": "object", "properties": {"image_path": {"type": "string"}}},
    output_schema={"type": "object"},
    risk_level="LOW",
    allowed_roles=["admin", "operator", "viewer"],
    sandbox_required=False,
    network_required=False,
    handler=_run_ocr_handler,
))

tool_registry.register_tool(ToolDefinition(
    name="analyze_scanned_document",
    description="Extract structured key-values, sections, and low-confidence anti-hallucination flags from a scanned document.",
    input_schema={"type": "object", "properties": {"image_path": {"type": "string"}}},
    output_schema={"type": "object"},
    risk_level="LOW",
    allowed_roles=["admin", "operator", "viewer"],
    sandbox_required=False,
    network_required=False,
    handler=_analyze_scanned_document_handler,
))

tool_registry.register_tool(ToolDefinition(
    name="analyze_engineering_drawing",
    description="Extract equipment tags, instruments, valves, annotations, and schematics from P&ID diagrams.",
    input_schema={"type": "object", "properties": {"image_path": {"type": "string"}}},
    output_schema={"type": "object"},
    risk_level="LOW",
    allowed_roles=["admin", "operator", "viewer"],
    sandbox_required=False,
    network_required=False,
    handler=_analyze_engineering_drawing_handler,
))

tool_registry.register_tool(ToolDefinition(
    name="generate_visual_evidence",
    description="Crop and generate a base64 visual evidence snippet for grounding verification.",
    input_schema={"type": "object", "properties": {"bbox": {"type": "object"}}, "required": ["bbox"]},
    output_schema={"type": "object"},
    risk_level="LOW",
    allowed_roles=["admin", "operator", "viewer"],
    sandbox_required=False,
    network_required=False,
    handler=_generate_visual_evidence_handler,
))

