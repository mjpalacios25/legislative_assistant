# Legislative Assistant

An AI-powered Graph RAG application for legislative and policy research. Ask questions about federal legislation and get accurate, grounded answers backed by actual bill text stored in a knowledge graph — reducing hallucinations compared to a plain LLM.

Currently indexed: **Every Student Succeeds Act (ESSA)**

The backend runs a local LLM on whichever GPU it finds: **NVIDIA (CUDA)** — including under WSL2 — or **Apple Silicon (MLX)**.

### Knowledge Graph

Bills are parsed into nodes and connected by relationships in a Neo4j knowledge graph. Each retrieval query traverses the graph to fetch the matched section plus its siblings, providing richer surrounding context to the LLM.

Building the graph is a two-step pipeline:

1. **Parse** — `backend/sample/build_node_files.py` reads the bill XML from `backend/public/`, walks it with the `BillParser` class in `backend/sample/utils.py` (bill → title → part → section → subsection → paragraph → subparagraph → clause → subclause), de-duplicates edges, and writes one Neo4j-ready TSV per node type to `backend/sample/parser/nodes/` plus `part_of` relationships to `backend/sample/parser/relationships/`.
2. **Load + embed** — `backend/sample/build_knowledge_graph.py` loads those TSVs into Neo4j in batches, labels every node inside the bill hierarchy `:Embeddable`, then hands off to `VectorStore` to embed those nodes and create the vector index — all in one run.

The embedding side is defined once in `backend/sample/embed_graph.py`:

| Setting | Value |
|---|---|
| Embedding model | `Qwen/Qwen3-Embedding-0.6B` |
| Vector dimension | 1024 |
| Similarity | cosine (vectors are L2-normalised) |
| Neo4j vector index | `ESSA` on `(:Embeddable {embedding})` |
| Attention | FlashAttention-2 on NVIDIA, `sdpa` elsewhere |
| Padding | left (the model pools on the last token) |

FlashAttention-2 comes from the prebuilt Hub kernel `kernels-community/flash-attn2` rather
than the `flash-attn` package, which has no wheel for torch 2.13. This needs
`transformers >= 5.17` and the `kernels` package — both pinned in `backend/pyproject.toml`.
Older transformers pins that kernel to v1, whose builds stop at torch 2.12, and fails with
a misleading *"the package for FlashAttention2 doesn't seem to be installed"*. On a
successful load transformers logs `You do not have flash_attn installed, using
kernels-community/flash-attn2 from the kernels library instead!`. The kernel is downloaded
on first use and cached under `~/.cache/huggingface/hub/kernels--kernels-community--flash-attn2`,
so a fully offline (`HF_HUB_OFFLINE=1`) run works only after one online run.

Anything that queries the index must embed with the same model — Neo4j rejects a search whose vector dimension does not match the index. Reuse `EMBEDDING_MODEL_NAME`, `EMBEDDING_DIMENSION`, and `VECTOR_INDEX_NAME` from `sample/embed_graph.py` rather than redeclaring them.

![ESSA Knowledge Graph](public/ESSA%20Node%20Viz.png)

---

## How it works

1. **Query classification** — The LLM first evaluates whether the user's question is ESSA-related. If yes, it restates the question in one line before retrieval. If not, it falls back to a direct LLM response. The classifier is capped at 64 new tokens so it cannot stall the first byte with long deliberation.
2. **Vector retrieval** — The rewritten question is embedded and used to perform a similarity search against legislation chunks stored in a Neo4j knowledge graph. A Cypher retrieval query also fetches sibling nodes to provide surrounding context.
3. **RAG answer generation** — Retrieved context is injected into a prompt and the LLM generates a response grounded in actual bill text. The LLM is instructed to cite its sources.
4. **Streaming to UI** — Responses are streamed token-by-token to the browser via Server-Sent Events (SSE). A `new_message` event is sent immediately so the UI shows a loading state while classification runs, and `<think>` reasoning blocks are stripped from the stream.

```
User question
    → Query classification (LLM)
    → Vector search (Neo4j + Qwen3-Embedding-0.6B)
    → RAG prompt construction
    → Answer generation (local LLM: Qwen3.5-9B on CUDA, or Qwen3-4B on MLX)
    → Streamed response (SSE → Next.js route handler → UI)
```

### Hardware detection and the LLM service

`backend/sample/system_check.py` defines `DeviceManager`, which detects the accelerator via torch (`cuda` → `mps` → `cpu`). `backend/llm/model.py` branches on it:

| Device | Model | Runtime |
|---|---|---|
| NVIDIA (CUDA) | `Qwen/Qwen3.5-9B`, 4-bit NF4 via bitsandbytes (~6 GiB weights, fits in 16 GB VRAM) | `HuggingFacePipeline` + `ChatHuggingFace` |
| Apple Silicon (MPS) | `Qwen/Qwen3-4B-MLX-4bit` | `MLXPipeline` + `ChatMLX` |
| CPU only | not supported — `chat_model` is never defined and import fails | — |

