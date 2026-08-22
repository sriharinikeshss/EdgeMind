# Sovereign On-Premise Agentic AI Workbench (MRPL 26117)
## Complete Technical & Implementation Plan

---

## 1. Project Vision

**Name:** **KAVACH** (Sanskrit: "armor/shield") — *Sovereign Multimodal Agentic Workbench*, or formally **KAVACH-AI: Air-Gapped Agentic Intelligence Platform**.

- **Problem solved:** Industrial/confidential organizations (defense, energy, manufacturing, PSU plants) cannot send sensitive documents, drawings, or data to cloud LLMs (ChatGPT/Copilot/Claude API) due to confidentiality, regulation, or air-gap mandates — yet they need LLM-grade productivity: summarizing inspection reports, reading P&IDs, drafting approval notes, writing/verifying code, doing calculations. KAVACH delivers this entirely inside the factory network, with zero external calls.
- **Key differentiator:** Not a single chatbot wrapper — a **multi-model, tool-using, self-validating agent** that routes each task fragment to the *right* specialized local model, executes multi-step plans with real tools, and produces **verified, downloadable deliverables**, not just chat text.
- **What makes it "sovereign":** 100% on-premise inference (no API keys to OpenAI/Anthropic/Google), open-weight models with verifiable hashes, network egress physically/logically blocked, all storage/vector DB/RAG local, full audit trail, and a live "Sovereignty Status" indicator provable to judges/auditors in real time.
- **What makes it genuinely agentic:** A **Planner → Executor → Validator → Replanner** loop that decomposes a goal into steps, chooses tools/models per step, observes results, self-checks against sources/calculations, and iterates on failure — with human-in-the-loop approval gates before any sensitive or final action. A chatbot answers one turn; KAVACH plans, acts, checks, and produces artifacts.

---

## 2. End-to-End Workflows

### 2.1 Generic Skeleton
```
User Prompt/Files
   → Task Understanding (classify type, modality, complexity, sensitivity)
   → Model/Task Router (select model(s) + tools)
   → Planner (decompose into ordered steps + dependencies)
   → Executor (loop: select tool → execute → observe)
   → Validator (grounding/consistency/calculation/schema checks)
   → Iterate (replan on failure, up to N retries)
   → Artifact Generation (DOCX/XLSX/PPTX/PDF/code)
   → Artifact Validation
   → Human Approval (if sensitive)
   → Final Response + Audit Log Entry
```

### 2.2 Document Summarization
`upload doc → parse_docx/parse_pdf → chunk → (optional RAG cross-reference) → reasoning model summarizes → validator checks claims vs source → DOCX/markdown summary artifact → citations attached`

### 2.3 Scanned PDF / OCR
`PDF pages → render to images → preprocess (deskew/denoise) → OCR (text regions) + confidence scoring → low-confidence regions flagged → structured text reconstructed → reasoning model consumes structured text → validator cross-checks OCR confidence before accepting claims`

### 2.4 Engineering Drawing / P&ID Understanding
`image/drawing → vision-language model → equipment/tag/valve/line detection → relationship extraction (connectivity graph) → structured JSON representation → reasoning model answers questions grounded in the JSON (not free visual guessing) → explicit "visual evidence" crop attached to each claim`

### 2.5 Coding Task
`NL request → coding model selected by router → generate_code() → sandbox execute_tests() → capture stdout/stderr → detect errors → fix_code() → rerun → verify_code() → package_code_artifact()`

### 2.6 Spreadsheet / Calculation Task
`read_workbook() → identify formulas/data → execute_calculation() in sandboxed Python (never LLM mental math for final numbers) → verify_calculation() cross-check → write_cells()/create_formula() → save_workbook() → validate_xlsx()`

### 2.7 Knowledge-Base / RAG Task
`query → hybrid_search (BM25 + vector) → rerank → build_context() with citations → reasoning model answers only from retrieved context → validator verifies every claim maps to a retrieved chunk → citations rendered in UI`

### 2.8 Multi-Step Approval-Note Generation
`scanned report (OCR) + SOP (RAG) → extract findings → compare vs SOP → calculate required values (sandbox) → draft note (reasoning model) → generate_docx() → validate_docx() (sections/citations/calc check) → human approval gate → finalize`

### 2.9 Multimodal Task (text + image + tables)
`process_multimodal_task(): classify files → route text to document pipeline, images to vision pipeline → fuse contexts (combine_visual_and_textual_context) → single reasoning pass grounded in both → artifact generation → validation`

---

## 3. System Architecture

### 3.1 Layers & Responsibilities

| Layer | Responsibility |
|---|---|
| Frontend/UI | Chat/workbench, uploads, live agent trace, approvals |
| API Gateway | REST + WebSocket entrypoint, rate limiting, request validation |
| AuthN/AuthZ | Local identity provider (Keycloak/OIDC), RBAC |
| Agent Orchestration | Task state machine, planner/executor loop |
| Model Router | Chooses model per subtask given modality/VRAM/latency |
| LLM Inference | Local model servers (vLLM/Ollama/TGI) |
| Vision/OCR | Layout detection, OCR engine, VLM for images/drawings |
| RAG/Knowledge | Ingestion, chunking, embeddings, vector DB, reranking |
| Tool Execution | Registered tool calls (file, calc, DB, generation) |
| Sandbox | Isolated container for code execution |
| Artifact Generation | DOCX/XLSX/PPTX/PDF/code writers |
| Validation | Grounding, schema, calculation, hallucination checks |
| Audit/Logging | Immutable event log of every action |
| Security/Privacy | Encryption, data classification, egress blocking |
| Storage/DB | Postgres (relational) + local object storage + vector DB |

### 3.2 Data Flow (summary)
UI → API Gateway (authenticated) → Orchestrator creates Task → Task Understanding classifies → Router picks model(s)/tools → Planner emits plan → Executor loop calls Tool Layer / Model Layer / RAG Layer, writing every event to Audit Log → Validator scores output → Artifact Layer persists files to local object store → Approval workflow (if required) → Response streamed back over WebSocket → all data at rest encrypted, nothing leaves the private VLAN.

