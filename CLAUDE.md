# CLAUDE.md — EdgeMind KAVACH Developer Context

> **Read this file first before touching any code.**
> This file gives Claude Code the full picture of what this project is, how it is structured, what has been built, and the hard rules to follow. Treat every instruction here as a strict contract.

---

## 1. Project Identity & Goal

**Project Name:** EdgeMind KAVACH
**What it is:** A sovereign, on-premise agentic AI workbench. A multi-agent system that can reason over documents, run tools, generate artifacts (DOCX/XLSX), and perform complex multi-step workflows — all without any external internet calls.

**The single most important constraint:**
> ⚠️ **ZERO external network calls. EVER. Everything runs locally.**
> No OpenAI API. No Anthropic API. No AWS. No GCP. No Hugging Face Inference API. No cloud OCR. Nothing leaves the machine. If you suggest anything that touches the internet for AI inference or data, you are wrong.

**Master Plan File:** [`phase-by-phase-implementation-plan.md`](./phase-by-phase-implementation-plan.md)
Read this file to understand the full 11-phase roadmap, team ownership (M1–M6), integration points, and Definitions of Done.

**Architecture Plan File:** [`sovereign-agentic-workbench-plan.md`](./sovereign-agentic-workbench-plan.md)

---

## 2. Tech Stack

### Backend
| Layer | Technology |
|-------|-----------|
| API Framework | FastAPI 0.103.1 |
| ORM | SQLAlchemy 2.0.20 |
| Database | PostgreSQL 15 |
| Migrations | Alembic 1.12.0 |
| Auth | JWT via `python-jose`, password hashing via `passlib[bcrypt]==1.7.4` + `bcrypt==4.0.1` (pinned — do not upgrade, causes hash bug) |
| HTTP Client | `httpx` |
| Runtime | Python 3.11 (inside Docker), Python 3.10 (local dev) |

### Frontend
| Layer | Technology |
|-------|-----------|
| Framework | React 19 + TypeScript |
| Build Tool | Vite 8 |
| Linter | oxlint |
| Auth Context | `src/context/AuthContext.tsx` |

### Infrastructure (Docker Compose — 6 containers)
| Container | Image | Port | Purpose |
|-----------|-------|------|---------|
| `postgres` | postgres:15 | 5432 | Relational data store |
| `qdrant` | qdrant/qdrant:latest | 6333 | Vector DB for RAG |
| `minio` | minio/minio:latest | 9000/9001 | S3-compatible artifact/document storage |
| `ollama` | ollama/ollama:latest | 11434 | Local LLM inference server |
| `backend` | edgemind-backend (built from `./backend/Dockerfile`) | 8000 | FastAPI server |
| `frontend` | edgemind-frontend (built from `./frontend/Dockerfile`) | 5173 | React UI |

### AI Models (Ollama — local only)
| Model Tag | Type | VRAM | Purpose |
|-----------|------|------|---------|
| `qwen2.5:1.5b` | Reasoning | ~2 GB | General reasoning, summarization, Q&A |
| `qwen2.5-coder:1.5b` | Coding | ~2 GB | Code generation, debugging, scripts |

**To pull models (first time only):**
```bash
docker-compose exec ollama ollama pull qwen2.5:1.5b
docker-compose exec ollama ollama pull qwen2.5-coder:1.5b
```

---

## 3. Phase Implementation Status

| Phase | Name | Status |
|-------|------|--------|
| Phase 0 | Foundation & Scaffolding | ✅ Done |
| Phase 1 | Basic Local LLM Chat | ✅ Done |
| Phase 2 | Model Registry & Router | ✅ Done |
| Phase 3 | Agent Core (Planner → Executor → Validator Loop) | ✅ Done |
| Phase 4 | Tool Layer (Real Tools, Sandboxed) | 🟡 Partial |
| Phase 5 | Multimodal Pipeline (OCR + Vision) | 🟡 Partial |
| Phase 6 | RAG Integration | 🟡 Partial |
| Phase 7 | Artifact Generation (DOCX/XLSX/PDF) | 🔲 Pending |
| Phase 8 | Validation Engine | 🔲 Pending |
| Phase 9 | Security & Sovereignty Hardening | 🔲 Pending |
| Phase 10 | Integration, Polish & Demo Rehearsal | 🔲 Pending |

**What is done in each completed phase:**
- **Phase 0:** Monorepo structure, Docker Compose 6-container setup, JSON schemas (`task/tool/model/artifact.schema.json`), all stub modules.
- **Phase 1:** FastAPI backend wired to Ollama, JWT auth (`/api/auth/login`, `/api/auth/me`), PostgreSQL task persistence, React chat UI, Login page.
- **Phase 2:** Multi-model `ModelRegistry` with keyword-based `classify_task()` → `route_task()`, environment-driven model config, Phase 2 unit tests.

---

## 4. Folder Structure & Ownership

