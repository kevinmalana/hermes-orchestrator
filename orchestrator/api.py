"""
FastAPI app — orchestration server on port 18793.
Hermes gateway remains on 18792.
LangGraph workflow is invoked here.
"""

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from uvicorn import Config, Server

from .workflow import build_workflow
from .state import AgentState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("orchestrator.api")

# Compile workflow once at startup
try:
    app_workflow = build_workflow()
    log.info("LangGraph workflow compiled OK")
except Exception as e:
    log.error(f"Workflow compile failed: {e}")
    app_workflow = None

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TaskRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    source: str = "api"
    task_id: Optional[str] = None


class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


class ResultRequest(BaseModel):
    task_id: str
    response: str
    confidence: float = 1.0


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Orchestrator starting — port 18793")
    yield
    log.info("Orchestrator shutting down")


app = FastAPI(title="LangGraph Orchestrator", lifespan=lifespan)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "workflow": "loaded" if app_workflow else "FAILED",
    }


@app.get("/health/graph")
async def graph_health():
    if app_workflow is None:
        raise HTTPException(503, "workflow not loaded")
    return {
        "status": "ok",
        "nodes": list(app_workflow.nodes.keys()),
    }


@app.post("/v1/task", response_model=TaskResponse)
async def create_task(req: TaskRequest):
    if app_workflow is None:
        raise HTTPException(503, "workflow not loaded")

    task_id = req.task_id or str(uuid.uuid4())

    initial_state = AgentState(
        task_id=task_id,
        session_id=req.session_id,
        raw_message=req.message,
        source=req.source,
    )

    def run_graph():
        try:
            result = app_workflow.invoke(dict(initial_state))
            log.info(f"[graph] task_id={task_id} confidence={result.get('confidence', 0)}")
            return result
        except Exception as e:
            log.error(f"[graph] task_id={task_id} error: {e}")
            return {"error": str(e)}

    # Run in thread pool to avoid blocking
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, run_graph)

    return TaskResponse(
        task_id=task_id,
        status="queued",
        message="Task accepted and queued for processing",
    )


@app.post("/v1/result")
async def receive_result(req: ResultRequest):
    log.info(f"[result] task_id={req.task_id} confidence={req.confidence}")
    return {"status": "received", "task_id": req.task_id}


@app.get("/v1/task/{task_id}")
async def get_task(task_id: str):
    return {"task_id": task_id, "status": "processing"}


# ---------------------------------------------------------------------------
# Dashboard UI
# ---------------------------------------------------------------------------

DASHBOARD_HTML = Path("/tmp/dashboard.html").read_text()

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_full():
    return DASHBOARD_HTML


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_server():
    config = Config(
        app="orchestrator.orchestrator.api:app",
        host="127.0.0.1",
        port=18793,
        log_level="info",
        access_log=False,
    )
    server = Server(config)
    server.run()


if __name__ == "__main__":
    run_server()
