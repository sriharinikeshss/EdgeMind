import uuid
from pydantic import BaseModel

class TaskRequest(BaseModel):
    prompt: str

class TaskResponse(BaseModel):
    task_id: str
    status: str
    response: str
    model_used: str

class ModelRegistryStub:
    def route_task(self, prompt: str) -> str:
        # Stub for model routing, currently defaults to a mock local model
        return "qwen2.5-72b-instruct-mock"

    def execute_prompt(self, model_id: str, prompt: str) -> str:
        # Stub for model execution. In reality this calls Ollama/vLLM.
        return f"This is a mocked local response from {model_id} for: '{prompt}'"

registry = ModelRegistryStub()