```
EdgeMind/
├── CLAUDE.md                          ← You are here
├── docker-compose.yml                 ← Full 6-container infra
├── phase-by-phase-implementation-plan.md   ← Master roadmap
├── sovereign-agentic-workbench-plan.md     ← Architecture doc
│
├── backend/                           ← Python FastAPI backend
│   ├── Dockerfile
│   ├── main.py                        ← FastAPI app entry point, CORS, routers
│   ├── requirements.txt               ← Pinned deps — don't casually upgrade
│   ├── api/
│   │   ├── agent.py                   ← Phase 3: POST /api/agent (Agent loop)
│   │   ├── auth.py                    ← JWT login/me endpoints (Phase 9: Keycloak)
│   │   ├── rag.py                     ← Phase 6: RAG endpoints
│   │   ├── tasks.py                   ← POST /api/tasks — task creation & model call
│   │   └── vision.py                  ← Phase 5: Vision/OCR endpoints
│   ├── artifacts/
│   │   └── docx_writer.py             ← Phase 7: DOCX generation stub
│   ├── database/
│   │   ├── models.py                  ← SQLAlchemy models: User, Task, TaskStep, Artifact
│   │   ├── repo.py                    ← Database repository functions
│   │   └── session.py                 ← DB engine, SessionLocal, get_db dependency
│   ├── models/
│   │   └── registry.py                ← ⭐ THE MODEL ROUTER — always go through this
│   ├── ocr/
│   │   ├── preprocess.py              ← Phase 5: OCR preprocessing (standalone API)
│   │   └── processor.py               ← Phase 5: OCR processor (Tesseract)
│   ├── orchestrator/                  ← Phase 3 (M1 — Orchestration Lead)
│   │   ├── state_machine.py           ← TaskStatus enum + transition rules
│   │   ├── planner.py                 ← Phase 3: generate_plan()
│   │   ├── executor.py                ← Phase 3: execute_plan()
│   │   └── validator.py               ← Phase 3: validate_answer()
│   ├── rag/
│   │   └── ingest.py                  ← Phase 6: chunk_document(), generate_embeddings()
│   ├── sandbox/
│   │   └── manager.py                 ← Phase 4: sandboxed Python execution
│   ├── schemas/
│   │   ├── artifact.schema.json
│   │   ├── model.schema.json
│   │   ├── task.schema.json
│   │   └── tool.schema.json           ← Interface contracts — honor these
│   ├── tests/
│   │   ├── test_phase1.py             ← 13 tests: auth, DB, RAG, OCR, state machine
│   │   ├── test_phase2.py             ← 4 tests: routing classify/route logic
│   │   ├── test_phase3.py             ← Phase 3 tests
│   │   ├── test_qa_phase2.py          ← Phase 2 QA tests
│   │   └── test_qa_phase3.py          ← Phase 3 QA tests
│   └── tools/
│       └── registry.py                ← Phase 4: Tool registry (register/execute/permission)
│
├── frontend/                          ← React + TypeScript + Vite
│   ├── Dockerfile
│   ├── package.json
│   ├── package-lock.json              ← Must be committed (CI depends on it)
│   └── src/
│       ├── App.tsx                    ← Root app with routing
│       ├── components/
│       │   └── Chat.tsx               ← Main chat component
│       ├── context/
│       │   └── AuthContext.tsx        ← JWT auth context + provider
│       └── pages/
│           └── Login.tsx              ← Login page (uses admin/kavach123 in dev)
│
└── tools/
    └── egress_monitor.sh              ← Phase 9: network sovereignty audit script
```

---

## 5. Key Files to Know

| File | Why it matters |
|------|---------------|
| [`phase-by-phase-implementation-plan.md`](./phase-by-phase-implementation-plan.md) | The master 11-phase build plan. Read before implementing anything. |
| [`backend/models/registry.py`](./backend/models/registry.py) | The model router. Every LLM call goes through `registry.route_task()` then `registry.execute_prompt()`. Never bypass this. |
| [`docker-compose.yml`](./docker-compose.yml) | Defines all 6 containers. The source of truth for ports, env vars, and service dependencies. |
| [`backend/database/models.py`](./backend/database/models.py) | SQLAlchemy ORM models. Know the schema before touching tasks/users/artifacts. |
| [`backend/orchestrator/state_machine.py`](./backend/orchestrator/state_machine.py) | TaskStatus enum and legal transitions. Phase 3 will use this heavily. |
| [`backend/api/auth.py`](./backend/api/auth.py) | JWT auth. Dev users: `admin/kavach123` and `operator/kavach123`. |

---

## 6. Dev Workflow

### Branch Strategy
```
hari-dev  →  dev  →  main
```
- All new work is done on `hari-dev`.
- When stable, merge to `dev` and push to GitHub.
- `main` is only updated for releases.
- **Never push directly to `main`.**

### Common Commands
```bash
# Start everything
docker-compose up -d --build

# Restart only the backend (after code changes)
docker-compose up -d --build backend

# Watch backend logs live
docker-compose logs -f backend

# Run all tests (local)
pytest backend/tests/

# Run tests inside Docker
docker-compose run --rm backend pytest

# Pull AI models (first time only)
docker-compose exec ollama ollama pull qwen2.5:1.5b
docker-compose exec ollama ollama pull qwen2.5-coder:1.5b

# Access services
# Frontend UI:  http://localhost:5173
# Backend API:  http://localhost:8000
# API Docs:     http://localhost:8000/docs
# MinIO UI:     http://localhost:9001
# Qdrant UI:    http://localhost:6333/dashboard
```

