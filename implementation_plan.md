# Cryptographic Audit Trail Implementation Plan

This document outlines the end-to-end technical implementation plan for the KAVACH Cryptographic Audit Trail feature. The UI is currently in place, but the backend implementation requires a tamper-evident, hash-chained logging mechanism to ensure sovereignty and compliance.

## User Review Required

> [!IMPORTANT]
> The audit trail is a critical compliance component. Please review the hashing strategy (SHA-256 hash chaining) and database schema to ensure it meets the air-gapped sovereignty requirements. Let me know if you approve this approach before execution.

## Proposed Changes

### 1. Database Schema
We will introduce an append-only `audit_logs` table to store all cryptographic logs.

#### [NEW] `backend/database/models.py` (or equivalent schema file)
Create the SQLAlchemy/SQLModel entity for `AuditLog`:
- `id`: UUID (Primary Key)
- `actor_id`: String (User ID or 'system')
- `action`: String (e.g., 'DOCUMENT_UPLOAD', 'TASK_EXECUTE', 'TOOL_CALL', 'USER_LOGIN')
- `target_type`: String (e.g., 'document', 'task', 'artifact')
- `target_id`: String (Nullable)
- `details`: JSON (Contextual metadata)
- `timestamp`: DateTime (UTC)
- `prev_hash`: String (Hash of the chronologically previous log entry)
- `hash`: String (SHA-256 hash of `[id, actor_id, action, timestamp, prev_hash, details]`)

### 2. Core Audit Service
We need a robust, concurrency-safe service to write logs and compute hash chains.

#### [NEW] `backend/services/audit_service.py`
Implement `AuditService`:
- `log_event(actor_id, action, target_type, target_id, details)`: 
  - Retrieves the most recent log's `hash` (using a row-level lock or serialized transaction to prevent race conditions).
  - Computes the new SHA-256 hash.
  - Inserts the new record.
- `verify_chain()`: (Optional/Admin) Iterates through the audit log and re-computes hashes to ensure no rows were tampered with.
- `get_recent_logs(limit)`: Retrieves the latest logs for the UI.

### 3. API Endpoints
We need to expose the audit logs to the frontend UI.

#### [NEW] `backend/api/audit.py`
Create the FastAPI router for audit logs:
- `GET /api/audit/export`: Returns a JSON list of recent audit logs formatted to match the frontend expectations (`{ audit_logs: [...] }`).
- Register this router in `backend/main.py`.

#### [MODIFY] `backend/main.py`
- Include the new audit router: `app.include_router(audit.router, prefix="/api/audit", tags=["Audit"])`

### 4. Integration (Event Emitting)
Inject the `AuditService.log_event` into critical pathways across the application to build a comprehensive trail.

#### [MODIFY] `backend/api/auth.py`
- Log `USER_LOGIN` and `USER_LOGOUT` events.

#### [MODIFY] `backend/api/documents.py`
- Log `DOCUMENT_UPLOAD`, `DOCUMENT_DELETE`, and `DOCUMENT_INDEX` events.

#### [MODIFY] `backend/api/agent.py`
- Log `TASK_CREATED`, `TOOL_EXECUTION_START`, `TOOL_EXECUTION_SUCCESS`, `TOOL_EXECUTION_FAILED`, and `ARTIFACT_GENERATED` events.

### 5. Frontend Alignment
Ensure the data structures returned by `/api/audit/export` map cleanly to the UI.

#### [MODIFY] `frontend/app.js` (Minor adjustments if necessary)
- The frontend currently expects: `l.created_at`, `l.hash`, `l.user_id`, `l.action`, `l.details_json`, `l.integrity_status`. 
- Ensure the backend serialization matches this naming convention exactly.

## Verification Plan

### Automated Tests
- `pytest backend/tests/test_audit.py`: Verify that sequential `log_event` calls produce a valid cryptographic chain (each `prev_hash` correctly matches the prior `hash`).
- Test race conditions by firing multiple concurrent `log_event` calls and ensuring the chain remains unbroken.

### Manual Verification
1. Perform actions in the workbench (upload a document, prompt the agent, sign out/in).
2. Navigate to the "Audit Trail" tab in the UI.
3. Verify that new events populate instantly with valid SHA-256 hashes and display the `✓ verified` integrity badge.
4. Manually modify a row in the database using SQL to test tampering, and ensure a backend verification script flags the chain as broken.
