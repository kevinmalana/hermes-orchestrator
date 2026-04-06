# Hermes LangGraph Orchestrator

**Hermes as primary agent platform + LangGraph as orchestration engine. No OpenClaw.**

---

## Architecture

```
Telegram ──▶ Hermes Gateway (18792)
                    │
            simple? ──Yes──▶ Hermes direct answer
                    │
                   No
                    ▼
          LangGraph Orchestrator (18793)
                    │
          ingest → classify → planner
                    │              │
                  END         worker (Hermes)
                              critic → synthesize
                              send_result → Hermes → Telegram
```

**Ports:**
- 18792 — Hermes Gateway (messaging)
- 18793 — LangGraph Orchestrator (workflow engine + dashboard)

---

## Quick Start

```bash
# Install dependencies
/root/venv/bin/pip install -r /orchestrator/requirements.txt

# Start orchestrator
bash /scripts/start_orchestrator.sh

# Verify
curl http://127.0.0.1:18793/health
```

---

## Dashboard

Open in browser: `http://<vps-ip>:18793/`

Shows: node status, API endpoints, quick actions, test curl commands.

Auto-refreshes every 10 seconds.

---

## API

### POST /v1/task
```json
{"message": "deploy quizworld to production", "source": "telegram"}
```

### GET /health
Returns `{status: "ok", workflow: "loaded"}`

### GET /health/graph
Returns `{nodes: ["ingest", "classify", ...]}`

---

## LangGraph Studio UI

For visual graph debugging, use LangGraph CLI:

```bash
cd /orchestrator
PYTHONPATH=/orchestrator langgraph dev \
  --config /orchestrator/langgraph.json \
  --port 18794 \
  --no-browser
```

Then open: `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:18794`

---

## Status

| Component | Status |
|-----------|--------|
| LangGraph workflow (7 nodes) | ✅ |
| FastAPI dashboard on 18793 | ✅ |
| Hermes bridge integration (mock fallback) | ✅ |
| systemd unit | ✅ |
| Committed to GitHub | ✅ |
| Real Hermes endpoint integration | 🔲 fix endpoints |
| Docker build | 🔲 |

---

## Files

```
/orchestrator/
  orchestrator/           # Python package
    __init__.py
    workflow.py           # LangGraph graph
    state.py              # AgentState schema
    nodes.py              # 6 node implementations
    api.py                # FastAPI server
  requirements.txt
  langgraph.json          # LangGraph Studio config
  docker-compose.yml
  .env.example
  systemd/orchestrator.service
```
