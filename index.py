import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("AIAutomationServer")

# ---------------------------------------------------------------------------
# Pydantic Schemas (API Request / Response models)
# ---------------------------------------------------------------------------
class AutomationRequest(BaseModel):
    user_id: str = Field(..., example="usr_9021")
    user_feedback: str = Field(..., example="I love the new UI update! It makes automation so easy.")

class AIAnalysisResult(BaseModel):
    sentiment: str
    confidence: float
    summary: str

class WorkflowResponse(BaseModel):
    workflow_id: str
    status: str
    payload: Dict[str, Any]
    results: Dict[str, Any]
    errors: List[str]
    created_at: str

# ---------------------------------------------------------------------------
# Core Workflow State
# ---------------------------------------------------------------------------
class WorkflowContext:
    def __init__(self, payload: Dict[str, Any]):
        self.workflow_id: str = str(uuid4())
        self.payload: Dict[str, Any] = payload
        self.results: Dict[str, Any] = {}
        self.errors: List[str] = []
        self.status: str = "PENDING"
        self.created_at: str = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "status": self.status,
            "payload": self.payload,
            "results": self.results,
            "errors": self.errors,
            "created_at": self.created_at,
        }

# In-memory storage for workflow jobs
JOBS_DB: Dict[str, WorkflowContext] = {}

# ---------------------------------------------------------------------------
# Modular Workflow Steps
# ---------------------------------------------------------------------------
class BaseStep:
    def __init__(self, name: str):
        self.name = name

    async def execute(self, context: WorkflowContext) -> WorkflowContext:
        raise NotImplementedError

class IngestionStep(BaseStep):
    async def execute(self, context: WorkflowContext) -> WorkflowContext:
        logger.info(f"[{self.name}] Processing incoming API request payload...")
        await asyncio.sleep(0.2)
        return context

class SentimentAnalysisAIStep(BaseStep):
    async def _mock_llm_inference(self, text: str) -> Dict[str, Any]:
        await asyncio.sleep(1.0)  # Simulate AI model latency
        text_lower = text.lower()
        if any(w in text_lower for w in ["great", "love", "awesome", "good"]):
            sentiment, score = "positive", 0.94
        elif any(w in text_lower for w in ["issue", "bug", "broken", "hate"]):
            sentiment, score = "negative", 0.88
        else:
            sentiment, score = "neutral", 0.50

        return {
            "sentiment": sentiment,
            "confidence": score,
            "summary": text[:50] + "..." if len(text) > 50 else text
        }

    async def execute(self, context: WorkflowContext) -> WorkflowContext:
        logger.info(f"[{self.name}] Analyzing sentiment via AI...")
        input_text = context.payload.get("user_feedback", "")
        
        if not input_text:
            context.errors.append(f"{self.name}: Empty feedback string provided.")
            return context

        ai_output = await self._mock_llm_inference(input_text)
        context.results["ai_analysis"] = ai_output
        return context

class DecisionRoutingStep(BaseStep):
    async def execute(self, context: WorkflowContext) -> WorkflowContext:
        logger.info(f"[{self.name}] Routing actions based on sentiment...")
        ai_data = context.results.get("ai_analysis", {})
        sentiment = ai_data.get("sentiment", "neutral")

        if sentiment == "positive":
            context.results["routed_action"] = "Logged feedback to marketing showcase."
        elif sentiment == "negative":
            context.results["routed_action"] = "Escalated high-priority ticket to Zendesk/Support."
        else:
            context.results["routed_action"] = "Archived for standard review."

        return context

# ---------------------------------------------------------------------------
# Pipeline Engine
# ---------------------------------------------------------------------------
class AutomationEngine:
    def __init__(self):
        self.steps: List[BaseStep] = [
            IngestionStep("Ingestion"),
            SentimentAnalysisAIStep("AI Analysis"),
            DecisionRoutingStep("Action Router")
        ]

    async def run(self, context: WorkflowContext) -> WorkflowContext:
        context.status = "PROCESSING"
        for step in self.steps:
            try:
                context = await step.execute(context)
                if context.errors:
                    context.status = "FAILED"
                    return context
            except Exception as e:
                logger.exception(f"Error executing step {step.name}")
                context.errors.append(str(e))
                context.status = "FAILED"
                return context

        context.status = "COMPLETED"
        return context

engine = AutomationEngine()

# ---------------------------------------------------------------------------
# FastAPI Application & Endpoints
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AI Automation Server",
    description="Backend API server for async AI workflows and task automation.",
    version="2.0.0"
)

# Background Task Worker
async def run_workflow_task(job_id: str):
    context = JOBS_DB.get(job_id)
    if context:
        await engine.run(context)

@app.post("/api/v1/automation/run", response_model=WorkflowResponse)
async def run_sync_automation(request: AutomationRequest):
    """Executes the AI automation pipeline synchronously and returns results immediately."""
    context = WorkflowContext(payload=request.model_dump())
    JOBS_DB[context.workflow_id] = context
    await engine.run(context)
    return context.to_dict()

@app.post("/api/v1/automation/submit", status_code=202)
async def submit_async_automation(request: AutomationRequest, background_tasks: BackgroundTasks):
    """Submits the AI automation task asynchronously in the background."""
    context = WorkflowContext(payload=request.model_dump())
    JOBS_DB[context.workflow_id] = context
    background_tasks.add_task(run_workflow_task, context.workflow_id)
    return {
        "message": "Workflow submitted successfully",
        "workflow_id": context.workflow_id,
        "status": context.status
    }

@app.get("/api/v1/automation/status/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow_status(workflow_id: str):
    """Fetches status and results for a specific workflow ID."""
    context = JOBS_DB.get(workflow_id)
    if not context:
        raise HTTPException(status_code=404, detail="Workflow ID not found")
    return context.to_dict()

@app.websocket("/ws/automation")
async def websocket_automation(websocket: WebSocket):
    """Real-time WebSocket endpoint to submit tasks and stream execution status."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            context = WorkflowContext(payload=data)
            
            await websocket.send_json({"event": "STARTED", "workflow_id": context.workflow_id})
            await engine.run(context)
            await websocket.send_json({"event": "COMPLETED", "data": context.to_dict()})
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")

# ---------------------------------------------------------------------------
# Direct File Execution Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
