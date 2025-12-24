# ✨ Reactive Notebook (Python / SQL)

A **reactive notebook** where code cells automatically re-execute when their dependencies change. Supports **Python** and **SQL** cells with real-time updates via Server-Sent Events.

## Features

### Core Functionality
- **Reactive Execution** - Cells automatically rerun when dependencies change (like Excel formulas)
- **Python Cells** - Execute Python code with variable tracking
- **SQL Cells** - Query PostgreSQL with `{{variable}}` substitution from Python context
- **Debounced Auto-Run** - 500ms delay after editing before execution (prevents excessive reruns)
- **Smart Dependency Tracking** - AST analysis for Python, placeholder detection for SQL
- **Error Isolation** - Failed cells only block their descendants, not independent branches
- **Variable Cleanup** - Deleting or editing cells properly clears stale variables

### Technical Features
- **Timeout Protection** - 30-second execution limit for Python and SQL
- **Row Limits** - SQL queries limited to 1000 rows (with truncation warnings)
- **Connection Pooling** - Efficient PostgreSQL connection management
- **Duplicate Detection** - Clear errors for conflicting variable definitions
- **Real-time Updates** - SSE streaming with last-write-wins concurrency
- **E2E Type Safety** - Pydantic v2 backend, OpenAPI → TypeScript frontend

---

## Project Structure

```
reactive_notebook/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── main.py            # FastAPI app + API routes
│   │   ├── domain/            # Pydantic models
│   │   │   └── models.py      # Cell, Notebook, Request/Response types
│   │   ├── repo/              # Data persistence (Repository pattern)
│   │   │   ├── base.py        # NotebookRepository interface
│   │   │   └── in_memory.py   # In-memory implementation
│   │   ├── analysis/          # Dependency extraction
│   │   │   ├── python.py      # AST-based Python analysis
│   │   │   └── sql.py         # {{var}} placeholder detection
│   │   ├── graph/             # Dependency graph + DAG
│   │   │   └── dag.py         # Graph building, cycle detection, topo sort
│   │   ├── runtime/           # Code execution
│   │   │   ├── scheduler.py   # Orchestrates reactive execution
│   │   │   ├── python_executor.py  # Python execution with timeouts
│   │   │   ├── sql_executor.py     # SQL execution + variable substitution
│   │   │   └── pool_manager.py     # PostgreSQL connection pooling
│   │   └── events/            # Server-Sent Events
│   │       ├── bus.py         # EventBus for SSE streaming
│   │       └── models.py      # SseEvent types
│   ├── requirements.txt       # Python dependencies
│   └── pyrightconfig.json     # Type checking config
│
├── frontend/                   # React + TypeScript frontend
│   ├── src/
│   │   ├── main.tsx           # App entry point
│   │   ├── pages/
│   │   │   └── NotebookPage.tsx    # Main notebook UI
│   │   ├── components/
│   │   │   ├── CellView.tsx        # Code cell editor + output
│   │   │   └── ErrorBanner.tsx     # Error message display
│   │   ├── lib/
│   │   │   ├── apiClient.ts        # REST API calls
│   │   │   └── sse.ts              # SSE event handling
│   │   ├── store/
│   │   │   └── notebookStore.ts    # State management
│   │   ├── hooks/
│   │   │   └── useDebounce.ts      # Debounce hook for auto-run
│   │   └── gen/
│   │       └── api-types.ts        # Generated TypeScript types
│   ├── package.json
│   └── vite.config.ts
│
├── testing.md                 # Test scenarios
├── plan.md                    # Original implementation plan
└── README.md                  # This file
```

---

## Quick Start

### Prerequisites

- **Python 3.11+** (with pip or uv)
- **Node.js 18+** (with npm)
- **Docker** (for PostgreSQL testing, optional)

### Installation

#### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Generate TypeScript types from OpenAPI schema
# (requires backend running on port 8000)
npm run generate-types
```

#### 3. Start Services

**Terminal 1 - Backend:**
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

---

### Optional: PostgreSQL Test Database

For testing SQL cells, set up a PostgreSQL container:

```bash
# Start PostgreSQL
docker run --name test-postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=testdb \
  -p 5432:5432 \
  -d postgres:15

# Wait 5 seconds for startup, then create test data
sleep 5
docker exec test-postgres psql -U postgres -d testdb -c \
  "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, status TEXT);"