### 3.3 ASCII Architecture Diagram
```
┌───────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND / WORKBENCH                         │
│   Chat UI | Upload | Task Trace | Model Badge | Tool Log | Approvals      │
└──────────────────────────────┬────────────────────────────────────────────┘
                                │ HTTPS/WSS (internal network only)
┌──────────────────────────────▼────────────────────────────────────────────┐
│                          API GATEWAY  (FastAPI/Nginx)                    │
└──────────────────────────────┬────────────────────────────────────────────┘
                                │
┌──────────────────────────────▼────────────────────────────────────────────┐
│                      AUTH (Keycloak/OIDC) + RBAC                         │
└──────────────────────────────┬────────────────────────────────────────────┘
                                │
┌──────────────────────────────▼────────────────────────────────────────────┐
│                      AGENT ORCHESTRATOR (Task State Machine)             │
│      Planner ─► Executor ─► Validator ─► Replanner ─► Finalizer          │
└───┬───────────┬───────────┬───────────┬───────────┬──────────────────────┘
    │           │           │           │           │
┌───▼───┐  ┌────▼────┐ ┌────▼────┐ ┌────▼─────┐ ┌───▼──────┐
│ MODEL │  │  RAG /   │ │  TOOL    │ │ SANDBOX  │ │ ARTIFACT │
│ROUTER │  │KNOWLEDGE │ │ REGISTRY │ │(Docker)  │ │  GEN     │
└───┬───┘  └────┬────┘ └────┬────┘ └────┬─────┘ └───┬──────┘
    │           │           │           │           │
┌───▼──────┐┌───▼─────┐┌────▼─────┐┌────▼─────┐┌────▼─────┐
│ LLM      ││ Vector   ││ File/DB  ││ Isolated ││ DOCX/XLSX│
│ Servers  ││ DB       ││ Tools    ││ Container││ PPTX/PDF │
│(vLLM/    ││(Qdrant)  ││          ││ (no net) ││ /code    │
│ Ollama)  ││          ││          ││          ││          │
└──────────┘└──────────┘└──────────┘└──────────┘└──────────┘
        │
┌───────▼────────────────────────────────────────────────────┐
│  VISION/OCR LAYER (VLM + Tesseract/PaddleOCR + layout model) │
└───────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│  VALIDATION LAYER  │  AUDIT/LOGGING  │  SECURITY/EGRESS BLOCK  │
└───────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│  STORAGE: Postgres (metadata) | MinIO (files) | Qdrant (vectors)│
└───────────────────────────────────────────────────────────────┘

              [ FIREWALL: ALL EXTERNAL EGRESS DENIED BY DEFAULT ]
```

---

## 4. Model Architecture

| Model Role | Example Open-Weight Model | Notes |
|---|---|---|
| General reasoning | Llama-3.1-70B-Instruct / Qwen2.5-72B-Instruct (quantized) | Long-context reasoning, note drafting |
| Coding model | Qwen2.5-Coder-32B / DeepSeek-Coder-V2 | Code gen, debugging |
| Vision-language | Qwen2-VL-72B / InternVL2 | P&ID, photos, drawings |
| OCR | PaddleOCR / docTR / Tesseract 5 | Text extraction from scans |
| Embedding | BGE-M3 / Nomic-Embed-Text | RAG chunk embeddings |
| Reranker | BGE-Reranker-v2-m3 | Reorders top-K retrieval results |
| Routing/classification | Small distilled model (Qwen2.5-1.5B / DistilBERT classifier) | Fast task-type classification |
| Speech (optional) | Whisper (large-v3, local) | Voice notes/dictation, Phase 2 |

**Router decision factors:** task type (from classifier), input modality, required context length, current VRAM headroom (via `nvidia-smi`/`nvml`), model quality tier vs latency budget, and hardware availability (GPU vs CPU fallback). The router is **model-agnostic**: models are registered via a metadata schema (see §Model Registry) so any new open-weight checkpoint can be swapped in without code changes — only a registry entry.

**Routing algorithm (pseudocode):**
```
candidates = filter(models, task_type ∈ model.capabilities)
candidates = filter(candidates, model.vram_requirement <= available_vram)
scored = [ (m, score(m.quality, m.latency, priority, ctx_fit)) for m in candidates ]
selected = argmax(scored)
if selected.unavailable: fallback_model(next_best)
```

---

## 5. Agent Architecture

- **Planner:** decomposes goal into an ordered, dependency-aware step graph.
- **Executor:** walks the graph, invoking Tool Selector per step.
- **Tool Selector:** matches step intent → registered tool via metadata/permission check.
- **Memory/Context Manager:** maintains rolling context, compresses/summarizes old turns, persists task state for resumability.
- **Validator:** checks each step's output (and the final artifact) against grounding/calculation/schema rules.
- **Retry/Iteration:** on validator failure, triggers `replan()` (bounded retries, e.g., max 3) before escalating to human.
- **Human-in-the-loop:** approval gate before any action classified as sensitive (finalizing an approval note, deleting/overwriting a file, executing untrusted code with file I/O).
- **Task State Management:** explicit state machine (see §AB) persisted in Postgres for crash recovery.

### Example Execution Trace
**Request:** *"Read this scanned inspection report, identify critical findings, compare with SOP, calculate required values, draft an approval note, generate DOCX, validate, present for approval."*

```
[CLASSIFIED] task_type=multimodal_approval_note, sensitivity=HIGH
[PLANNED] steps:
  1. ocr.preprocess_pdf_page + run_ocr(inspection_report.pdf)
  2. vision.analyze_scanned_document (flag low-confidence regions)
  3. rag.hybrid_search("relevant SOP clauses") → retrieve_context()
  4. reasoning_model.compare(findings, sop_context) → critical_findings[]
  5. sandbox.execute_calculation(required_values)
  6. reasoning_model.draft_approval_note(findings, calcs, citations)
  7. artifact.create_docx(note) 
  8. validation.validate_docx + validate_citations + validate_calculations
  9. human.create_approval_request() → WAIT
 10. on approve → finalize_task(); on reject → replan(step 6)
[EXECUTING] step 1 ... OK (ocr_confidence=0.94)
[EXECUTING] step 2 ... 2 regions flagged <0.6 confidence → surfaced to user
[EXECUTING] step 3 ... 4 SOP clauses retrieved, cited
[EXECUTING] step 4 ... 3 critical findings identified
[EXECUTING] step 5 ... sandboxed calc verified (tolerance ✓)
[EXECUTING] step 6 ... draft generated
[EXECUTING] step 7 ... DOCX created (hash=...)
[VALIDATING] step 8 ... PASS (grounding_score=0.97)
[WAITING_FOR_APPROVAL] → notify approver
[COMPLETED] on approval; audit trail finalized
```

---

## 6. Tools to Implement

| Tool | Purpose | Tech/Library | Security Notes | MVP/Phase2 |
|---|---|---|---|---|
| File reader/writer | Local FS I/O | Python `pathlib` | Path allow-listing, no traversal | MVP |
| PDF parser | Extract text/tables | `pypdf`, `pdfplumber` | Sandboxed parsing (malformed PDFs) | MVP |
| OCR | Scanned text extraction | PaddleOCR/Tesseract | Local only, no cloud OCR API | MVP |
| Image analysis | Photos/drawings | Local VLM | No image ever leaves host | MVP |
| Document parser | DOCX/PPTX structure | `python-docx`, `python-pptx` | Strip macros/embedded objects | MVP |
| Spreadsheet R/W | XLSX manipulation | `openpyxl` | Formula injection sanitization | MVP |
| Calculator | Deterministic math | Python `decimal`/`numpy` in sandbox | No `eval()` on raw strings | MVP |
| Python execution | Data/calc scripts | Sandboxed subprocess | See §10 | MVP |
| Code sandbox | Run generated code | Docker/gVisor/Firecracker | Network off, FS isolated | MVP |
| Internal doc search | Keyword search | Postgres full-text / BM25 (Elasticsearch/OpenSearch) | RBAC-filtered | MVP |
| RAG retrieval | Semantic search | Qdrant/pgvector | Same as above | MVP |
| Web access | External browsing | — | **Disabled by default**, requires explicit admin unlock, off in air-gapped mode | Phase 2 (optional, disabled) |
| Database query | Structured queries | Parameterized SQL only | No dynamic SQL from LLM text | Phase 2 |
| DOCX/XLSX/PPTX/PDF gen | Deliverables | `python-docx/pptx/openpyxl`, `reportlab`/`weasyprint` | Template injection checks | MVP |
| JSON/CSV processing | Data interchange | stdlib `json`/`csv`, `pandas` | Schema validation | MVP |
| Report generation | Composite artifacts | Jinja2 templates + doc libs | Validate before send | MVP |
| Validation tools | Consistency checks | Custom rule engine + LLM-as-judge (local) | See §12 | MVP |

