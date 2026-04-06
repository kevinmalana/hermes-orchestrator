"""
LangGraph workflow — 6-node graph:
  ingest → classify → [END (direct) | planner → worker → critic → synthesize → send_result]
"""

from orchestrator.state import AgentState
from orchestrator.nodes import (
    node_ingest,
    node_classify,
    node_planner,
    node_worker,
    node_critic,
    node_synthesize,
    node_send_result,
)

from langgraph.graph import StateGraph, END

WORKFLOW_DESCRIPTION = """
┌─────────┐    ┌───────────┐    ┌────────────────┐
│ ingest  │───▶│ classify  │───▶│   END          │
└─────────┘    └───────────┘    │   (Hermes      │
     │              │            │   direct)      │
     │              ▼            └────────────────┘
     │        ┌──────────┐
     │        │ planner  │
     │        └────┬─────┘
     │             ▼
     │        ┌────────┐
     │        │ worker │◀─── retry loop
     │        └───┬────┘
     │            ▼
     │        ┌────────┐
     │        │ critic │─── needs_retry= true ──▶ worker
     │        └───┬────┘
     │            ▼
     │      ┌───────────┐
     │      │ synthesize│
     │      └─────┬─────┘
     │            ▼
     │      ┌────────────┐
     │      │ send_result│
     │      └────────────┘
"""


def _classify_route(state: AgentState) -> str:
    """Route after classify: simple → END, complex → planner."""
    return "planner" if state.low_confidence else END


def _critic_route(state: AgentState) -> str:
    """Route after critic: retry if needed (max 2), else synthesize."""
    if state.needs_retry and state.retry_count < 2:
        return "worker"
    return "synthesize"


def build_workflow() -> StateGraph:
    """Build and return the compiled LangGraph workflow."""
    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("ingest", node_ingest)
    builder.add_node("classify", node_classify)
    builder.add_node("planner", node_planner)
    builder.add_node("worker", node_worker)
    builder.add_node("critic", node_critic)
    builder.add_node("synthesize", node_synthesize)
    builder.add_node("send_result", node_send_result)

    # Entry
    builder.set_entry_point("ingest")

    # ingest → classify
    builder.add_edge("ingest", "classify")

    # classify routing: simple → END (Hermes direct), complex → planner
    builder.add_conditional_edges("classify", _classify_route)

    # planner → worker
    builder.add_edge("planner", "worker")

    # worker → critic
    builder.add_edge("worker", "critic")

    # critic loop: retry → worker (max 2), else → synthesize
    builder.add_conditional_edges("critic", _critic_route)

    # synthesize → send_result → END
    builder.add_edge("synthesize", "send_result")
    builder.add_edge("send_result", END)

    return builder.compile()
