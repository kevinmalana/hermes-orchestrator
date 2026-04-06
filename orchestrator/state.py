"""
AgentState — shared state schema for all LangGraph nodes.
Every node receives this and returns partial updates.
"""

from typing import Optional, Any
from pydantic import BaseModel, Field


class AgentState(BaseModel):
    # Identity
    task_id: str = ""
    session_id: Optional[str] = None

    # Ingestion
    raw_message: str = ""
    source: str = "telegram"  # telegram | api | cron | webhook

    # Classification
    intent: str = ""           # question | task | event | unknown
    complexity: str = ""       # simple | moderate | complex
    low_confidence: bool = False

    # Planning
    plan: dict = Field(default_factory=dict)  # {steps: [], estimated_time: "", tools_needed: []}
    plan_approved: bool = False

    # Worker output contract
    summary: str = ""
    findings: list = Field(default_factory=list)
    risks: list = Field(default_factory=list)
    artifacts: list = Field(default_factory=list)
    confidence: float = 0.0
    next_action: str = ""

    # Retry / critic loop
    needs_retry: bool = False
    retry_count: int = 0
    critique: str = ""

    # Synthesize
    final_response: str = ""

    # Result
    result_sent: bool = False
    error: Optional[str] = None

    class Config:
        extra = "allow"  # allow extra fields from Hermes