---

## 7. Multimodal Pipeline

```
Input file → type detection
  ├─ digital PDF/DOCX → text extraction directly
  └─ scanned PDF/image → page rendering (pdf2image) → preprocessing (deskew, contrast)
        → layout detection (LayoutParser/DocLayNet model) → OCR (PaddleOCR)
        → (if drawing/P&ID) vision-language model for component/tag/connection extraction
→ structured representation (JSON: text blocks + bounding boxes + confidence + visual entities)
→ retrieval/reasoning (reasoning model consumes ONLY the structured representation, never "guesses" from a blurry mental image)
→ output with citations pointing to page/region/bbox
```

**Anti-hallucination measures:**
- Reasoning model is never shown a raw ambiguous image without a structured extraction layer already run.
- Every visual claim must reference a bounding-box/region ID from the extraction step ("visual evidence").
- Low OCR/vision confidence regions are explicitly flagged and excluded from confident claims — surfaced as "needs human verification" rather than silently guessed.
- Validator cross-checks that every factual claim in the output maps to an extracted entity, not free generation.

---

## 8. Local RAG / Knowledge Base

- **Ingestion:** watch folder / manual upload → `ingest_document()`.
- **Parsing:** format-specific parsers (§Document Processing).
- **Chunking:** structure-aware (by heading/section, ~300–500 tokens, overlap ~15%).
- **Metadata:** doc_id, version, source path, classification level, page/section, timestamp.
- **Embeddings:** BGE-M3 (local), stored with metadata.
- **Vector DB:** Qdrant (self-hosted, on-prem) or `pgvector` for simplicity.
- **Hybrid search:** BM25 (OpenSearch/Postgres FTS) + vector similarity, combined via reciprocal rank fusion.
- **Reranking:** BGE-Reranker-v2-m3 on top-K candidates.
- **Context construction:** assemble top-N reranked chunks with citation tags before passing to reasoning model.
- **Citations/provenance:** every chunk carries doc_id + page + hash; citations rendered in UI, clickable to source.
- **Versioning:** new upload of same doc_id creates version N+1; old chunks marked superseded, not deleted (audit trail).

---

## 9. Security / Sovereignty

- **Air-gapped deployment:** entire stack (models, DB, vector DB, app) runs inside an isolated VLAN/host with no default route to internet.
- **No external API calls:** all LLM/embedding/OCR/vision calls resolve to `localhost`/internal service DNS only; code review + automated egress tests enforce this.
- **Network egress blocking:** `iptables`/firewall rules deny all outbound except explicitly whitelisted internal subnets; enforced at host and container level.
- **Local model inference:** vLLM/Ollama/TGI serving locally-stored checkpoints.
- **Local storage:** Postgres + MinIO + Qdrant all on-prem, encrypted volumes (LUKS/dm-crypt).
- **RBAC:** Keycloak roles (Admin, Approver, Operator, Viewer) enforced at API gateway and tool-authorization layer.
- **Encryption:** TLS for internal traffic, AES-256 at rest for documents/artifacts.
- **Secrets management:** HashiCorp Vault (self-hosted) or `.env` + OS keyring for hackathon scope.
- **Audit logs:** append-only table, every tool call/model call/approval logged with hash chaining for tamper-evidence.
- **File isolation:** per-task working directories, no cross-task file access.
- **Sandbox isolation:** Docker with `--network none`, read-only root FS, seccomp profile.
- **Prompt injection protection:** system-prompt isolation, content-type tagging of untrusted document text, output-schema constraints, tool-call allow-listing.
- **Tool authorization:** every tool call checked against role + risk level before execution.
- **Data classification:** documents tagged Public/Internal/Confidential/Secret; classification gates which models/tools may touch them.
- **Human approval:** required for: finalizing approval notes, overwriting/deleting files, any action tagged HIGH sensitivity.
- **Model supply-chain verification:** SHA-256 checksum verification of model weights against a signed manifest before loading.

**Live demo of "no data leaves the machine":**
1. Run `tcpdump`/Wireshark on the host's external interface during the entire demo — show zero packets to any non-local IP.
2. Show firewall rule dump (`iptables -L`) with default-deny egress policy.
3. Display the in-UI **Sovereignty Status** panel: `LOCAL ONLY / AIR-GAPPED / NO EXTERNAL CONNECTIONS`, live-updated from `verify_no_egress()`.
4. Physically disconnect the Ethernet/Wi-Fi during the demo and show the system still works end-to-end.
5. Show `generate_sovereignty_report()` output as a signed artifact for judges.

---

## 10. Code Execution Sandbox

- **Technology:** Docker (hackathon-practical) with option to harden later via gVisor or Firecracker microVMs.
- **Resource limits:** `--memory=512m --cpus=1 --pids-limit=64`.
- **Time limits:** wall-clock timeout (`timeout 10s` wrapper) + orchestrator-level watchdog kill.
- **Filesystem isolation:** ephemeral container, only task-scoped input files copied in via a temp mount; **no** access to host filesystem, no bind-mount of confidential document store.
- **Network disabled:** `--network none` always.
- **Package restrictions:** pre-baked image with an allow-listed package set; no internet-based `pip install` at runtime.
- **Allowed languages:** Python and (Phase 2) Node.js/Bash, each in its own hardened image.
- **Output capture:** stdout/stderr captured, size-capped, returned to executor.
- **Validation:** exit code + output schema checked before trusting results.
- **Cleanup:** container destroyed (`destroy_sandbox()`) after every execution; no state persists between tasks.

This guarantees generated code can **never** read/write confidential host files — it only ever sees the explicit, whitelisted input copied in for that step.

---

## 11. Artifact Generation

| Artifact | Library | Validation After Generation |
|---|---|---|
| DOCX | `python-docx` | Section presence, citation presence, hash |
| XLSX | `openpyxl` | Formula integrity, no #REF!/#DIV0 errors |
| PPTX | `python-pptx` | Slide count, placeholder completeness |
| PDF | `reportlab`/`weasyprint` | Page count, text extractability |
| Source code | Language-specific writer | Sandbox execution + test pass |
| CSV/JSON | stdlib | Schema/row-count validation |
| Calculation report | Jinja2 template + calc engine | Recompute & diff-check against report figures |