docker exec test-postgres psql -U postgres -d testdb -c \
  "INSERT INTO users VALUES
   (123, 'Alice', 'active'),
   (456, 'Bob', 'active'),
   (789, 'Charlie', 'inactive');"
```

In the notebook UI, configure the DSN:
```
postgresql://postgres:password@localhost:5432/testdb
```

**To stop later:**
```bash
docker stop test-postgres && docker rm test-postgres
```

---

## Usage & Testing

### Usage (quick guide)

- **Create cells**: Click **+ Python** or **+ SQL**.
- **Run cells**:
  - **Auto-run**: Edit code, pause for ~500ms, and the impacted subgraph runs automatically.
  - **Manual run**: Click **Run** on a cell to execute it and its dependents.
- **Python cells**: Define variables/functions/classes and print to stdout for output.
- **SQL cells**: Use `{{var}}` placeholders to reference values from Python context.
  - Strings are quoted/escaped; lists/tuples are expanded; outputs are returned as JSON.
- **Delete cells**: Removes the cell and clears its defined names; dependents may error if they relied on deleted defs.

### Testing checklist

| Scenario | Setup | Expected |
|---|---|---|
| **Python → Python** | `x = 10` then `y = x + 5`, edit `x` to `20` | Cell 2 reruns; `y = 25` |
| **Cascading deps** | `x = 5` → `y = x + 5` → `z = y * 2`, edit `x` to `10` | Runs in order; y=15, z=30 |
| **SQL variable substitution** | Python: `user_id = 123`; SQL uses `{{user_id}}`, change to `456` | SQL reruns with new value |
| **Delete upstream** | Create `x = 10` → `y = x + 5`, delete `x` cell | Dependent errors (NameError/undefined) |
| **Edit removes a var** | Cell defines `x` and `y`; downstream uses `x`; edit to remove `x` | Downstream errors for `x` |
| **Undefined SQL placeholder** | SQL references `{{nonexistent}}` | Clear error indicating missing variable |
| **Duplicate definitions** | Two cells both define `x = ...` | Duplicate-definition error (names + cells) |
| **Independent branches** | A independent of failing B; C depends only on A | C still runs successfully |
| **Timeout (Python)** | `import time; time.sleep(35)` | Stops ~30s with timeout error |
| **Row limit (SQL)** | Query returns >1000 rows | Truncates to 1000 with warning |

---

## Technical Architecture

### Reactive Execution Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    User Edits Cell X                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
              ┌────────────────┐
              │  Debounce 500ms│
              └────────┬────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │  1. Analyze All Cells       │
         │     - Extract defs/refs      │
         │     - Persist to repo        │
         └─────────────┬────────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │  2. Build Dependency Graph  │
         │     - Cell A → Cell B if    │
         │       B.refs ∩ A.defs ≠ ∅   │
         └─────────────┬────────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │  3. Get Impacted Subgraph   │
         │     - Find all descendants  │
         │       of Cell X              │
         └─────────────┬────────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │  4. Topological Sort        │
         │     - Order cells by deps   │
         │     - Detect cycles          │
         └─────────────┬────────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │  5. Execute in Order        │
         │     - Clear old vars        │
         │     - Run each cell         │
         │     - Track failures        │
         │     - Skip if dep failed    │
         └─────────────┬────────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │  6. Stream SSE Events       │
         │     - cell_status           │
         │     - cell_output           │
         │     - cell_error            │
         └──────────────────────────────┘
```

### Dependency Graph Example

```python
# Cell 1
x = 10

# Cell 2
y = x + 5

# Cell 3
z = y * 2

# Cell 4 (independent)
a = 100
```

**Graph Structure:**
```
Cell 1 ──→ Cell 2 ──→ Cell 3

Cell 4 (no edges)
```

**Adjacency List:**
```python
{
  'cell1': {'cell2'},      # Cell 2 depends on Cell 1
  'cell2': {'cell3'},      # Cell 3 depends on Cell 2
  'cell3': set(),          # Cell 3 has no dependents
  'cell4': set()           # Cell 4 is independent
}
```

**Execution Order (Topological Sort):**
```
Edit Cell 1 → Execute: [Cell 1, Cell 2, Cell 3]
Edit Cell 4 → Execute: [Cell 4]  (independent)
```

---

## Tech Stack

