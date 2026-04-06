"""
LangGraph nodes — each is a pure function: (state) -> dict updates.
Worker node calls Hermes; all others are synchronous logic.
"""

import json
import logging
import time
import uuid
from typing import Literal

from .state import AgentState

log = logging.getLogger("orchestrator.nodes")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hermes_call(payload: dict, timeout: int = 60) -> dict:
    """
    Call the Hermes bridge/local API.
    Returns parsed JSON response.
    Falls back to mock on connection failure.
    """
    import urllib.request
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:18792/v1/task",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log.warning(f"Hermes call failed ({e}), returning mock response")
        return {
            "summary": f"Mock: processed '{payload.get('message', '')[:80]}'",
            "findings": [],
            "risks": [],
            "artifacts": [],
            "confidence": 0.5,
            "next_action": "review",
        }


# ---------------------------------------------------------------------------
# Node: ingest
# ---------------------------------------------------------------------------

def node_ingest(state: AgentState) -> dict:
    """Parse and normalise the inbound message."""
    log.info(f"[ingest] task_id={state.task_id} source={state.source}")
    raw = state.raw_message.strip()
    if not raw:
        return {"error": "empty message"}
    return {
        "raw_message": raw,
        "task_id": state.task_id or str(uuid.uuid4()),
    }


# ---------------------------------------------------------------------------
# Node: classify
# ---------------------------------------------------------------------------

def node_classify(state: AgentState) -> dict:
    """
    Fast rule-based classifier.
    In production this could call a lightweight LLM; for MVP uses keywords.
    """
    msg = state.raw_message.lower()

    # Intent detection
    if any(k in msg for k in ["?", "what", "how", "why", "when", "where", "which"]):
        intent = "question"
    elif any(k in msg for k in ["build", "deploy", "create", "fix", "update", "run", "do"]):
        intent = "task"
    elif any(k in msg for k in ["alert", "notify", "trigger", "webhook", "event"]):
        intent = "event"
    else:
        intent = "unknown"

    # Complexity
    if any(k in msg for k in ["build", "deploy", "architect", "migrate", "create system"]):
        complexity = "complex"
    elif any(k in msg for k in ["fix", "debug", "analyse", "review", "analyze"]):
        complexity = "moderate"
    else:
        complexity = "simple"

    # Low-confidence flag → routes to LangGraph deep path
    low_confidence = intent == "unknown" or complexity == "complex"

    log.info(f"[classify] intent={intent} complexity={complexity} low_confidence={low_confidence}")
    return {
        "intent": intent,
        "complexity": complexity,
        "low_confidence": low_confidence,
    }


# ---------------------------------------------------------------------------
# Node: planner
# ---------------------------------------------------------------------------

def node_planner(state: AgentState) -> dict:
    """
    Build an execution plan from the message.
    Returns a dict with steps, estimated_time, tools_needed.
    """
    msg = state.raw_message
    steps = []

    # Very simple step planner — in production would call an LLM
    if "deploy" in msg.lower():
        steps = [
            {"step": 1, "action": "inspect", "description": "Inspect current repo state"},
            {"step": 2, "action": "build", "description": "Run build/compile"},
            {"step": 3, "action": "deploy", "description": "Deploy to target environment"},
        ]
        est_time = "10-15 min"
        tools = ["terminal", "docker"]
    elif "code" in msg.lower() or "build" in msg.lower():
        steps = [
            {"step": 1, "action": "research", "description": "Understand requirements"},
            {"step": 2, "action": "implement", "description": "Write/modify code"},
            {"step": 3, "action": "test", "description": "Run tests"},
        ]
        est_time = "5-20 min"
        tools = ["terminal", "editor"]
    elif "research" in msg.lower() or "find" in msg.lower():
        steps = [
            {"step": 1, "action": "search", "description": "Search and gather info"},
            {"step": 2, "action": "synthesise", "description": "Synthesise findings"},
        ]
        est_time = "2-5 min"
        tools = ["web"]
    else:
        steps = [
            {"step": 1, "action": "analyze", "description": "Analyse request"},
            {"step": 2, "action": "execute", "description": "Execute appropriate action"},
        ]
        est_time = "1-10 min"
        tools = ["terminal"]

    plan = {
        "steps": steps,
        "estimated_time": est_time,
        "tools_needed": tools,
    }
    log.info(f"[planner] plan={json.dumps(plan)}")
    return {"plan": plan, "plan_approved": True}