Pipeline: generate → `calculate_artifact_hash()` → run format-specific validator → if fail, feed error back to agent for one repair iteration → else mark artifact COMPLETE and attach to task.

---

## 12. Validation Engine

Checks performed: factual consistency (claims vs sources), source grounding, calculation correctness (recompute independently), citation presence, document completeness (required sections present), file integrity (hash, opens without corruption), code execution success, schema correctness (JSON/CSV), hallucination risk (unsupported-claim ratio), and policy/security violations (PII leak, disallowed content).

**Grounding score** = (claims supported by a retrieved/extracted source) / (total factual claims). Threshold e.g. ≥0.9 to pass; below that, `detect_unsupported_claims()` returns the offending claims and the orchestrator calls `replan()` to regenerate just that portion — bounded to 3 retries before flagging for human review.

---

## 13. Frontend

- **Chat/Workbench** — main interaction pane.
- **File upload** (single & multi-file, drag-drop).
- **Task status** — live state machine badge (PLANNED/EXECUTING/VALIDATING/...).
- **Agent execution trace** — expandable step list with timestamps.
- **Selected model display** — badge showing which model handled each step (routing transparency for judges).
- **Tool calls** — expandable JSON of inputs/outputs per call.
- **Sources/citations** — clickable chips linking to source doc/page.
- **Generated artifacts** — download cards with hash + validation status.
- **Approval buttons** — Approve / Reject / Request Revision.
- **Security status** — data classification of current task.
- **Network isolation status** — live "AIR-GAPPED" badge.
- **Audit history** — searchable timeline.

**Suggested stack:** React + TypeScript, TailwindCSS, shadcn/ui, WebSocket client (native or `socket.io-client`), state via Zustand/Redux Toolkit.

---

## 14. Backend Technology Stack

| Concern | Choice |
|---|---|
| Frontend | React + TS + Tailwind |
| Backend/API | FastAPI (Python) |
| Agent orchestration | Custom orchestrator (LangGraph optional) |
| Model serving | vLLM (GPU) / Ollama (fallback, easy quantized models) |
| Vector DB | Qdrant (or `pgvector` to reduce moving parts) |
| Relational DB | PostgreSQL |
| OCR | PaddleOCR |
| Document processing | `python-docx/pptx/openpyxl`, `pdfplumber` |
| Sandbox | Docker (local daemon) |
| Artifact generation | Same doc libs + `reportlab` |
| Auth | Keycloak (OIDC) or simple JWT for hackathon scope |
| Logging | Structured JSON logs → Loki/ELK (or just Postgres table for hackathon) |
| Monitoring | Prometheus + Grafana (optional for demo) |
| Deployment | Docker Compose (single workstation), Kubernetes optional for scale-out |

---

## 15. Team of 6

| # | Role | Responsibilities | Tech | Modules Owned | Deliverables |
|---|---|---|---|---|---|
| 1 | **Tech Lead / Orchestration Engineer** | Agent state machine, planner/executor/validator loop, integration | Python, FastAPI | Agent Orchestrator, Planner, Task State Machine | Working PLAN→EXECUTE→VALIDATE loop |
| 2 | **Model/Infra Engineer** | Model serving, router, VRAM management, quantization | vLLM/Ollama, CUDA | Model Registry, Model Router, LLM Inference | Multi-model serving + routing demo |
| 3 | **RAG/Knowledge Engineer** | Ingestion, chunking, embeddings, hybrid search | Qdrant, BGE models | RAG pipeline, Vector DB, Embedding/Reranking | Working RAG with citations |
| 4 | **Multimodal/Vision Engineer** | OCR, layout detection, VLM integration, P&ID extraction | PaddleOCR, VLM | Vision/OCR layer, Multimodal pipeline | Scanned-doc + P&ID demo |
| 5 | **Tools/Backend Engineer** | Tool registry, sandbox, artifact generation, DB schema | Docker, python-docx/pptx/openpyxl | Tool Layer, Sandbox, Artifact Generation, Database | Sandbox + artifact pipeline |
| 6 | **Frontend/Security Engineer** | UI, auth, RBAC, audit log UI, network sovereignty demo | React, Keycloak, iptables | Frontend, Security Engine, Audit/Logging, Network Sovereignty | Full workbench UI + live sovereignty demo |

Each module exposes a clear internal API/interface (see §API Design) so the six workstreams integrate without blocking each other.

---

## 16. Development Phases

| Phase | Features | Tech | Dependencies | Definition of Done |
|---|---|---|---|---|
| 0 – Setup | Repo, Docker Compose skeleton, CI | Git, Docker | — | All services boot locally |
| 1 – Basic Local LLM | Single model serving + chat | vLLM/Ollama | Phase 0 | Local chat working, no cloud calls |
| 2 – Model Router | Multi-model registry + routing | Router service | Phase 1 | 2+ models auto-selected correctly |
| 3 – Agent Core | Planner/Executor/Validator loop | Orchestrator | Phase 2 | Multi-step task completes end-to-end |
| 4 – Tools | File/calc/DB tools registered | Tool registry | Phase 3 | Agent calls ≥5 tools successfully |
| 5 – Multimodal | OCR + VLM pipeline | PaddleOCR, VLM | Phase 4 | Scanned doc → structured text demo |
| 6 – RAG | Ingestion → hybrid search → citations | Qdrant | Phase 4 | RAG answer with correct citations |
| 7 – Artifact Generation | DOCX/XLSX/PPTX/PDF writers | doc libs | Phase 3 | Valid downloadable artifacts |
| 8 – Validation | Grounding/calc/schema validators | Custom rules | Phase 5,6,7 | Failing artifact triggers retry |
| 9 – Security | RBAC, egress block, audit log, sandbox hardening | Keycloak, iptables | All above | Sovereignty report passes |
| 10 – Integration/Demo | Full pipeline, UI polish, demo scripts | — | All above | Both demo scenarios run reliably live |

---

## 17. MVP vs Advanced Features

**A. Must-have MVP:** document/PDF ingestion, OCR for scanned docs, 2+ model routing (reasoning + coding), planner/executor/validator loop, sandboxed Python/code execution, DOCX/XLSX generation, basic RAG with citations, RBAC login, audit log, network egress blocking + status badge, human approval gate.

**B. Strong differentiators:** P&ID/engineering-drawing understanding, live agent execution trace UI, sovereignty live-demo (Wireshark/cable-pull), validator-driven auto-retry loop, model-selection transparency badge.

**C. Phase-2/advanced:** speech input, Kubernetes deployment, Vault secrets management, fine-tuned domain classifier, multi-tenant workspace isolation, advanced P&ID connectivity-graph reasoning.

**D. Do NOT build (wastes hackathon time):** a custom LLM training pipeline, a proprietary vector DB, a full custom OCR model from scratch, a general-purpose web browser tool (contradicts sovereignty goal), a mobile app, multi-cloud deployment abstractions.