Check what the backend will see with:

```bash
cd backend
uv run python sample/system_check.py
```

`backend/services/llm_service.py` is the single async entry point to the model (`acomplete`, `astream_text`). Routers never call the model's async API directly, because the two branches differ: `ChatMLX` supports LangChain's async API natively, while `ChatHuggingFace` over a `HuggingFacePipeline` is synchronous only, so the service bridges it through a worker thread. The service also:

- serialises generation behind a single GPU slot, so concurrent requests cannot race for device memory;
- renders the prompt with `enable_thinking=False`, so Qwen answers directly instead of emitting reasoning with an unclosed `<think>` tag that filters cannot strip.

---

## Retrieval evaluation

`backend/evaluations/` measures how well the vector search finds the right piece of the bill for a question. It works in three stages. Each stage writes a file to `backend/public/` that the next stage reads.

```
Bill XML ──generate_samples.py──▶ Subsections.json
         ──generate_dataset.py──▶ questions.yaml   (question → expected subsection)
         ──evaluation.py────────▶ Recall@k / MRR@k table
```

### 1. Parse subsections — `generate_samples.py`

Opens `BILLS-114s1177enr.xml`, goes to **Title I, Part A** of ESSA (found by its fixed XML element ids), and collects every `<subsection>` in every section there. Each subsection's text is cleaned the same way `BillParser.clean_text` cleans text before it goes into Neo4j:

- the subsection's full text is taken, including all nested paragraphs and clauses;
- runs of whitespace are collapsed to a single space;
- the text is NFKD-normalised and converted to ASCII.

Matching the graph's cleaning is what lets a subsection be lined up with the node retrieval returns. The list of subsection strings is saved to `Subsections.json`.

### 2. Generate synthetic questions — `generate_dataset.py`

