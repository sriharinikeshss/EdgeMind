# KAVACH — Phase-by-Phase Implementation Plan
### With Independent, Parallelizable Work for Each of the 6 Team Members

Team roster used throughout:
- **M1 — Orchestration Lead** (agent loop, planner, state machine)
- **M2 — Model/Infra Engineer** (model serving, router, VRAM)
- **M3 — RAG/Knowledge Engineer** (ingestion, embeddings, vector search)
- **M4 — Multimodal/Vision Engineer** (OCR, vision, P&ID)
- **M5 — Tools/Backend Engineer** (tools, sandbox, artifacts, DB)
- **M6 — Frontend/Security Engineer** (UI, auth, audit, network sovereignty)

Each phase below gives: **Goal**, **What to do**, **How to do it (concrete steps)**, **Per-member independent tasks**, **Integration point**, and **Definition of Done (DoD)**. Members work in parallel inside a phase and only sync at the integration point at the end of the phase.

---

## PHASE 0 — Foundation & Setup

**Goal:** Everyone can run the full (empty) stack locally and push code without blocking each other.

**What to do:** Stand up the repo skeleton, Docker Compose environment, CI, and stub services for every layer so all six people have a place to write code from day one.

**How to do it:**
1. Create the monorepo with the folder structure from the architecture doc (`frontend/`, `backend/{api,orchestrator,routing,models,tools,rag,vision,ocr,sandbox,validation,artifacts,security,database,observability}/`, `configs/`, `deployment/`, `tests/`).
2. Write `docker-compose.yml` with placeholder containers: `postgres`, `qdrant`, `minio`, `backend` (FastAPI skeleton returning `{status:"ok"}`), `frontend` (React skeleton).
3. Set up GitHub Actions (or local pre-commit) running `lint + test` on every push.
4. Define shared contracts up front: `task.schema.json`, `tool.schema.json`, `model.schema.json`, `artifact.schema.json` — these are the interface contracts every module will honor.
5. Each member creates their module folder with a `README.md` stating what functions they own (from the ownership matrix) and stub function signatures (raise `NotImplementedError`).

**Per-member independent tasks:**
- **M1:** Scaffold `backend/orchestrator/` with empty classes `Planner`, `Executor`, `Validator`, `TaskStateMachine`; write the state enum from §AB.
- **M2:** Stand up Ollama or vLLM container with one small model (e.g., a 7B model) just to prove local inference works end-to-end; write `models/registry.py` stub.
- **M3:** Stand up Qdrant container; write `rag/ingest.py` stub and a "hello world" ingest+search script against one dummy PDF.
- **M4:** Install PaddleOCR/Tesseract locally; run OCR on one sample scanned image to confirm the pipeline dependency works.
- **M5:** Scaffold `tools/registry.py`, `sandbox/manager.py`, `artifacts/docx_writer.py` stubs; get Docker sandbox spinning a "hello world" container with `--network none`.
- **M6:** Scaffold React app with routing, a login page (dummy), and Keycloak (or JWT-stub) container running.

**Integration point:** All six containers boot via one `docker-compose up`; a shared `/health` endpoint returns green for every stub service.

**DoD:** Repo cloned fresh → `docker-compose up` → all services healthy → CI passing → schemas committed and reviewed by all six.

---

## PHASE 1 — Basic Local LLM Chat (No Routing Yet)

**Goal:** Prove sovereign, local-only LLM inference works, end-to-end, through the real UI — the "smallest complete vertical slice."

**What to do:** Wire one model, one API endpoint, one chat UI panel together, with zero external network calls.

**How to do it:**
1. M2 serves one reasoning model locally (vLLM/Ollama) exposing an OpenAI-compatible local endpoint.
2. M1 builds `POST /api/tasks` → creates a task row → calls the model directly (no router yet) → returns the text response.
3. M6 wires the chat UI to call that endpoint and render streaming/plain text response.
4. M5 adds `create_task_record()` / `update_task_record()` repository functions against Postgres.
5. Confirm via packet capture (`tcpdump`) that no request leaves the host during a chat call.