---

## 18. Demo Scenarios

**Demo 1 — Approval Note (primary):** Upload scanned inspection report + SOP PDF + a P&ID photo → system OCRs the report, retrieves relevant SOP clauses via RAG, reasons over findings, runs a sandboxed calculation, drafts an approval note, generates a DOCX, validates it (citations + calc check), routes to a human approver in the UI, and finalizes on approval. Judges see the full agent trace, model badges, and sovereignty status live.

**Demo 2 — Coding Task (secondary):** NL request ("write and verify a function to compute pipe stress from these parameters") → coding model selected → code generated → executed in sandbox → tests run → on failure, agent auto-debugs and reruns → verified code artifact delivered with test output.

---

## 19. Model Routing Demo

- Upload a text document → UI model badge shows **Reasoning Model (Qwen2.5-72B)** selected, visible in the "Selected Model" panel with the router's justification (task_type=document_analysis).
- Submit a coding request → badge switches to **Coding Model (Qwen2.5-Coder-32B)**, justification (task_type=coding).
- Upload a P&ID photo → badge switches to **Vision-Language Model (Qwen2-VL)**.

This routing is visible to judges live via the "Model Selection" panel in the frontend, plus a routing-decision log entry (`log_model_selection()`) shown in the audit trail.

---

## 20. Network Sovereignty Demo

Show, in real time: (1) Wireshark/tcpdump capturing zero packets to external IPs throughout the whole demo; (2) `iptables -L` default-deny egress ruleset; (3) the in-app "AIR-GAPPED / NO EXTERNAL CONNECTIONS" badge staying green; (4) physically unplugging network during the approval-note demo and completing it successfully; (5) the exported `sovereignty_report` artifact as evidence judges can inspect afterward.

---

## 21. Data Flow & Security Flow

```
[Upload] → encrypted at rest (MinIO, AES-256) → classified (Confidential) 
   → only RBAC-authorized roles can retrieve → passed to OCR/RAG in-memory,
   never written unencrypted to disk → model inference happens locally 
   (weights + KV cache stay in host GPU/CPU memory) → generated artifact 
   encrypted at rest → audit log records every touchpoint (who, what, when,
   which model, which tool) → nothing crosses the network boundary at any point.
```
Confidential data exists at rest (encrypted object store), in-memory during processing (host-only), and in generated artifacts (encrypted, access-controlled) — never in transit to any external endpoint.

---

## 22. Database Schema (practical)

```sql
users(id, username, password_hash, role_id, created_at)
roles(id, name, permissions_json)
tasks(id, user_id, type, status, sensitivity, created_at, updated_at)
task_steps(id, task_id, step_no, tool_name, model_name, status, input_json, output_json, started_at, ended_at)
models(id, name, version, quantization, modality, context_length, vram_mb, status)
model_routes(id, task_type, model_id, priority, created_at)
documents(id, filename, classification, version, storage_path, hash, uploaded_by, uploaded_at)
document_chunks(id, document_id, chunk_text, page_no, embedding_id, metadata_json)
embeddings_meta(id, chunk_id, vector_db_id, model_used, created_at)
tool_calls(id, task_step_id, tool_name, args_json, result_json, risk_level, timestamp)
artifacts(id, task_id, type, storage_path, hash, validation_status, created_at)
validation_results(id, artifact_id, check_type, score, passed, details_json)
audit_logs(id, actor_id, action, target_type, target_id, timestamp, prev_hash, hash)
approvals(id, task_step_id, requested_by, approver_id, status, comment, decided_at)
```

---

## 23. API Design (key endpoints)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/tasks` | POST | Create a new task |
| `/api/tasks/{id}` | GET | Get task status + trace |
| `/api/tasks/{id}/cancel` | POST | Cancel a running task |
| `/api/tasks/{id}/resume` | POST | Resume from persisted state |
| `/api/documents` | POST | Upload document(s) |
| `/api/documents` | GET | List documents |
| `/api/documents/{id}` | DELETE | Delete a document |
| `/api/tasks/{id}/artifacts` | GET | List/download generated artifacts |
| `/api/tasks/{id}/steps/{step_id}/approve` | POST | Approve a pending step |
| `/api/tasks/{id}/steps/{step_id}/reject` | POST | Reject a pending step |
| `/api/audit-logs` | GET | Query audit history |
| `/api/system/health` | GET | Health of all subsystems |
| `/ws/tasks/{id}` | WS | Live task trace stream (steps, model selection, tool calls) |

---

## 24. Repository Structure

```
kavach/
├── frontend/               # React app
├── backend/
│   ├── api/                # FastAPI routers
│   ├── auth/                
│   ├── orchestrator/       # planner, executor, validator, state machine
│   ├── routing/            # model registry + router
│   ├── models/             # model server clients
│   ├── tools/              # tool registry + individual tool modules
│   ├── rag/                # ingestion, chunking, retrieval
│   ├── vision/             # VLM integration
│   ├── ocr/                # OCR pipeline
│   ├── sandbox/            # docker sandbox manager
│   ├── validation/         # grounding/schema/calc validators
│   ├── artifacts/          # docx/xlsx/pptx/pdf generators
│   ├── security/           # RBAC, encryption, egress checks
│   ├── database/           # models, migrations, repositories
│   └── observability/      # metrics, health checks
├── configs/                # model registry yaml, routing rules
├── deployment/              # docker-compose.yml, k8s manifests
└── tests/                  # unit + integration tests per module
```

---

## 25. Performance (single workstation, mid-range GPU)

- **Quantization:** serve models at 4-bit/8-bit (AWQ/GPTQ/GGUF) to fit consumer GPU VRAM (e.g., 24GB).
- **Model loading/unloading:** lazy-load on first request per role; unload idle models after timeout to free VRAM.
- **VRAM management:** router checks `nvidia-smi` headroom before scheduling; queues tasks if insufficient.
- **Batching:** batch concurrent RAG/embedding requests.
- **Context management:** summarize/compress old turns via `compress_context()` to stay under model context limit.
- **Caching:** cache embeddings and repeated OCR results by file hash.
- **CPU fallback:** small classification/embedding models run on CPU when GPU is busy with generation.
- **Concurrency:** task queue (Celery/RQ) limits concurrent heavy-model tasks to what VRAM allows.

---

## 26. Evaluation Metrics

Task success rate, routing accuracy (% correct model chosen vs ground truth), RAG retrieval precision/recall, hallucination/grounding rate (unsupported-claim ratio), OCR accuracy (CER/WER), code execution success rate, artifact correctness (schema/calc pass rate), end-to-end latency, GPU/VRAM utilization, and a security check: verified zero-egress packet count during test runs.

**vs. generic single-model chatbot:** a single-model chatbot cannot reliably do OCR+vision+code+RAG with one model at acceptable quality/latency, produces no verifiable artifacts, has no validation loop (higher hallucination), and offers no sovereignty guarantees or audit trail — KAVACH's multi-model + validation-loop design should show materially higher grounding scores and artifact-correctness rates in side-by-side testing.

