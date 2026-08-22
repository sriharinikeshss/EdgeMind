import uuid
from fastapi import APIRouter
from models.registry import registry, TaskRequest, TaskResponse
# In real application, we would use a DB session here to save to backend/database/models.py

router = APIRouter()

@router.post("/tasks", response_model=TaskResponse)
def create_task(req: TaskRequest):
    task_id = str(uuid.uuid4())
    
    # 1. Store task in DB with status CREATED (Mocked)
    
    # 2. Call local model (No router yet, just direct call)
    model_id = registry.route_task(req.prompt)
    model_response = registry.execute_prompt(model_id, req.prompt)
    
    # 3. Update task in DB with status COMPLETED (Mocked)
    
    return TaskResponse(
        task_id=task_id,
        status="COMPLETED",
        response=model_response,
        model_used=model_id
    )