### Git Commit Convention
```bash
git add .
git commit -m "feat: <description>"   # New feature
git commit -m "fix: <description>"    # Bug fix
git commit -m "chore: <description>"  # Config/tooling changes
git push origin hari-dev
# Then merge to dev:
git checkout dev && git merge hari-dev && git push origin dev && git checkout hari-dev
```

---

## 7. Strict Rules & Constraints

### ✅ ALWAYS do this:
- Always route LLM calls through `registry.route_task()` → `registry.execute_prompt()` in `backend/models/registry.py`.
- Always write tests in `backend/tests/` for every new feature.
- Always update `backend/requirements.txt` when adding a new Python dependency (and pin the version).
- Always check the `phase-by-phase-implementation-plan.md` before implementing — follow the stated approach.
- Always keep the `frontend/package-lock.json` committed (CI depends on it for caching).
- Always honor the `task.schema.json`, `tool.schema.json`, `model.schema.json`, `artifact.schema.json` contracts in `backend/schemas/`.

### ❌ NEVER do this:
- **Never call Ollama's HTTP endpoint directly** from API handlers or orchestrator code. All calls go through the `ModelRegistry` singleton.
- **Never suggest OpenAI, Anthropic, AWS Bedrock, Google Vertex AI, or any cloud AI API.** This is a sovereign, offline system.
- **Never commit `__pycache__/` or `.pyc` files.** Add them to `.gitignore` if they sneak in.
- **Never hardcode model names** like `"qwen2.5:1.5b"` outside of `registry.py`. Use the `OLLAMA_REASONING_MODEL` / `OLLAMA_CODING_MODEL` environment variables.
- **Never push directly to `main`.**
- **Never upgrade `bcrypt`** beyond `4.0.1`. The current `passlib==1.7.4` + `bcrypt==4.0.1` combination is deliberately pinned to avoid a known password hashing crash bug on Python 3.11+.
- **Never add network calls to OCR or Vision modules.** All OCR is done locally via PaddleOCR or Tesseract. No cloud vision APIs.

---

## 8. Database Schema (Quick Reference)

The PostgreSQL schema lives in [`backend/database/models.py`](./backend/database/models.py).

| Table | Key Columns |
|-------|-------------|
| `users` | `id`, `username`, `password_hash`, `role` (admin/operator/viewer) |
| `tasks` | `id`, `description`, `status` (TaskStatus enum), `model_used`, `response`, `created_at` |
| `task_steps` | `id`, `task_id (FK)`, `action`, `result`, `created_at` |
| `artifacts` | `id`, `task_id (FK)`, `filename`, `file_hash`, `created_at` |
| `model_routes` | `id`, `task_id`, `task_type`, `selected_model`, `routing_reason` |
| `tool_calls` | `id`, `task_id`, `tool_name`, `arguments`, `result`, `status` |
| `audit_logs` | `id`, `action`, `details` |

---

## 9. Environment Variables (Backend)

Configured in `docker-compose.yml` and readable via `os.getenv()`.

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./edgemind_dev.db` (local dev) | PostgreSQL or SQLite connection string |
| `QDRANT_URL` | `http://qdrant:6333` | Qdrant vector DB URL |
| `MINIO_URL` | `http://minio:9000` | MinIO object storage URL |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama server base URL |
| `OLLAMA_REASONING_MODEL` | `qwen2.5:1.5b` | Default reasoning model |
| `OLLAMA_CODING_MODEL` | `qwen2.5-coder:1.5b` | Default coding model |
| `JWT_SECRET_KEY` | `kavach-dev-secret-...` | JWT signing key (change in prod) |
| `JWT_EXPIRE_MINUTES` | `480` | Token expiry (8 hours) |
| `OLLAMA_TIMEOUT` | `120` | Seconds to wait for Ollama response |

---

## 10. Phase 3 — What's Next (Agent Core)

The immediate next milestone is **Phase 3: Agent Core (Planner → Executor → Validator Loop)**.

Key things to implement (from the master plan):
1. **`TaskStateMachine` persistence** in `orchestrator/state_machine.py` — wire `persist_task_state()` and `restore_task_state()` to the `tasks` table.
2. **`generate_plan()`** in `orchestrator/planner.py` — call the reasoning model with a "produce a JSON step plan" prompt, parse into a DAG.
3. **`execute_plan()` / `execute_step()`** in `orchestrator/executor.py` — walk the step graph, calling tools from `tools/registry.py`.
4. **`validate_answer()`** in `orchestrator/validator.py` — minimal check: non-empty output and schema match.
5. **Live WS trace** — M6's responsibility: emit WebSocket events at each state transition for the UI trace panel.
6. **`task_steps` write-through** — every step persisted to the DB via `backend/database/models.py`.

**Definition of Done for Phase 3:** A 3+ step task runs end-to-end; state machine transitions are visible and persisted; a forced tool failure correctly transitions to `RETRYING` then `FAILED`.