---

## 27. Patent / Innovation Angle (possible novelty areas, not a legal claim)

- Sovereignty-aware model routing (routing decisions that factor in data-classification level, not just performance).
- Validation-driven agent replanning loop tied to a quantitative grounding score.
- Multimodal agent orchestration that forces vision claims through a structured, bounding-box-grounded intermediate representation before reasoning (anti-hallucination-by-construction).
- Local tool authorization framework combining RBAC + data classification + risk level per tool call.
- Confidential artifact generation with cryptographic hash-chained audit trail across every model/tool touch.
- Hardware-aware, VRAM-budget-constrained model selection for air-gapped single-workstation deployment.

---

## 28. Final Feature Checklist (by module)

- **Orchestration:** task state machine, planner, executor, validator, replanner, human-approval gate
- **Models:** registry, router, multi-model serving, VRAM-aware scheduling
- **RAG:** ingestion, chunking, hybrid search, reranking, citations, versioning
- **Multimodal:** OCR, layout detection, VLM, P&ID entity/connection extraction
- **Tools:** file I/O, calculator, Python sandbox, DB query, document parsers, artifact generators
- **Artifacts:** DOCX/XLSX/PPTX/PDF/code/CSV/JSON generation + validation
- **Security:** RBAC, encryption, egress blocking, audit logging, prompt-injection defenses, model hash verification
- **Frontend:** chat/workbench, uploads, live trace, model/tool visibility, approvals, sovereignty status
- **Observability:** health checks, GPU/CPU metrics, latency tracking

---

## 29. Final Architecture Summary

- **Final architecture:** layered agentic system — UI → Gateway → Auth → Orchestrator (Plan/Execute/Validate/Replan) → Model Router → (LLM / Vision-OCR / RAG / Tools / Sandbox) → Artifact Generation → Validation → Audit, all inside an air-gapped network boundary.
- **Final tech stack:** React+FastAPI+PostgreSQL+Qdrant+vLLM/Ollama+PaddleOCR+Docker sandbox+Keycloak.
- **Six-member team:** Orchestration Lead, Model/Infra Engineer, RAG Engineer, Multimodal/Vision Engineer, Tools/Backend Engineer, Frontend/Security Engineer.
- **MVP:** OCR+RAG+2-model routing+plan/execute/validate loop+DOCX/XLSX generation+RBAC+audit+egress blocking.
- **Differentiators:** validation-driven agent loop, P&ID understanding, live sovereignty demo, model-routing transparency.
- **Demo flow:** scanned-report → SOP-grounded approval note (primary) + NL-to-verified-code (secondary).
- **Why it satisfies 26117:** it directly delivers every named capability in the problem statement — sovereignty, multimodality, open-weight multi-model use, agentic multi-step execution, local tools, and real generated deliverables — with a live, demonstrable proof of zero data egress.

**Gaps to fix in the original proposal:** (1) "automatically route tasks to the appropriate model" needs the explicit VRAM/latency-aware router in §4/§5E — build this early, it's often under-scoped; (2) "verified code" requires the sandbox validation loop in §10/§Q, not just code generation; (3) genuine sovereignty proof requires the live network-monitoring demo in §20, not just an architecture claim — schedule this rehearsal explicitly in Phase 10.

---

## 30. Implementation-Level Function Inventory

Legend for execution mode: **[S]**ynchronous, **[A]**sync, **[BW]**Background Worker, **[WS]**WebSocket event. **[REST]** = exposed via API; else internal-only.

### A. Frontend / Workbench (Owner: #6)
| Function | Purpose | Mode | Exposed |
|---|---|---|---|
| `create_task()` | Start new task session | A | REST (calls backend `create_task`) |
| `upload_file()` / `upload_multiple_files()` | Send files to backend | A | REST |
| `submit_prompt()` | Send user message | A | REST/WS |
| `display_task_status()` | Render state machine badge | WS | internal |
| `display_agent_steps()` | Render live trace | WS | internal |
| `display_model_selection()` | Show routing badge | WS | internal |
| `display_tool_execution()` | Show tool call details | WS | internal |
| `display_sources()` / `display_citations()` | Render RAG citations | WS | internal |
| `display_generated_artifacts()` / `download_artifact()` | Show/download files | S | REST |
| `approve_action()` / `reject_action()` / `request_revision()` | Human-in-loop controls | A | REST |
| `display_security_status()` / `display_network_status()` | Sovereignty badges | WS | internal |
| `display_audit_log()` | Audit viewer | S | REST |
| State store (Zustand slice) + `handleWSEvent()` | Frontend state mgmt | internal | — |

### B. API / Backend (Owner: #1, supported by all)
| Function | Route | Mode | 
|---|---|---|
| `create_task()` | `POST /api/tasks` | A [REST] |
| `get_task()` | `GET /api/tasks/{id}` | S [REST] |
| `cancel_task()` | `POST /api/tasks/{id}/cancel` | A [REST] |
| `resume_task()` | `POST /api/tasks/{id}/resume` | A [REST] |
| `submit_user_message()` | `POST /api/tasks/{id}/message` | A [REST] |
| `upload_document()` / `list_documents()` / `delete_document()` | `POST/GET/DELETE /api/documents` | A/S [REST] |
| `get_task_history()` | `GET /api/tasks/{id}/history` | S [REST] |
| `get_artifacts()` | `GET /api/tasks/{id}/artifacts` | S [REST] |
| `get_audit_logs()` | `GET /api/audit-logs` | S [REST] |
| `approve_task_step()` / `reject_task_step()` | `POST /api/.../approve|reject` | A [REST] |
| `get_system_health()` | `GET /api/system/health` | S [REST] |

### C. Task Understanding (Owner: #1)
`classify_task()`, `detect_task_type()`, `detect_required_modalities()`, `extract_task_requirements()`, `estimate_task_complexity()`, `estimate_context_size()`, `detect_sensitive_operation()`, `determine_required_tools()`, `determine_required_outputs()` — all **[S]**, internal, called synchronously at task creation using the small classifier model. Distinguishes: general reasoning, document analysis, summarization, coding, spreadsheet, calculation, RAG, image understanding, scanned PDF, engineering drawing, multimodal, artifact generation.

### D. Model Registry (Owner: #2)
`register_model()`, `unregister_model()`, `update_model()`, `get_model()`, `list_models()` **[S, REST-admin]**; `health_check_model()` **[BW]**; `load_model()`/`unload_model()` **[A]**; `get_model_capabilities()`, `get_model_resource_requirements()`, `get_available_models()` **[S, internal]**. Metadata schema: name, version, quantization, modality, context_length, vram_mb, capabilities[], latency_profile, quality_profile, local_path, status.