Takes the first 51 subsections and asks an LLM to write **two questions per subsection**, giving up to 102 test cases. The LLM is reached through [instructor](https://python.useinstructor.com/) over an OpenAI-compatible endpoint at `http://localhost:8080/v1`. The prompt asks for a question of at most two sentences that the subsection can answer. Each request randomly adds one constraint to make retrieval harder:

- add irrelevant context, such as a time of day, the current year or a school district; or
- keep the question vague instead of citing section numbers.

The reply is parsed into a `Question` model (`chain_of_thought`, `question`). Calls run two at a time (`Semaphore(2)`), time out after 60 s, and are retried up to 3 times. Each result becomes a `pydantic_evals.Case`:

- `inputs` is the generated question;
- `expected_output` is `[subsection text]`;
- `metadata` holds the subsection's `chunk_id`.

The full dataset is saved to `questions.yaml`.

### 3. Evaluate retrieval — `evaluation.py`

Loads `questions.yaml` and runs every question against the `ESSA` vector index. This uses a plain retrieval query that returns the top 40 nodes' own text, without the sibling expansion the chat endpoint adds, so results can be compared directly with the expected subsection. Searches run in a thread pool with 10 workers.

`RagMetricsEvaluator` scores each case at k = 1, 3, 5, 10, 15, 20, 25, 30, 35 and 40:

| Metric | Meaning |
|---|---|
| `recall@k` | Share of the expected subsections that appear in the top k results |
| `mrr@k` | 1 / rank of the first correct result within the top k (0 if it is missing) |

Before comparing, both sides have **all whitespace removed and are lowercased** (`_normalize`). Small spacing differences between how the dataset and the graph were built would otherwise make correct hits count as misses; adding this step raised the measured MRR and Recall a lot. Only a retrieved node whose full text equals the subsection counts as a hit. A child paragraph or clause from inside that subsection does not.

Queries are embedded with `VectorStore().embedding_model` from `sample/embed_graph.py` against `VECTOR_INDEX_NAME`, the same model and index the graph was built with. Scores are averaged over all cases and printed as a table. Runs are traced with Logfire, and traces are exported only when `LOGFIRE_TOKEN` is set.

Latest results (102 questions, `Qwen3-Embedding-0.6B`):

| k | 1 | 3 | 5 | 10 | 20 | 30 |
|---|---|---|---|---|---|---|
| Recall@k | 0.74 | 0.87 | 0.88 | 0.92 | 0.96 | 1.00 |
| MRR@k | 0.74 | 0.80 | 0.80 | 0.81 | 0.81 | 0.81 |

### Running it

From `backend/`, after building the knowledge graph:

```bash
uv run python evaluations/generate_samples.py
```

```bash
# Needs an OpenAI-compatible server on :8080 serving Qwen/Qwen3-4B-MLX-4bit, e.g. on Apple Silicon:
uv run mlx_lm.server --model Qwen/Qwen3-4B-MLX-4bit --port 8080
```

```bash
uv run python evaluations/generate_dataset.py
```

```bash
uv run python evaluations/evaluation.py
```

`Subsections.json` and `questions.yaml` are already committed, so you can skip straight to the last command unless you want a fresh dataset. On NVIDIA, `mlx_lm.server` is unavailable. Use any OpenAI-compatible server on port 8080 instead, such as vLLM or llama.cpp, and change the `model=` name in `generate_dataset.py` to match.

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React 19, Tailwind CSS v4 |
| Backend | FastAPI, Python 3.13 |
| LLM inference | NVIDIA: transformers + bitsandbytes (`Qwen/Qwen3.5-9B`, NF4) · Apple Silicon: MLX (`Qwen/Qwen3-4B-MLX-4bit`) |
| Embeddings | `Qwen/Qwen3-Embedding-0.6B` (1024-dim) via HuggingFace / sentence-transformers, FlashAttention-2 on NVIDIA |
| Vector store / graph | Neo4j with LangChain Neo4j integration |
| LLM orchestration | LangChain, LangGraph |
| Package manager | pnpm (frontend), uv (backend) |

---

## Prerequisites

- One of:
  - **NVIDIA GPU with CUDA** (~16 GB VRAM for the 4-bit 9B model) on Linux or WSL2
  - **macOS with Apple Silicon** (M1 or later)
- Node.js 20+ and pnpm
- Python 3.13+ and [uv](https://docs.astral.sh/uv/)
- A running Neo4j instance (see [Build the knowledge graph](#4-build-the-knowledge-graph) to populate it)

---

## Getting started

### 1. Clone the repo

```bash
git clone <repo-url>
cd legislative_assistant
```

### 2. Configure the backend

Create a `.env` file inside the `backend/` directory. All five keys are
required -- `backend/config/main.py` has no defaults and will fail at import if
any is missing:

```bash
# backend/.env
HUGGINGFACEHUB_API_TOKEN=hf_...
NEO4J_URL=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_DB=neo4j
NEO4J_PW=your-neo4j-password
```

`env_file` is resolved relative to the working directory, so the backend must be
started from `backend/`.

### 3. Install backend dependencies

```bash
cd backend
uv sync
```

Dependencies are declared in `backend/pyproject.toml` and locked in `backend/uv.lock` (the old `requirements.txt` is gone).

> **Note:** The first run downloads model weights from HuggingFace — Qwen3.5-9B on NVIDIA (~18 GB at bf16, quantised to 4-bit on load) or Qwen3-4B-MLX (~2.5 GB) on Apple Silicon — plus the embedding model and, on NVIDIA, the FlashAttention-2 kernel.

### 4. Build the knowledge graph

Skip this if your Neo4j instance already has the `ESSA` index. Otherwise, from `backend/`:

```bash
# Parse the bill XML into node/relationship TSVs (already committed; rerun after parser changes)
uv run python sample/build_node_files.py
```

```bash
# Load the TSVs into Neo4j, label :Embeddable nodes, embed them, and create the vector index
uv run python sample/build_knowledge_graph.py
```

### 5. Start the backend

```bash
# From the backend/ directory
uv run uvicorn main:app --reload --port 8000
```

### 6. Configure the frontend

```bash
# From the project root
cp .env.example .env.local
```

`BACKEND_URL` tells the Next.js server where FastAPI lives. The browser never
calls FastAPI directly — the route handler at `app/api/chat/route.ts` forwards
`/api/chat` to `BACKEND_URL` and pipes the SSE body straight through, so
requests stay same-origin and CORS is not on the path. (A `next.config.ts`
rewrite was used previously, but it buffered `text/event-stream` responses
until generation finished.) `BACKEND_URL` is deliberately not prefixed
`NEXT_PUBLIC_`, so it is never inlined into the client bundle.

Leave `NEXT_PUBLIC_API_URL` empty unless the browser must reach the backend at
an absolute URL instead of through the route handler.

Set `NEXT_PUBLIC_ADAPTER_TYPE=in-memory` to serve chat from a local mock stream.
That lets you work on the frontend without starting the backend, which loads the
LLM, the embedding model and a Neo4j connection at import time.

### 7. Install frontend dependencies

```bash
pnpm install
```

### 8. Start the frontend

```bash
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Project structure

```
legislative_assistant/
├── app/                        # Next.js app directory
│   ├── api/chat/route.ts       # Streams /api/chat through to the FastAPI backend
│   ├── chat/                   # Chat UI components and hooks
│   ├── components/             # Shared UI components (layout, sidebar)
│   ├── queries/                # React Query fetchers
│   ├── rag/                    # RAG-related frontend utilities
│   └── streaming/              # SSE streaming utilities
├── backend/
│   ├── chat/
│   │   ├── rag.py              # /api/chat endpoint: classify → retrieve → stream answer
│   │   └── think_filter.py     # Strips <think> reasoning tokens from streamed output
│   ├── config/
│   │   └── main.py             # Settings from .env, plus PUBLIC_DIR / PARSER_DIR paths
│   ├── evaluations/
│   │   ├── generate_samples.py # Title I Part A subsections → public/Subsections.json
│   │   ├── generate_dataset.py # LLM-generated questions → public/questions.yaml
│   │   └── evaluation.py       # Recall@k / MRR@k over the ESSA vector index
│   ├── llm/
│   │   └── model.py            # Builds chat_model for the detected GPU (CUDA or MLX)
│   ├── public/                 # Source bill XML (e.g. BILLS-114s1177enr.xml)
│   ├── sample/
│   │   ├── build_node_files.py       # Bill XML → node / relationship TSVs
│   │   ├── build_knowledge_graph.py  # TSVs → Neo4j, then embed + create vector index
│   │   ├── embed_graph.py            # Embedding model + VectorStore (single source of truth)
│   │   ├── system_check.py           # DeviceManager: detects nvidia / apple_silicon / cpu
│   │   ├── utils.py                  # BillParser and edge de-duplication helpers
│   │   ├── congress_api.py           # Congress.gov API client
│   │   └── parser/                   # Generated TSVs
│   ├── services/
│   │   └── llm_service.py      # Async bridge to the model, GPU serialisation, prompt rendering
│   ├── vectorstore/
│   │   └── retreiver.py        # Neo4j vector retrieval + RAG prompt construction
│   ├── schemas.py              # Pydantic models for legislation data
│   ├── pyproject.toml          # Backend dependencies (uv)
│   └── main.py                 # FastAPI app entry point
├── pyrightconfig.json          # Type checking rooted at backend/ with its .venv
└── vitest.config.mts           # Frontend test config
```

---

## Development

**Run frontend tests:**
```bash
pnpm test
```

**Lint / format frontend:**
```bash
pnpm lint
pnpm format
```

**Run backend tests** (from `backend/`):
```bash
uv run pytest
```

**Backend API docs** (auto-generated by FastAPI):
```
http://localhost:8000/docs
```

**Editor setup (incl. WSL):** `pyrightconfig.json` and `.vscode/settings.json` point Pyright/Pylance at `backend/.venv` and add `backend/` to the import path, so first-party imports like `from config.main import settings` resolve.

---

## Known issues

- **No CPU fallback** — With neither CUDA nor MPS available, `llm/model.py` defines no `chat_model` and the backend fails at import.
- **Short generation ceiling on NVIDIA** — `max_new_tokens` is 4096 to leave VRAM for the KV cache; the Qwen3.5 model card recommends up to 32,768. Raise it if your GPU has headroom.
- **One generation at a time** — `services/llm_service.py` serialises all model calls behind a single GPU slot, so concurrent users queue.
- **Evaluation question generation is tied to MLX** — `generate_dataset.py` assumes a local OpenAI-compatible server serving `Qwen/Qwen3-4B-MLX-4bit` on port 8080.
- **`modal/` shadows the Modal package** — `backend/modal/` shadows the `modal` PyPI package in the editable install. Renaming the directory is the durable fix.

---

## Next steps

- [ ] **Expand the knowledge graph** — Ingest additional legislation beyond ESSA (appropriations bills, IDEA, HEA, etc.)
- [ ] **Optimize data injestion** — Sync eval and injestion methods for extracting legislative text.
- [ ] **Link bills to the US Code** — Add relationships between bill sections and the US Code sections they amend
- [ ] **Lawmaker relationships** — Add nodes for sponsors, co-sponsors, and committee members; enable queries like "which bills did Sen. X sponsor?"
- [ ] **Regulation linkage** — Connect legislation to related CFR regulations for end-to-end policy tracing
- [ ] **Source citations in UI** — Surface the retrieved Neo4j documents alongside the answer so users can verify sources
- [ ] **Multi-bill comparison** — Support queries that compare provisions across multiple bills
- [ ] **Cloud deployment** — Add a deployment configuration for running inference on a remote GPU (Modal, Fly.io, etc.)
- [ ] **Graph visualization** — Display the knowledge graph subgraph used to answer each query
- [ ] **Agentic legislative workflows** — Build multi-step AI agents that can plan new legislation (drafting sections, identifying conflicts with existing law) and search the web for policy research and precedent
- [ ] **Evaluation frameworks** — Implement evaluation pipelines for all AI workflows and outputs, including retrieval quality, answer faithfulness, and end-to-end response accuracy