### Backend
| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.11+ | Runtime |
| **FastAPI** | 0.127.0 | Web framework + OpenAPI |
| **Pydantic** | 2.12.5 | Data validation + serialization |
| **asyncpg** | 0.31.0 | PostgreSQL async driver |
| **Uvicorn** | 0.40.0 | ASGI server |
| **Pyright** | 1.1.395 | Type checking |
| **Ruff** | 0.6.9 | Linting + formatting |

### Frontend
| Technology | Version | Purpose |
|------------|---------|---------|
| **React** | 19.1.0 | UI framework |
| **TypeScript** | 5.8.3 | Type safety |
| **Vite** | 7.1.4 | Build tool + dev server |
| **CodeMirror** | 4.25.1 | Code editor |
| **openapi-typescript** | 7.4.4 | Type generation |

### Key Libraries
- **Python AST** - Dependency extraction from Python code
- **graphlib.TopologicalSorter** - DAG ordering and cycle detection
- **asyncio** - Async execution with timeouts
- **Server-Sent Events (SSE)** - Real-time updates

---

## Technical Decisions

### 1. **Repository Pattern**
- **Decision:** Abstract data layer behind `NotebookRepository` interface
- **Rationale:** Enables easy swap from in-memory to SQLite/Postgres persistence without changing business logic
- **Implementation:** `InMemoryNotebookRepository` currently, but was planning migration to `SqliteNotebookRepository` with more time

### 2. **Dependency Tracking**
- **Python:** AST visitor pattern to extract variable/function definitions and references
- **SQL:** Regex pattern `{{var_name}}` for explicit dependency declaration

### 3. **DAG Execution**
- **Decision:** Use `graphlib.TopologicalSorter` from Python stdlib
- **Optimization:** Only execute impacted subgraph (not entire notebook)

### 4. **Error Isolation**
- **Decision:** Track failed cells, skip their descendants but allow independent branches to continue
- **Rationale:** Avoid wasting execution time on cells that can't succeed due to missing upstream definitions
- **Behavior:**
  - When Cell A fails, any Cell B that depends on A is **skipped** (status set to "idle", not executed)
  - Skipped cells do **not** show their own errors (e.g., NameError) - they're silently skipped
  - Independent cells (those not depending on failed cells) continue executing normally
- **Example:**
  - Cells: `x = 5` (A) → `y = x + 5` (B) → `z = y * 2` (C), and independent `w = 100` (D)
  - Delete Cell A → Cell B shows "NameError: x is not defined", Cell C is **skipped** (no error shown), Cell D runs normally
- **Note:** This means you'll only see the **first error in a dependency chain**, not cascading errors

### 5. **Variable Lifecycle**
- **Decision:** Clear old defs before re-execution
- **Rationale:** Prevents stale variables when cells are edited/deleted
- **Implementation:** Store old defs, clear from globals, then execute new code

### 6. **Concurrency Control**
- **Decision:** Last-write-wins with runId + execution lock
- **Rationale:** Prevents race conditions, users see most recent state
- **Trade-off:** Sequential execution (could parallelize independent branches in future)

### 7. **Type Safety**
- **Backend:** Pydantic v2 models for all data structures
- **Frontend:** OpenAPI → TypeScript generation for API contract
- **Benefit:** Compile-time guarantees, prevents API drift

---

## Future Improvements (Prioritized)

1. **SQLite Persistence** - Implement `SqliteNotebookRepository` for durability (survive restarts), run history, and multi-notebook support.
2. **Cell Reordering** - Drag-and-drop cell ordering (persist `order` changes; validate no circular dependencies).
3. **Execution History** - Store and view past runs (timestamps, outputs, comparisons).
4. **Performance Optimizations** - Parallelize independent branches, avoid full-graph rebuilds, and virtualize large notebooks.
5. **Enhanced SQL Support** - Multiple database types, richer result rendering, and SQL autocomplete based on schema.
6. **Export/Import** - Export notebooks (JSON), import `.ipynb`, and export cells as scripts.
7. **Collaboration** - Real-time multi-user editing (CRDT/OT).
8. **More Languages** - Add JavaScript, R, and shell cells.
9. **Rich Outputs** - Render plots, DataFrames, and HTML outputs.
10. **Safer Execution Environment** - Run code in an isolated worker process with resource limits (timeouts, memory/output caps) and stricter filesystem/network access controls.
11. **Cell Templates** - Common templates for loading/visualization patterns.
12. **Variable Inspector** - Inspect Python context variables and their values.

---

<!-- Usage guide merged into "Usage & Testing" above. -->