### E. Model Router (Owner: #2)
`route_task()` **[S]** — entry point called by orchestrator per step; `score_models()`, `select_best_model()`, `check_model_availability()`, `check_vram_capacity()`, `estimate_inference_cost()`, `estimate_latency()`, `fallback_model()` all **[S, internal]**; `route_multimodal_task()`, `route_coding_task()`, `route_document_task()`, `route_vision_task()`, `route_reasoning_task()` are thin wrappers around `route_task()` with task-type presets. Algorithm given in §4.

### F. Agent Orchestrator (Owner: #1)
`create_agent_task()`, `initialize_task_state()` **[A]**; `create_plan()`, `validate_plan()` **[S]**; `execute_plan()` **[BW]** (long-running); `execute_step()`, `select_tool()`, `call_tool()`, `observe_tool_result()`, `update_task_state()` **[A, internal, emits WS events]**; `detect_failure()`, `retry_step()`, `replan()` **[A]**; `finalize_task()`, `terminate_task()` **[A, REST-triggered]**. Implements PLAN→EXECUTE→OBSERVE→VALIDATE→REPLAN→EXECUTE→FINALIZE.

### G. Planner (Owner: #1)
`generate_plan()`, `decompose_task()`, `identify_dependencies()`, `order_steps()`, `estimate_step_cost()`, `identify_required_tools()`, `identify_required_models()`, `identify_validation_requirements()`, `create_execution_graph()` — all **[S, internal]**, called once per task/replan; returns a structured DAG object (list of step nodes with tool/model/dependency fields), not free text.

### H. Agent Memory/Context (Owner: #1)
`create_context()`, `add_message()`, `add_tool_result()`, `add_document_context()`, `add_retrieved_context()` **[S]**; `summarize_context()`, `compress_context()` **[A]** (calls reasoning model); `retrieve_relevant_memory()` **[S]**; `clear_task_context()`, `persist_task_state()`, `restore_task_state()` **[A, internal, backed by Postgres]**.

### I. Tool Registry (Owner: #5)
`register_tool()`, `unregister_tool()`, `get_tool()`, `list_tools()` **[S, admin REST]**; `check_tool_permission()`, `validate_tool_arguments()` **[S, internal]**; `execute_tool()` **[A]**; `log_tool_call()` **[A, internal → audit]**. Tool metadata: name, description, input/output schema, permissions, risk_level, allowed_roles, network_requirement, sandbox_requirement.

### J. File Tools (Owner: #5)
`read_file()`, `write_file()`, `copy_file()`, `move_file()`, `delete_file()`, `list_files()`, `inspect_file()`, `detect_file_type()`, `extract_metadata()`, `calculate_file_hash()` — all **[S, internal]**, path-allow-listed, support PDF/DOCX/XLSX/PPTX/TXT/CSV/JSON/images/code.

### K. Document Processing (Owner: #3/#5)
`parse_pdf()`, `parse_docx()`, `parse_xlsx()`, `parse_pptx()`, `extract_text()`, `extract_tables()`, `extract_images()`, `detect_document_structure()`, `detect_headings()`, `detect_pages()`, `normalize_document()`, `create_document_representation()` — **[S/A, internal]**, feed both RAG ingestion and task pipelines.

### L. OCR (Owner: #4)
`preprocess_image()`, `preprocess_pdf_page()`, `detect_text_regions()`, `run_ocr()`, `extract_handwritten_text()`, `extract_structured_text()`, `calculate_ocr_confidence()`, `flag_low_confidence_regions()` — **[A, internal]**, PaddleOCR-backed, output feeds Vision/Multimodal layer.

### M. Vision/Multimodal (Owner: #4)
`analyze_image()`, `analyze_document_page()`, `analyze_scanned_document()`, `analyze_engineering_drawing()`, `detect_objects()`, `detect_regions()`, `identify_diagram_components()`, `extract_visual_relationships()`, `combine_visual_and_textual_context()`, `generate_visual_evidence()` — **[A, internal]**. P&ID specifics: equipment ID, pipe/line ID, valve ID, tag extraction, instrument ID, connection extraction — flagged as best-effort, not engineering-certified accuracy, unless separately validated against ground truth.

### N–P. RAG / Vector DB / Embedding (Owner: #3)
`ingest_document()`, `preprocess_document()`, `chunk_document()` **[A]**; `generate_embeddings()`, `embed_text()`, `embed_document()`, `embed_query()` **[A]**; `store_chunks()`, `index_document()`, `create_collection()`, `insert_embedding()`, `batch_insert_embeddings()` **[BW]**; `search_documents()`, `semantic_search()`, `keyword_search()`, `hybrid_search()`, `search_embeddings()`, `filter_by_metadata()` **[S]**; `rerank_results()`, `rerank_documents()`, `calculate_similarity()`, `filter_low_relevance_results()` **[S]**; `retrieve_context()`, `build_context()`, `generate_citations()`, `verify_source()` **[S]**; `get_document_version()`, `update_document_index()`, `delete_embeddings()`, `delete_document_index()`, `update_embedding()` **[A, admin REST]**.

### Q. Coding Agent (Owner: #1/#5)
`analyze_code_request()`, `generate_code()` **[A]** (calls coding model); `inspect_repository()`, `create_code_file()`, `modify_code()` **[S, internal]**; `generate_tests()` **[A]**; `execute_tests()`, `capture_execution_output()` **[A, via sandbox]**; `detect_compile_error()`, `detect_runtime_error()`, `analyze_failure()`, `fix_code()`, `rerun_tests()`, `verify_code()`, `package_code_artifact()` **[A]**. Never executes on host — always via §R sandbox.

### R. Code Sandbox (Owner: #5)
`create_sandbox()`, `configure_sandbox()`, `copy_input_files()` **[A]**; `execute_code()`, `execute_tests()` **[BW]**; `enforce_timeout()`, `enforce_memory_limit()`, `enforce_cpu_limit()`, `disable_network()` **[internal config, applied at container creation]**; `capture_stdout()`, `capture_stderr()`, `collect_output_files()` **[A]**; `destroy_sandbox()` **[A]**. Host protection: ephemeral container + explicit whitelisted file copy-in only, `--network none`, read-only rootfs — no path to confidential document store ever mounted.

### S. Python/Calculation Tool (Owner: #5)
`execute_python()`, `execute_calculation()` **[A, sandboxed]**; `validate_expression()`, `generate_calculation_steps()`, `verify_calculation()`, `compare_expected_result()`, `generate_calculation_report()` **[S, internal]**.

### T. Spreadsheet Agent (Owner: #5)
`read_workbook()`, `inspect_sheet()`, `read_cells()` **[S]**; `write_cells()`, `create_sheet()`, `create_formula()`, `calculate_formula()`, `generate_chart()` **[A]**; `validate_workbook()`, `detect_formula_errors()`, `save_workbook()` **[A]**.

### U. Artifact Generation (Owner: #5)
`create_docx()`, `create_xlsx()`, `create_pptx()`, `create_pdf()`, `create_csv()`, `create_json()`, `create_report()` **[A]**; `add_table()`, `add_image()`, `add_heading()`, `add_citations()`, `add_calculation_steps()`, `apply_template()` **[S, internal helpers]**; `save_artifact()`, `calculate_artifact_hash()` **[A]**.

