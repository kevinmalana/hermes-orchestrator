# LangGraph Orchestrator MVP

**Hermes as primary agent + LangGraph as orchestration engine. No OpenClaw.**

---

## What This Is

A lightweight orchestration layer that:
1. Receives tasks from Hermes gateway
2. Routes simple tasks to Hermes direct path
3. Routes complex tasks through a LangGraph workflow (planner → worker → critic → synthesize → send_result)
4. Uses Hermes as the worker for all deep execution (terminal, Docker, SSH, research, coding)

---

## Architecture

```
Hermes Gateway (18792) ────── simple ──────► Hermes direct answer
              │
              └─── complex ──► LangGraph Orchestrator (18793)
                                    │
                              planner → worker (Hermes) → critic → synthesize → send_result
```

See [docs/architecture.md](docs/architecture.md) for full details.

---

## Quick Start

### 1. Install dependencies

```bash
/root/venv/bin/pip install -r /orchestrator/requirements.txt
```

### 2. Configure

```bash
cp /orchestrator/.env.example /config/orchestrator.env
# Edit /config/orchestrator.env
```

### 3. Start

```bash
# Option A: systemd (recommended)
/root/venv/bin/python -m uvicorn orchestrator.api:app --host 127.0.0.1 --port 18793 &

# Option B: via script
bash /scripts/start_orchestrator.sh
```

### 4. Verify

```bash
curl http://127.0.0.1:18793/health
curl http://127.0.0.1:18793/health/graph
```

---

## API

### POST /v1/task
```json
{
  "message": "deploy quizworld to production",
  "session_id": "abc-123",
  "source": "telegram"
}
```

### GET /health
Returns `{status: "ok", workflow: "loaded|FAILED"}`

### GET /health/graph
Returns `{nodes: ["ingest", "classify", ...]}`

---

## Directories

| Path | Purpose |
|------|---------|
| `/orchestrator` | Python package (workflow, nodes, api) |
| `/config` | YAML config, env files |
| `/scripts` | Startup scripts |
| `/docs` | Architecture & runbook docs |

---

## Status

| Component | Status |
|-----------|--------|
| LangGraph workflow (6 nodes) | ✅ Built |
| FastAPI server on 18793 | ✅ Built |
| Hermes bridge integration (mock fallback) | ✅ Built |
| systemd unit | ✅ Built |
| Architecture docs | ✅ Built |
| End-to-end test | 🔲 Not verified |
| systemd install + verify | 🔲 Not verified |

---

## Environment Variables

See [`.env.example`](orchestrator/.env.example) for full list.

Key variables:
- `HERMES_BRIDGE_URL` — Hermes gateway address (default: `http://127.0.0.1:18792`)
- `ORCHESTRATOR_PORT` — orchestrator port (default: `18793`)
- `OPENAI_API_KEY` — for LLM-powered classifier/planner (optional)
- `WORKER_TIMEOUT_SECONDS` — Hermes worker timeout (default: 120)
- `MAX_RETRIES` — critic retry limit (default: 2)