**Per-member independent tasks:**
- **M1:** Implement bare task creation + single synchronous "call model, store, return" flow; no planner yet.
- **M2:** Get the model server stable, measure baseline latency/VRAM, document quantization used.
- **M3:** In parallel, start real RAG groundwork: build the document chunker (`chunk_document()`) against dummy text, independent of the chat flow.
- **M4:** In parallel, build the OCR preprocessing function (`preprocess_pdf_page()`, `preprocess_image()`) and test on 5 sample scans, independent of chat flow.
- **M5:** Build the Postgres schema migrations for `users`, `tasks`, `task_steps`, `artifacts` (full schema from §22), independent of chat flow.
- **M6:** Build login (Keycloak/JWT), the chat panel, and a basic egress-monitoring script (`tcpdump` wrapper) that will be reused in Phase 9's sovereignty demo.

**Integration point:** A user logs in, types a message, gets a real local-model response, and it's persisted in Postgres and visible in the UI.

**DoD:** End-to-end chat works through the UI; zero external packets observed; task row correctly persisted with status COMPLETED.

---

## PHASE 2 — Model Registry & Router (Multi-Model)

**Goal:** Add a second model (coding model) and prove the router auto-selects the correct one per task type.

**What to do:** Build the model registry with metadata, the router's scoring algorithm, and a visible "which model was used" signal.

**How to do it:**
1. M2 registers ≥2 models in `models/registry.py` with the metadata schema (modality, VRAM, capabilities, latency/quality profile).
2. M2 implements `route_task()`, `score_models()`, `select_best_model()`, `check_vram_capacity()` per the algorithm in §4/§5E.
3. M1 hooks the router into the task-creation flow: after `classify_task()` (simple heuristic/keyword classifier for now, upgrade in Phase 3), call `route_task()` before invoking the model.
4. M6 adds the "Selected Model" badge to the UI, fed by a new field returned in the task response / WS event.
5. M5 adds `log_model_selection()` writing to `tool_calls`/`audit_logs` so routing is auditable.

**Per-member independent tasks:**
- **M2:** Build registry + router + VRAM check; write unit tests with mocked VRAM values to prove routing logic (independent of real GPU).
- **M1:** Build a minimal rule-based `classify_task()` (regex/keyword: "code"→coding, else→reasoning) to feed the router; this is throwaway and gets replaced in Phase 3.
- **M3:** Continue RAG build: implement `generate_embeddings()` + `store_chunks()` against Qdrant (still not wired to chat).
- **M4:** Continue vision/OCR build: implement `run_ocr()` + `calculate_ocr_confidence()` and validate accuracy against a labeled sample set.
- **M5:** Implement `model_routes` table + repository functions; build the first real tool: `execute_python()` in a bare (not-yet-hardened) subprocess, to be moved into the sandbox in Phase 4.
- **M6:** Build the model badge UI component and the WS event contract (`model_selected` event) that M1/M2 will emit to.

**Integration point:** Submitting a coding prompt routes to the coding model; a normal prompt routes to the reasoning model; UI badge reflects this correctly both times.

**DoD:** ≥95% correct routing on a 20-prompt manual test set (10 coding, 10 general); routing decision logged and visible in UI and audit log.

---

## PHASE 3 — Agent Core (Planner → Executor → Validator Loop)

**Goal:** Replace the single-shot call with a real multi-step agent loop, even if it only has 1–2 trivial tools so far.

**What to do:** Implement the state machine, planner (produces a structured step graph), executor (walks the graph), and a minimal validator (schema/format check only, richer checks come in Phase 8).

