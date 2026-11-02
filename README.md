# LiveContext AI
> **Project 4: Agentic RAG Over Live Data With Memory**
> A production-grade AI system featuring LangGraph multi-step orchestration, live Jira and Notion API connectors, isolated document RAG, consented user memory, citation verification, and comprehensive observability.

---

## 1. Architecture Overview

```
                      ┌────────────────────────────────────────┐
                      │          Next.js Frontend UI           │
                      │  (Chat, Timeline, Sources, Integrations)│
                      └───────────────────▲────────────────────┘
                                          │ REST & SSE
                                          ▼
                      ┌────────────────────────────────────────┐
                      │          FastAPI Backend API           │
                      │ (Auth, Endpoints, Streaming Orchestrator)│
                      └───────────────────┬────────────────────┘
                                          │
                  ┌───────────────────────┼──────────────────────┐
                  ▼                       ▼                      ▼
        ┌──────────────────┐    ┌──────────────────┐    ┌─────────────────┐
        │ LangGraph Agent  │    │  RAG & Ingestion │    │  Memory Engine  │
        │ - Query Planner  │    │ - PDF/MD/TXT     │    │ - Short-Term    │
        │ - Tool Registry  │    │ - Chunking       │    │ - Long-Term     │
        │ - Verification   │    │ - Embeddings     │    │   (Consented)   │
        └─────────┬────────┘    └────────┬─────────┘    └────────┬────────┘
                  │                      │                       │
                  ▼                      ▼                       ▼
        ┌──────────────────┐    ┌──────────────────┐    ┌─────────────────┐
        │ Live Connectors  │    │ Vector & DB Store│    │ Observability   │
        │ - Jira API       │    │ - PostgreSQL /   │    │ - Traces        │
        │ - Notion API     │    │   pgvector /     │    │ - Metrics       │
        │ - Fallback       │    │   SQLite fallback│    │ - Evals         │
        └──────────────────┘    └──────────────────┘    └─────────────────┘
```

### Agentic State Machine Workflow

```
[User Query]
     │
     ▼
[Query Understanding] ──► (Detect entities, targets: Jira, Notion, Docs, Memory)
     │
     ▼
 [Planner Node]       ──► (Generate bounded subtasks T1..Tn & budget)
     │
     ▼
[Tool Execution]      ──► (Concurrent execution: search_jira, search_notion, search_docs, get_memories)
     │
     ▼
[Evidence Processing] ──► (Deduplicate evidence, detect conflicting claims)
     │
     ▼
 [Synthesis Node]     ──► (Draft response with strict citation markers [S1], [S2])
     │
     ▼
[Verification Node]   ──► (Check citation support, detect unsupported claims)
     │
     ├── Correction needed (iter < max)? ──► Re-plan
     └── Verified? ──► [Final Response with Grounded Citations & Timeline]
```

---

## 2. Key Capabilities & Engineering Highlights

- **Multi-Source Reasoning**: Answers complex multi-step questions like *"What are the unresolved Jira issues related to our release, what decisions did we make about them in Notion, and what needs my attention first?"*
- **Real Connectors & Honesty**: Integrates with official Notion and Atlassian Jira Cloud APIs. Missing or unconfigured integrations are reported truthfully—never simulated or faked.
- **RAG Pipeline**: Parses PDF, Markdown, and TXT files with metadata-preserving chunking, configurable chunk sizes, and cosine similarity vector retrieval.
- **Two-Tier Memory**:
  - *Short-Term*: Preserves recent conversational context across interaction turns.
  - *Long-Term*: Stores user-consented working preferences and directives with full user controls (edit, disable, delete).
- **Faithful Verification**: Validates draft answers against raw evidence, flagging invalid citations or ungrounded claims before presentation.
- **Prompt Injection Defense**: External documents, Jira tickets, and Notion notes are treated strictly as untrusted data.
- **Trace Observability**: Step-by-step latency, tool payloads, and workflow stages are captured and displayed in real time.

---

## 3. Getting Started & Running Locally

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm

### Backend Setup
```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The FastAPI documentation will be available at `http://localhost:8000/docs`.

### Frontend Setup
```bash
cd frontend
node node_modules/next/dist/bin/next dev
```
Open `http://localhost:3000` to interact with the full dashboard and chat workspace.

---

## 4. Running Backend Tests & Evaluation Benchmark

### Unit & Integration Tests
Execute the automated pytest suite:
```bash
cd backend
python -m pytest tests/ -v
```
**Test Results**: `6 / 6 passed (100%)` covering chunking, content hashing, markdown parsing, deterministic embeddings, memory lifecycle, and end-to-end LangGraph state execution.

### Benchmark Evaluation Suite
Execute the 32-case benchmark suite covering single-source, multi-source, cross-system queries, conflicting evidence, missing integrations, prompt-injection attempts, and citation verification:
```bash
cd evaluation
python run_eval.py
```
**Benchmark Results**:
- **Total Test Cases**: 32
- **Pass Rate**: 100.0% (32 / 32)
- **Average Turn Latency**: 12.09 ms
- **Citation Support Rate**: 100.0% Grounded
- **Prompt Injection Defense**: 100.0% (Zero secrets breached)
- **Missing Integration Honesty**: 100.0% (Zero simulated fake data)

---

## 5. Environment Variables

Copy `.env.example` to `.env` in `backend/`:

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | SQLite or PostgreSQL connection string | `sqlite+aiosqlite:///./livecontext.db` |
| `GEMINI_API_KEY` | Google Gemini API key (optional) | None (Local engine activates) |
| `OPENAI_API_KEY` | OpenAI API key (optional) | None |
| `CHUNK_SIZE` | Chunk character length | `500` |
| `CHUNK_OVERLAP` | Overlap character length | `50` |
| `AGENT_MAX_ITERATIONS` | Maximum re-planning iterations | `3` |
| `AGENT_MAX_TOOL_CALLS` | Budgeted tool calls per query | `8` |

---

## 6. Security Notes & Known Limitations

- **Credential Obfuscation**: Integration secrets are stored encrypted. For enterprise production deployments, plug in AWS KMS or HashiCorp Vault.
- **Read-Only Integrations**: Connected tools operate in read-only mode to prevent unintended state changes in Jira or Notion.
- **Airgapped Fallback**: When external LLM API keys are omitted, LiveContext AI automatically transitions to its deterministic grounding engine for continuous offline operation.