# ---------------------------------------------------------------------------
# Node: worker
# ---------------------------------------------------------------------------

def node_worker(state: AgentState) -> dict:
    """
    Calls Hermes to do deep work.
    Constructs a task payload and POSTs to the Hermes bridge.
    Maps the response into the worker output contract.
    """
    log.info(f"[worker] task_id={state.task_id} retry={state.retry_count}")

    payload = {
        "task_id": state.task_id,
        "message": state.raw_message,
        "plan": state.plan,
        "source": state.source,
    }

    start = time.time()
    result = _hermes_call(payload, timeout=120)
    elapsed = time.time() - start

    log.info(f"[worker] completed in {elapsed:.1f}s confidence={result.get('confidence', 0)}")

    return {
        "summary": result.get("summary", ""),
        "findings": result.get("findings", []),
        "risks": result.get("risks", []),
        "artifacts": result.get("artifacts", []),
        "confidence": result.get("confidence", 0.5),
        "next_action": result.get("next_action", ""),
    }


# ---------------------------------------------------------------------------
# Node: critic
# ---------------------------------------------------------------------------

def node_critic(state: AgentState) -> dict:
    """
    Review worker output.
    Flags for retry if confidence is low or risks are high.
    """
    confidence = state.confidence
    risks = state.risks
    findings = state.findings

    needs_retry = confidence < 0.6 or len(risks) > 2
    critique = ""

    if confidence < 0.6:
        critique += f"Low confidence ({confidence:.2f}). "
    if len(risks) > 2:
        critique += f"High risk count ({len(risks)}). "
    if not findings:
        critique += "No findings returned. "

    retry_count = state.retry_count + (1 if needs_retry else 0)

    log.info(f"[critic] confidence={confidence} risks={len(risks)} needs_retry={needs_retry}")
    return {
        "needs_retry": needs_retry,
        "critique": critique,
        "retry_count": retry_count,
    }


# ---------------------------------------------------------------------------
# Node: synthesize
# ---------------------------------------------------------------------------

def node_synthesize(state: AgentState) -> dict:
    """
    Build the final natural-language response from worker output.
    """
    parts = []
    if state.summary:
        parts.append(state.summary)
    if state.findings:
        parts.append("\nFindings:")
        for f in state.findings:
            parts.append(f"  • {f}")
    if state.risks:
        parts.append("\nRisks:")
        for r in state.risks:
            parts.append(f"  ⚠ {r}")
    if state.artifacts:
        parts.append(f"\nArtifacts: {', '.join(state.artifacts)}")

    final = "\n".join(parts) if parts else state.summary or "Done."
    log.info(f"[synthesize] final_response length={len(final)}")
    return {"final_response": final}


# ---------------------------------------------------------------------------
# Node: send_result
# ---------------------------------------------------------------------------

def node_send_result(state: AgentState) -> dict:
    """
    POST the final response back to Hermes for delivery.
    """
    log.info(f"[send_result] task_id={state.task_id}")
    try:
        import urllib.request
        payload = {
            "task_id": state.task_id,
            "response": state.final_response,
            "confidence": state.confidence,
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:18792/v1/result",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            log.info(f"[send_result] Hermes ack: {resp.status}")
    except Exception as e:
        log.warning(f"[send_result] Hermes delivery failed: {e} — response logged only")

    return {"result_sent": True}