**How to do it:**
1. M1 implements `TaskStateMachine` transitions (CREATED→CLASSIFIED→PLANNED→EXECUTING→VALIDATING→COMPLETED/FAILED), persisted via `persist_task_state()`/`restore_task_state()`.
2. M1 implements `generate_plan()`/`decompose_task()`/`create_execution_graph()` — for now the planner can call the reasoning model with a "produce a JSON step plan" prompt, parsed into the DAG object.
3. M1 implements `execute_plan()`/`execute_step()`/`observe_tool_result()`/`update_task_state()`, calling into whatever tools exist (Phase 4 will expand these).
4. M1 implements a minimal `validate_answer()` (e.g., "is output non-empty and matches expected schema") — placeholder for the real Validator engine.
5. M6 adds the live "Agent Execution Trace" panel via WS events emitted at each state transition.
6. M5 adds `task_steps` write-through so every step is durably recorded.

**Per-member independent tasks:**
- **M1:** Build planner/executor/state machine/minimal validator — this phase's critical path.
- **M2:** In parallel, harden the router: add `estimate_latency()`, `fallback_model()`, and a queueing mechanism for when VRAM is insufficient (needed once multi-step tasks call the model repeatedly).
- **M3:** Wire RAG into a standalone retrieval API (`POST /api/rag/search`) that doesn't yet depend on the agent loop, so it can be tested independently and later becomes a "tool."
- **M4:** Wire OCR+vision into a standalone `/api/vision/analyze` endpoint, same independent-testability rationale.
- **M5:** Build out `tool_calls` table + `log_tool_call()`, and formalize the Tool Registry (`register_tool()`, `check_tool_permission()`, `execute_tool()`) so M1's executor has a real interface to call into (even if only 1–2 tools registered so far).
- **M6:** Build the live trace UI (step list, expand/collapse, status icons) driven by WS events from M1.

**Integration point:** A multi-step prompt (e.g., "summarize this text, then list 3 action items") produces a visible plan with 2+ steps, each executed and shown live in the UI, ending in COMPLETED.

**DoD:** Agent completes a 3+ step synthetic task end-to-end with full state-machine trace persisted and rendered live; a forced tool failure correctly transitions to RETRYING then FAILED (test this explicitly).

---

## PHASE 4 — Tool Layer (Real Tools, Registered & Authorized)

**Goal:** Give the agent a real, permission-checked toolbox: file I/O, calculator, sandboxed Python, DB query.

**What to do:** Formalize tool registration with schemas/permissions, and wire the executor to call real tools instead of placeholders.

