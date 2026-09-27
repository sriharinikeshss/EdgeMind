# EdgeMind

**A sovereign, air-gapped agentic AI workbench for industrial inspection — zero cloud dependency, runs entirely on-premise.**

[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.103-009688.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev)
[![Docker](https://img.shields.io/badge/docker-compose-2496ED.svg)](https://docs.docker.com/compose/)
[![Ollama](https://img.shields.io/badge/LLM-Ollama-black.svg)](https://ollama.ai)

---

## Demo

**Chat Interface**

<img src="docs/screenshots/chat.png" alt="Chat Interface" width="800">

*Submit a task and receive a streamed response from the local AI agent.*

---

**Agentic Execution Trace**

![Agentic Trace](docs/demo/agent_trace.gif)

*The Planner breaks the task into steps. The Executor runs each step through the tool registry. The Validator confirms the output — all visible in real time.*

---

**Audit Trail**

<img src="docs/screenshots/audit_trail.png" alt="Audit Trail" width="800">

*Every action is logged — model used, tool called, user, timestamp. No operation goes unrecorded.*

---

## The Problem

Industrial inspection environments — oil & gas, power generation, defence manufacturing — generate enormous volumes of reports, P&ID schematics, and operational data. Today's analysis workflow is largely manual: engineers sift through documents individually, with no shared context and no intelligent assistance.

The obvious solution — a cloud AI assistant — is off the table. Critical infrastructure operates under strict data sovereignty requirements. Sending inspection data to a third-party cloud API is a security and compliance failure, not a solution. Yet every mainstream "AI copilot" on the market requires an internet connection and phones home to an external inference provider.

The result is a forced choice between going fully manual or accepting unacceptable data exposure risk.

---

## Solution

EdgeMind is a full-stack agentic AI workbench that runs entirely on local hardware. There are no external API calls. Every byte of inference, retrieval, and storage stays within the deployment boundary.

- Multi-step agentic task execution via a Planner → Executor → Validator loop with state machine and retry logic
- On-premise LLM inference via Ollama — Qwen 2.5 for reasoning, Qwen 2.5 Coder for code tasks, LLaVA for vision
- OCR and vision pipeline for industrial inspection images using Tesseract, PaddleOCR, and LLaVA
- RAG pipeline for document-grounded question answering backed by a Qdrant vector store
- Role-based access control (admin / operator / viewer) with JWT authentication
- Air-gap enforcement on startup — the system actively blocks and audits any attempt at external egress

---

## Architecture

<img src="docs/architecture.png" alt="EdgeMind Architecture" width="1000">

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | React 18 + TypeScript + Vite | Hot-reload dev server, typed components |
| Backend | FastAPI (Python 3.11) | Async, auto-generated OpenAPI docs |
| LLM Inference | Ollama — Qwen 2.5 · Qwen 2.5 Coder · LLaVA | Fully local, no internet required |
| Vector Database | Qdrant | ANN search for RAG retrieval |
| Relational Database | PostgreSQL 15 | Tasks, users, artifacts, audit logs |
| Object Storage | MinIO | S3-compatible local file store |
| OCR | Tesseract + PaddleOCR | Local OCR, no cloud vision API |
| Containerization | Docker + Docker Compose | Single-command full-stack launch |
| Authentication | JWT (python-jose + passlib) | Stateless, role-scoped tokens |
| Report Generation | python-docx, openpyxl, ReportLab | DOCX / XLSX / PDF output |

---

## Features

**Agentic Core**
- Multi-step Planner → Executor → Validator loop
- Persistent state machine with legal transition enforcement and automatic retry on failure
- Extensible tool registry with per-tool permission scoping

**Inference**
- All LLM calls routed through a single `ModelRegistry` — no direct Ollama calls scattered across the codebase
- Task-type based model selection: reasoning tasks → Qwen 2.5, code tasks → Qwen 2.5 Coder
- Server-Sent Events (SSE) streaming for real-time agent trace in the UI

**Vision and OCR**
- P&ID schematic parsing and symbol extraction
- Inspection report OCR via Tesseract and PaddleOCR
- Image evidence upload with LLaVA-powered visual question answering

**Retrieval-Augmented Generation**
- Document ingestion pipeline with chunking and embedding
- Semantic search over ingested documents via Qdrant
- Grounded Q&A: answers cite the source document

**Security**
- Air-gap enforcement runs on every startup — blocks external egress and logs violations
- JWT role-based access control (admin / operator / viewer)
- Full audit log for every action
- Network egress monitoring via `tools/egress_monitor.sh`
- Prompt injection detection

**Artifact Generation**
- Downloadable DOCX, XLSX, and PDF reports generated from task outputs
- Artifacts stored in MinIO with content-hash verification

**Developer Experience**
- Hot-reload for both backend (uvicorn) and frontend (Vite)
- Full pytest suite in `backend/tests/`
- Interactive OpenAPI docs at `http://localhost:8000/docs`

---

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) 24+ and Docker Compose v2
- [Git](https://git-scm.com/)
- NVIDIA GPU with drivers installed (optional — CPU inference works, but is significantly slower)

### 1. Clone the repository

```bash
git clone https://github.com/<your-org>/EdgeMind.git
cd EdgeMind
```

### 2. Start all services

```bash
docker-compose up -d --build
```

This starts six services: `postgres`, `qdrant`, `minio`, `ollama`, `backend`, and `frontend`.

### 3. Pull the AI models (first boot only)

Wait for the `ollama` container to be healthy, then run:

```bash
docker-compose exec ollama ollama pull qwen2.5:1.5b
docker-compose exec ollama ollama pull qwen2.5-coder:1.5b
docker-compose exec ollama ollama pull llava
```

Model pulls are one-time. They are stored in the `ollama_data` Docker volume and persist across restarts.

### 4. Access the application

| Service | URL |
|---|---|
| Frontend UI | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| MinIO Console | http://localhost:9001 |
| Qdrant Dashboard | http://localhost:6333/dashboard |

### 5. Log in

```
Username: admin
Password: kavach123
```

> **Before any production deployment:** rotate `JWT_SECRET_KEY` and change the default credentials. See [Environment Variables](#environment-variables).

---

## Running the Application

These commands assume the stack is already set up. Use these for day-to-day operation.

### Start / Stop

```bash
# Start all services (detached)
docker-compose up -d

# Stop all services (data is preserved)
docker-compose down

# Stop all services and delete all volumes — full reset, data is lost
docker-compose down -v
```

### Rebuild a Single Service

Use this after modifying source code without restarting the entire stack:

```bash
# Rebuild and restart the backend only
docker-compose up -d --build backend

# Rebuild and restart the frontend only
docker-compose up -d --build frontend
```

### Logs

```bash
# Follow all services
docker-compose logs -f

# Follow the backend only
docker-compose logs -f backend
```

### Health Check

```bash
docker-compose ps
```

You can also hit the backend health endpoint directly:

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

---

## Project Structure

```
EdgeMind/
├── backend/                   # FastAPI application
│   ├── api/                   # Route handlers — tasks, auth, agent, agent_stream, rag, vision, documents, artifacts, security
│   ├── orchestrator/          # Planner → Executor → Validator loop and state machine
│   ├── models/                # ModelRegistry — every LLM call is routed through here
│   ├── rag/                   # Document ingestion, chunking, embedding, Qdrant retrieval
│   ├── vision/                # OCR pipeline (Tesseract / PaddleOCR) and LLaVA integration
│   ├── security/              # Air-gap enforcement, RBAC, audit logs, prompt injection detection
│   ├── database/              # SQLAlchemy ORM models and session management
│   ├── artifacts/             # DOCX / XLSX / PDF report generation
│   ├── schemas/               # JSON Schema contracts for tasks, tools, models, artifacts
│   └── tests/                 # pytest test suite
├── frontend/                  # React + TypeScript + Vite
│   └── src/
│       ├── components/        # Chat, AgentTrace, VisualEvidence
│       ├── pages/             # Login
│       └── context/           # AuthContext — JWT token management
├── samples/                   # Sample P&ID schematics and inspection report images
├── tools/                     # egress_monitor.sh — network sovereignty audit script
└── docker-compose.yml         # Defines all 6 services
```

---

## API Reference

A subset of the most frequently used endpoints. For the full interactive reference, open the Swagger UI at `http://localhost:8000/docs`.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/login` | Exchange credentials for a JWT token |
| `POST` | `/api/tasks` | Submit a new task for agentic execution |
| `GET` | `/api/tasks/{id}` | Retrieve task status and full step trace |
| `GET` | `/api/agent/stream/{id}` | SSE stream of live agent trace events |
| `POST` | `/api/rag/ingest` | Ingest a document into the vector store |
| `POST` | `/api/vision/analyze` | Run OCR and visual analysis on an uploaded image |
| `GET` | `/api/artifacts/{id}` | Download a generated report (DOCX / XLSX / PDF) |

All endpoints require a `Bearer` token in the `Authorization` header except `/api/auth/login`.

---

## Environment Variables

All variables are configured in `docker-compose.yml`. Override them via a `.env` file at the project root or by editing the compose file directly.

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | SQLite (local dev) | PostgreSQL or SQLite connection string |
| `QDRANT_URL` | `http://qdrant:6333` | Qdrant vector database URL |
| `MINIO_URL` | `http://minio:9000` | MinIO object storage URL |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama inference server URL |
| `OLLAMA_REASONING_MODEL` | `qwen2.5:1.5b` | Model used for reasoning tasks |
| `OLLAMA_CODING_MODEL` | `qwen2.5-coder:1.5b` | Model used for code tasks |
| `OLLAMA_VISION_MODEL` | `llava` | Model used for image analysis |
| `ENFORCE_AIRGAP` | `true` | Enforce air-gap isolation on startup |
| `JWT_SECRET_KEY` | `kavach-dev-secret-...` | JWT signing key — **change before production** |
| `JWT_EXPIRE_MINUTES` | `480` | Token expiry duration in minutes |
| `OLLAMA_TIMEOUT` | `120` | Seconds to wait for an Ollama response |

---

## Running Tests

```bash
# Run the full test suite locally (requires Python + dependencies installed)
pytest backend/tests/

# Run tests inside Docker (no local Python required)
docker-compose run --rm backend pytest

# Run a specific test file
docker-compose run --rm backend pytest tests/test_phase2_qa.py -v
```

---

## Acknowledgements

- [Ollama](https://ollama.ai) — local LLM inference runtime
- [Qdrant](https://qdrant.tech) — vector similarity search engine
- [FastAPI](https://fastapi.tiangolo.com) — Python web framework
- [React](https://react.dev) — frontend UI library
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) — open-source OCR engine
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) — OCR toolkit
- [MinIO](https://min.io) — S3-compatible object storage