### V. Artifact Validation (Owner: #5)
`validate_docx()`, `validate_xlsx()`, `validate_pptx()`, `validate_pdf()`, `validate_json()`, `validate_csv()`, `validate_file_integrity()`, `validate_required_sections()`, `validate_citations()`, `validate_calculations()`, `validate_artifact_schema()` — all **[A, internal]**, triggered right after generation.

### W. Validation/Grounding Engine (Owner: #1/#3)
`validate_answer()`, `validate_claims()`, `extract_claims()`, `verify_claim_against_sources()`, `calculate_grounding_score()`, `detect_unsupported_claims()`, `detect_hallucination_risk()`, `validate_tool_results()`, `validate_calculations()`, `validate_output_requirements()`, `generate_validation_report()` — **[A, internal]**. Grounding score threshold ≥0.9 to pass (see §12); below triggers `replan()`.

### X. Security Engine (Owner: #6)
`authenticate_user()`, `authorize_user()`, `check_role_permission()` **[S, REST via Keycloak]**; `classify_data()`, `classify_task_risk()` **[S, internal]**; `authorize_tool()`, `authorize_file_access()` **[S, internal]**; `sanitize_input()`, `detect_prompt_injection()`, `detect_malicious_file()` **[A]**; `validate_model_source()`, `verify_model_hash()` **[S, at startup]**; `encrypt_file()`, `decrypt_file()` **[A]**; `create_audit_event()` **[A]**; `block_unauthorized_action()` **[S]**.

### Y. Network Sovereignty (Owner: #6)
`check_network_status()`, `detect_external_connection()`, `block_external_connection()`, `verify_no_egress()` **[BW, polling]**; `monitor_network_events()`, `log_network_attempt()` **[BW]**; `generate_sovereignty_report()` **[S, REST]**. Drives the "LOCAL ONLY / AIR-GAPPED / NO EXTERNAL CONNECTIONS" UI badge via WS.

### Z. Audit/Logging (Owner: #6)
`log_task()`, `log_agent_step()`, `log_model_selection()`, `log_model_execution()`, `log_tool_call()`, `log_file_access()`, `log_document_retrieval()`, `log_validation()`, `log_approval()`, `log_security_event()`, `log_network_event()` — all **[A, fire-and-forget]**; `get_audit_history()`, `export_audit_report()` **[S, REST]**.

### AA. Human-in-the-Loop (Owner: #1/#6)
`create_approval_request()` **[A]**; `get_pending_approvals()` **[S, REST]**; `approve_request()`, `reject_request()`, `request_modification()` **[A, REST]**; `resume_after_approval()` **[A, internal]**; `record_approval()` **[A, internal → audit]**. Required for: finalizing an approval-note artifact, any file overwrite/delete, any HIGH-risk-classified tool call.

### AB. Task State Machine (Owner: #1)
States: CREATED, CLASSIFIED, PLANNED, WAITING_FOR_APPROVAL, EXECUTING, VALIDATING, RETRYING, COMPLETED, FAILED, CANCELLED. Functions: `transition_task_state()`, `validate_state_transition()` **[S, internal]**; `get_task_state()` **[S, REST]**; `recover_task()` **[A, on restart]**.

### AC. Database (Owner: #5, all contribute repositories)
`create_user()`, `create_role()`, `create_task_record()`, `create_task_step()`, `create_document_record()`, `create_chunk_record()`, `create_tool_call_record()`, `create_artifact_record()`, `create_validation_record()`, `create_audit_record()`, `create_approval_record()`, `update_task_record()`, `retrieve_task_history()` — all **[S/A, internal repository layer]**, one repository class per table, SQLAlchemy-based.

### AD/AE. Observability & Health (Owner: #6)
`collect_cpu_metrics()`, `collect_gpu_metrics()`, `collect_vram_metrics()`, `collect_model_latency()`, `collect_task_latency()`, `collect_tool_latency()`, `collect_error_metrics()` **[BW]**; `get_system_health()`, `generate_performance_report()` **[S, REST]**; `health_check()`, `readiness_check()`, `liveness_check()`, `check_gpu()`, `check_model_server()`, `check_database()`, `check_vector_database()`, `check_ocr_engine()`, `check_sandbox()`, `check_storage()` **[S, REST /health]**.

### AF. Multimodal End-to-End Pipeline (Owner: #4, integrates #1/#3)
`process_multimodal_task()` **[BW]** — orchestrates: file classification → PDF/image preprocessing → OCR → visual analysis → text extraction → document structure extraction → RAG retrieval → context fusion → model routing → reasoning → tool execution → validation → artifact generation → artifact validation → final response.

### AG. Master Orchestration (Owner: #1, calling into every module)
```
process_user_request()
   → route_request()          [F/E]
   → create_plan()            [G]
   → execute_agent()          [F: execute_plan→execute_step→call_tool/route_task]
   → validate_result()        [W]
   → generate_artifacts()     [U]
   → validate artifacts       [V]
   → request_human_approval() [AA]  (if sensitivity flag set)
   → finalize_task()          [F/AB]
```
All internal state transitions emit `log_*` calls (Z) and WS events (A) so the frontend trace updates live.

---

## Team-of-6 Function Ownership Matrix

| Member | Modules Owned | Interfaces Exposed to Others |
|---|---|---|
| **#1 Orchestration Lead** | F (Orchestrator), G (Planner), H (Memory), AB (State Machine), W (co-owns Validation), AG (Master Orchestration) | `execute_plan()`, `route_task()` call contract, `validate_result()` call contract, WS event schema |
| **#2 Model/Infra Engineer** | D (Model Registry), E (Model Router), LLM serving | `route_task(step) -> model_handle`, `get_model_capabilities()` |
| **#3 RAG/Knowledge Engineer** | N, O, P (RAG, Vector DB, Embedding/Reranking), co-owns K (Document Processing) | `retrieve_context(query) -> chunks+citations`, `ingest_document(doc)` |
| **#4 Multimodal/Vision Engineer** | L (OCR), M (Vision), AF (Multimodal Pipeline) | `process_multimodal_task(files) -> structured_representation` |
| **#5 Tools/Backend Engineer** | I, J (Tool Registry, File Tools), Q, R, S, T (Coding Agent, Sandbox, Calc, Spreadsheet), U, V (Artifact Gen/Validation), AC (Database) | `execute_tool(name,args) -> result`, `create_docx/xlsx/pptx/pdf(content) -> artifact` |
| **#6 Frontend/Security Engineer** | Frontend (A), X (Security), Y (Network Sovereignty), Z (Audit), AA (co-owns Human-in-loop), AD/AE (Observability) | REST/WS contracts to frontend, `authorize_tool()`, `create_audit_event()` |

This inventory is granular enough that all six members can immediately scaffold their module's files, define the listed function signatures as interfaces/stubs, write unit tests against the input/output contracts above, and begin parallel implementation from Phase 0 onward.