**How to do it:**
1. M5 implements `register_tool()` for each tool with input/output JSON schema, `risk_level`, `allowed_roles`.
2. M5 implements the sandbox properly: `create_sandbox()`, resource limits, `--network none`, `destroy_sandbox()` (per §10) — moves `execute_python()` here from Phase 2's bare version.
3. M1's executor calls `select_tool()` → `check_tool_permission()` → `execute_tool()` → `observe_tool_result()`, feeding results back into context.
4. M6 adds the "authorize_tool" RBAC check hook (calls into M6's Security Engine) so risky tools require the right role.
5. M5 adds `validate_tool_arguments()` so malformed LLM-produced tool calls are rejected before execution, not after.

**Per-member independent tasks:**
- **M5:** Harden the sandbox, register ≥5 tools (file reader/writer, calculator, Python exec, DB query stub, JSON/CSV tool) — critical path this phase.
- **M1:** Wire executor to the real Tool Registry interface; add retry logic (`retry_step()`) when a tool call fails validation.
- **M2:** Add model-serving resilience: health checks (`health_check_model()`), auto-restart on crash, since tool-calling tasks will run longer and hit the model server more.
- **M3:** Continue building the full RAG pipeline: chunking strategy refinement, metadata schema, start hybrid search (BM25 + vector) — still as an independent API, will merge in Phase 6.
- **M4:** Continue vision pipeline: layout detection integration (LayoutParser/DocLayNet), structured JSON output format finalized — independent API, merges in Phase 5.
- **M6:** Implement `authorize_tool()`/`check_role_permission()` in the Security Engine and RBAC roles (Admin/Approver/Operator/Viewer) in Keycloak; expose this as a function M5's tool registry calls.

**Integration point:** Agent handles "calculate the average of these 5 numbers using Python, then save the result to a text file" — spanning calculator/sandbox/file-write tools, each permission-checked and logged.

**DoD:** ≥5 tools registered and callable by the agent; a permission-denied case is demonstrated (Viewer role blocked from a write tool); all tool calls appear in `tool_calls` table and audit log.

---

## PHASE 5 — Multimodal Pipeline (OCR + Vision Integration)

**Goal:** Merge M4's standalone OCR/vision API into the actual agent pipeline as a first-class tool/step type.

**What to do:** Register vision/OCR as tools, add file-type detection to route images/scans to the right pipeline, and enforce the anti-hallucination rule (structured extraction before reasoning).

**How to do it:**
1. M4 finalizes `process_multimodal_task()` skeleton: file classification → preprocessing → OCR → layout/vision → structured JSON.
2. M5 registers `analyze_scanned_document`, `analyze_engineering_drawing`, `run_ocr` as tools in the Tool Registry (with `sandbox_requirement=false`, `network_requirement=false`).
3. M1's planner learns to insert an OCR/vision step whenever `detect_required_modalities()` (from Task Understanding, M1) flags image/scan input.
4. M4 implements confidence flagging (`flag_low_confidence_regions()`) and ensures the reasoning model is only ever given the structured JSON, never the raw ambiguous image directly.
5. M6 adds a "visual evidence" UI element — clicking a claim highlights the source bounding box/region.

**Per-member independent tasks:**
- **M4:** Deliver the full scanned-document and P&ID pipelines — critical path.
- **M1:** Extend `detect_required_modalities()`/`extract_task_requirements()` (Task Understanding) to correctly branch plans for image/scan inputs.
- **M2:** Register the vision-language model (e.g., Qwen2-VL) in the Model Registry and extend the router's `route_vision_task()`.
- **M3:** In parallel, finish hybrid search + reranking (`hybrid_search()`, `rerank_results()`) so RAG is feature-complete ahead of Phase 6 integration.
- **M5:** Add artifact "visual evidence" export helper (`generate_visual_evidence()` support: crop + attach region image to artifacts).
- **M6:** Build the bounding-box highlight/citation-click UI component, and the file-type-aware upload flow (image vs PDF vs docx icons/handling).

**Integration point:** Upload a scanned inspection report → agent auto-detects modality → runs OCR/vision as a step → produces a grounded summary with clickable visual evidence, with low-confidence regions clearly flagged.

**DoD:** A scanned document and a P&ID/photo both produce structured, source-grounded answers; low-confidence OCR regions are visibly flagged in UI; zero unflagged hallucinated visual claims in a 5-sample manual review.

---

## PHASE 6 — RAG Integration (Knowledge-Grounded Answers)

**Goal:** Merge M3's standalone RAG API into the agent as a first-class retrieval tool with citations.

**What to do:** Register RAG retrieval as a tool, wire citation objects through to the artifact/response layer, and add document versioning.

**How to do it:**
1. M5 registers `rag.retrieve_context` as a tool (`network_requirement=false`).
2. M1's planner adds a retrieval step whenever `determine_required_tools()` flags a knowledge/RAG task type.
3. M3 finalizes `generate_citations()`/`verify_source()` so every retrieved chunk carries doc_id/page/hash metadata all the way through to the final answer.
4. M3 implements document versioning (`get_document_version()`, `update_document_index()`) so re-uploaded SOPs supersede old chunks without deleting audit history.
5. M6 renders citations as clickable chips linking back to the source document viewer.

**Per-member independent tasks:**
- **M3:** Deliver full RAG-as-a-tool integration with citations and versioning — critical path.
- **M1:** Extend planner to combine RAG + reasoning steps (e.g., "retrieve SOP, then compare against findings") in one plan.
- **M2:** Tune embedding/reranker model serving (BGE-M3, BGE-Reranker) for latency; add them to the registry as their own "modality: embedding/rerank" model types.
- **M4:** Start wiring the cross-modal case: findings extracted from a scanned report (Phase 5 output) feeding into a RAG query (Phase 6) — build the `combine_visual_and_textual_context()` bridge.
- **M5:** Build a document upload → ingestion pipeline trigger (`ingest_document()` called automatically on upload) and the document management UI's backend endpoints (`list_documents`, `delete_document`).
- **M6:** Build the document library UI (upload, list, version history, delete) and the citation-chip component with source-document preview.

**Integration point:** "What does the SOP say about valve pressure limits, and does this scanned report's finding violate it?" → RAG retrieves SOP clause + OCR/vision extracts the finding → reasoning model compares both, with citations to both sources.

**DoD:** A RAG-grounded, citation-annotated answer is produced and verified correct in a 10-question test set (≥90% citation accuracy); document re-upload correctly versions instead of duplicating.

---

## PHASE 7 — Artifact Generation

**Goal:** The agent can end a task by producing real downloadable files (DOCX/XLSX/PPTX/PDF/code), not just chat text.

**What to do:** Implement the artifact writers, register them as tools, and wire the executor to call them as the final step(s) of relevant plans.

**How to do it:**
1. M5 implements `create_docx()`, `create_xlsx()`, `create_pptx()`, `create_pdf()`, `create_csv()`, `create_json()` plus helpers (`add_table()`, `add_heading()`, `add_citations()`, `apply_template()`).
2. M5 implements `save_artifact()`/`calculate_artifact_hash()` and the `artifacts` table wiring.
3. M1's planner adds an "artifact generation" step type whenever `determine_required_outputs()` flags a deliverable request ("draft an approval note", "generate a report").
4. M6 builds the artifact download card (filename, type icon, hash, download button) in the UI, fed by a new `artifact_created` WS event.
5. M4 contributes the template for embedding visual-evidence crops into DOCX artifacts (from Phase 5's bounding-box exports).

**Per-member independent tasks:**
- **M5:** Deliver all artifact writers + hashing + storage — critical path.
- **M1:** Wire "artifact generation" as a plan step type with proper dependency ordering (must come after reasoning/RAG/calc steps it depends on).
- **M2:** Optimize model server for longer-context "drafting" calls typical of report generation (larger max_tokens configs, streaming support).
- **M3:** Add `add_citations()` integration so RAG citations flow automatically into generated DOCX/report artifacts.
- **M4:** Build the visual-evidence-to-DOCX embedding helper.
- **M6:** Build the artifact card UI + download flow + artifact list panel per task.

**Integration point:** "Summarize this SOP and generate a DOCX report with citations" → agent retrieves, reasons, generates DOCX, and the UI shows a downloadable, hash-stamped file.

**DoD:** DOCX, XLSX, and at least one more format (PPTX or PDF) each successfully generated, downloaded, and manually opened without corruption in a test run; artifact hash reproducibly verifies file integrity.

---

## PHASE 8 — Validation Engine (Grounding, Calculation, Schema)

**Goal:** Replace Phase 3's placeholder validator with the real grounding/calculation/schema validation engine, wired to trigger automatic replanning.

**What to do:** Implement claim extraction, source verification, calculation re-checking, and artifact-specific validators; wire failures to `replan()`.

**How to do it:**
1. M1/M3 jointly implement `extract_claims()`, `verify_claim_against_sources()`, `calculate_grounding_score()`, `detect_unsupported_claims()` — using RAG citation metadata as ground truth.
2. M5 implements artifact-specific validators: `validate_docx()`, `validate_xlsx()` (formula error detection), `validate_required_sections()`, `validate_file_integrity()`.
3. M5/M1 implement `validate_calculations()` by independently re-running the calculation in the sandbox and diffing against the stated result.
4. M1 wires validator output into the state machine: score < threshold (e.g. 0.9) → `replan()` with the specific failing claims fed back as correction instructions; bounded to 3 retries.
5. M6 adds a "Validation Report" panel showing grounding score, per-check pass/fail, and retry count.

**Per-member independent tasks:**
- **M1:** Wire validator-to-replanner control flow and retry bounding — critical path.
- **M3:** Implement claim-to-source verification logic (semantic matching between claim text and retrieved chunk).
- **M4:** Extend validation to visual claims: verify every visual claim references a valid bounding-box/region ID from Phase 5's extraction (`detect_hallucination_risk()` for vision).
- **M5:** Implement all artifact-format validators + the independent calculation re-checker in the sandbox.
- **M2:** Add a "validator model" option — optionally use a separate, smaller local model as an LLM-judge for grounding checks, registered like any other model.
- **M6:** Build the validation report UI and the retry-count/iteration indicator in the live trace.

**Integration point:** Deliberately feed the agent a task where a plausible-but-wrong number is likely (e.g., ambiguous OCR); confirm the validator catches it, forces a retry, and either fixes it or escalates to human review after 3 attempts.

**DoD:** Grounding score computed and displayed for every completed task; a forced-failure test shows automatic replanning occurring and either resolving or correctly escalating; no artifact reaches "COMPLETED" status without passing its format-specific validator.

---

## PHASE 9 — Security & Sovereignty Hardening

**Goal:** Lock down the system so it demonstrably deserves the word "sovereign": RBAC, encryption, egress blocking, audit trail, prompt-injection defenses, model hash verification.

**What to do:** Harden every access path, finish the audit log, implement network monitoring, and prepare the live no-egress proof.

**How to do it:**
1. M6 finalizes RBAC roles/permissions across every API route and tool-authorization check (no route should be reachable without a role check).
2. M6 implements `encrypt_file()`/`decrypt_file()` for documents/artifacts at rest (AES-256 on MinIO volumes).
3. M6 implements `detect_prompt_injection()` (pattern/heuristic + content-type tagging of untrusted document text so it can't be mistaken for system instructions) and `sanitize_input()`.
4. M6 implements `validate_model_source()`/`verify_model_hash()` — SHA-256 checks against a signed manifest, run at model load time (M2 integrates this into `load_model()`).
5. M6 implements the firewall/`iptables` default-deny egress policy at the host/container level, plus `verify_no_egress()`/`monitor_network_events()`/`generate_sovereignty_report()`, and the live "Sovereignty Status" badge.
6. M5 finishes the full audit log (`log_*` functions, hash-chained `audit_logs` table) covering every model call, tool call, file access, and approval.

**Per-member independent tasks:**
- **M6:** Deliver RBAC, encryption, prompt-injection defenses, network sovereignty monitoring, and the Sovereignty Status UI — critical path.
- **M5:** Finish audit log hash-chaining and `export_audit_report()`; add file-isolation checks (per-task working directories, no cross-task file access).
- **M2:** Integrate model hash verification into the load path; add a startup check that refuses to serve an unverified model.
- **M1:** Wire `detect_sensitive_operation()` (Task Understanding) to force the human-approval gate for HIGH-risk actions (finalize approval note, overwrite/delete file).
- **M3:** Add data-classification tagging to documents/chunks so RAG retrieval respects classification-based access control.
- **M4:** Add a check that vision/OCR services never call any external API (verify no cloud OCR/vision fallback exists anywhere in the code path) — audit the vision module explicitly.

**Integration point:** Run the full Wireshark/`iptables`/cable-pull test from §20 while executing a real multi-step task; verify RBAC blocks an unauthorized role from an approval action; verify a tampered/unverified model fails to load.

**DoD:** Zero external packets during a full task run (verified on camera/screen-recording for later demo use); RBAC negative test passes; sovereignty report exports cleanly; audit log is complete and hash-chain-verifiable.

---

## PHASE 10 — Integration, Polish & Demo Rehearsal

**Goal:** Everything works together reliably, twice, live, in front of judges.

**What to do:** Full end-to-end runs of both demo scenarios, UI polish, performance tuning, and rehearsal with contingency plans.

**How to do it:**
1. Run Demo 1 (scanned inspection report + SOP + P&ID → approval note) and Demo 2 (NL coding request → sandboxed, verified code) at least 5 times each, fixing any flakiness.
2. Tune performance (quantization levels, VRAM headroom, caching) per §25 so demo latency is acceptable on the actual demo hardware.
3. Polish UI: consistent loading states, error messages, and make sure the model badge / trace / citations / sovereignty status are all visually clear to a judge glancing at the screen.
4. Prepare the live sovereignty proof script (packet capture window, firewall rule display, network cable-pull moment) as a rehearsed, timed segment.
5. Write a one-page judge handout mapping each MRPL 26117 requirement to the specific feature/screen that satisfies it.

**Per-member independent tasks:**
- **M1:** Stress-test the agent loop across both demo scenarios; fix any state-machine edge cases (e.g., approval timeout handling).
- **M2:** Final VRAM/performance tuning on the actual demo GPU; confirm model swap/load timing doesn't stall the demo.
- **M3:** Curate and pre-ingest the actual demo SOP/knowledge documents; verify retrieval quality on the exact demo queries.
- **M4:** Curate and test the actual demo scanned report + P&ID images; ensure OCR/vision confidence is high on these specific files (pre-validate, don't discover issues live).
- **M5:** Final artifact template polish (approval note DOCX layout, code artifact packaging) so generated files look professional.
- **M6:** Finalize UI polish, rehearse the sovereignty demo (packet capture, firewall dump, cable pull), and prepare the judge hand-out.

**Integration point:** Full dry-run in front of the whole team acting as mock judges; time it; identify and fix the weakest link.

**DoD:** Both demo scenarios complete successfully twice in a row without manual intervention; sovereignty proof is rehearsed and reliable; every MRPL 26117 requirement has a visible, demonstrable feature mapped to it.

---

## Cross-Phase Parallelism Summary

At almost every phase, each member has a **critical-path task for that phase** plus **1–2 forward-looking tasks** that get consumed in a later phase — this is what keeps all six people busy simultaneously instead of waiting on each other:

| Phase | M1 (Orchestration) | M2 (Model/Infra) | M3 (RAG) | M4 (Multimodal) | M5 (Tools/Backend) | M6 (Frontend/Security) |
|---|---|---|---|---|---|---|
| 0 | Scaffold state machine | Stand up 1 model | Stand up Qdrant | OCR smoke test | Sandbox smoke test | Login + React shell |
| 1 | Bare task flow | Serve model, baseline latency | Chunker (standalone) | Preprocessing fns (standalone) | Full DB schema | Chat UI + login |
| 2 | Rule-based classifier | Registry + router | Embeddings→Qdrant | OCR accuracy pass | model_routes table | Model badge UI |
| 3 | **Planner/Executor/SM (critical)** | Router hardening | RAG API (standalone) | Vision API (standalone) | Tool registry interface | Live trace UI |
| 4 | Executor→real tools | Model server resilience | Hybrid search build | Layout detection | **Sandbox+tools (critical)** | RBAC hooks |
| 5 | Modality-aware planning | Vision model registration | Reranking finish | **OCR/Vision merge (critical)** | Visual-evidence export | BBox highlight UI |
| 6 | Combined RAG+reasoning plans | Embedding/rerank tuning | **RAG-as-tool (critical)** | Cross-modal bridge | Ingestion triggers | Doc library UI |
| 7 | Artifact step type | Long-context tuning | Citations→artifacts | Visual evidence→DOCX | **Artifact writers (critical)** | Artifact card UI |
| 8 | **Validator→replan wiring (critical)** | LLM-judge model option | Claim verification | Visual hallucination check | Artifact/calc validators | Validation report UI |
| 9 | Sensitive-op approval gate | Model hash verification | Data classification tags | Vision egress audit | Audit log hash-chain | **RBAC/egress/encryption (critical)** |
| 10 | Agent stress test | Perf tuning | Demo content curation | Demo content curation | Artifact polish | Demo/UI rehearsal |

This table can be pasted directly into your sprint board — each row is one sprint, each cell is one person's ticket for that sprint, and every phase ends with a stated integration point everyone must sync on before moving forward.
