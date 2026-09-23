# Legislative Assistant

An AI-powered Graph RAG application for legislative and policy research. Ask questions about federal legislation and get accurate, grounded answers backed by actual bill text stored in a knowledge graph — reducing hallucinations compared to a plain LLM.

Currently indexed: **Every Student Succeeds Act (ESSA)**

### Knowledge Graph

Bills are parsed into nodes and connected by relationships in a Neo4j knowledge graph. Each retrieval query traverses the graph to fetch the matched section plus its siblings, providing richer surrounding context to the LLM.

`backend/sample/build_knowledge_graph.py` loads the parsed TSVs from `backend/sample/parser/`, labels every node inside the bill hierarchy `:Embeddable`, then embeds them into the vector index. The embedding side is defined once in `backend/sample/embed_graph.py`:

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

1. **Query classification** — The LLM first evaluates whether the user's question is legislation-related. If yes, it rewrites the question for clarity before retrieval. If not, it falls back to a direct LLM response.
2. **Vector retrieval** — The rewritten question is embedded and used to perform a similarity search against legislation chunks stored in a Neo4j knowledge graph. A Cypher retrieval query also fetches sibling nodes to provide surrounding context.
3. **RAG answer generation** — Retrieved context is injected into a prompt and the LLM generates a response grounded in actual bill text. The LLM is instructed to cite its sources.
4. **Streaming to UI** — Responses are streamed token-by-token to the browser via Server-Sent Events (SSE).

```
User question
    → Query classification (LLM)
    → Vector search (Neo4j + sentence-transformers)
    → RAG prompt construction
    → Answer generation (Qwen3-4B local via MLX)
    → Streamed response (SSE → Next.js UI)
```

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React 19, Tailwind CSS v4 |
| Backend | FastAPI, Python |
| LLM inference | MLX (`Qwen/Qwen3-4B-MLX-4bit`) — Apple Silicon only |
| Embeddings | `Qwen/Qwen3-Embedding-0.6B` (1024-dim) via HuggingFace / sentence-transformers, FlashAttention-2 |
| Vector store / graph | Neo4j with LangChain Neo4j integration |
| LLM orchestration | LangChain, LangGraph |
| Package manager | pnpm (frontend), uv (backend) |

---

## Prerequisites

- **macOS with Apple Silicon** (M1/M2/M3) — the backend uses MLX for local inference
- Node.js 20+ and pnpm
- Python 3.11+
- A running Neo4j instance with the ESSA legislation already ingested and indexed (index name: `ESSA`)

---

## Getting started

### 1. Clone the repo

```bash
git clone <repo-url>
cd legis-assistant-nextjs
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

> **Note:** The first run will download the Qwen3-4B model weights (~2.5 GB) and the embedding model from HuggingFace.

### 4. Start the backend

```bash
# From the backend/ directory with the virtual environment active
uvicorn main:app --reload --port 8000
```

### 5. Configure the frontend

```bash
# From the project root
cp .env.example .env.local
```

`BACKEND_URL` tells the Next.js server where FastAPI lives. The browser never
calls FastAPI directly -- `next.config.ts` rewrites `/api/*` through to
`BACKEND_URL`, so requests stay same-origin and CORS is not on the path. It is
deliberately not prefixed `NEXT_PUBLIC_`, so it is never inlined into the client
bundle.

Leave `NEXT_PUBLIC_API_URL` empty unless the browser must reach the backend at
an absolute URL instead of through the rewrite.

Set `NEXT_PUBLIC_ADAPTER_TYPE=in-memory` to serve chat from a local mock stream.
That lets you work on the frontend without starting the backend, which loads the
LLM, the embedding model and a Neo4j connection at import time.

### 6. Install frontend dependencies

```bash
pnpm install
```

### 7. Start the frontend

```bash
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Project structure

```
legis-assistant-nextjs/
├── app/                    # Next.js app directory
│   ├── chat/               # Chat UI components and hooks
│   ├── components/         # Shared UI components (layout, panels)
│   ├── rag/                # RAG-related frontend utilities
│   └── streaming/          # SSE streaming utilities
├── backend/
│   ├── chat/
│   │   ├── rag.py          # Main chat endpoint + MLX compatibility patches
│   │   └── think_filter.py # Strips <think> reasoning tokens from output
│   ├── vectorstore/
│   │   └── retreiver.py    # Neo4j vector retrieval + RAG answer generation
│   ├── config/
│   │   └── main.py         # App settings (Neo4j credentials via .env / secrets)
│   ├── nodes/              # Graph node ingestion scripts
│   ├── relationships/      # Graph relationship ingestion scripts
│   ├── data/               # Raw legislative data
│   └── main.py             # FastAPI app entry point
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

**Backend API docs** (auto-generated by FastAPI):
```
http://localhost:8000/docs
```

---

## Known issues

- **MLX / langchain-community compatibility** — `langchain-community 0.4.1` passes a `formatter` kwarg to `mlx_lm.generate()` that `mlx-lm 0.28.3` rejects. Three monkey-patches in `backend/llm/model.py` fix this at runtime. If you upgrade either library, test thoroughly before removing them.
- **Apple Silicon only** — MLX does not run on x86. To run on other hardware, swap `MLXPipeline` / `ChatMLX` for an OpenAI-compatible client (e.g., `langchain-openai`) or a remote inference provider.

---

## Next steps

- [ ] **Expand the knowledge graph** — Ingest additional legislation beyond ESSA (appropriations bills, IDEA, HEA, etc.)
- [ ] **Optimize data injestion** — Sync eval and injestion methods for extracting legislative text.
- [ ] **Link bills to the US Code** — Add relationships between bill sections and the US Code sections they amend
- [ ] **Lawmaker relationships** — Add nodes for sponsors, co-sponsors, and committee members; enable queries like "which bills did Sen. X sponsor?"
- [ ] **Regulation linkage** — Connect legislation to related CFR regulations for end-to-end policy tracing
- [ ] **Source citations in UI** — Surface the retrieved Neo4j documents alongside the answer so users can verify sources
- [ ] **Multi-bill comparison** — Support queries that compare provisions across multiple bills
- [ ] **Cloud deployment** — Add a deployment configuration for running inference on a remote GPU (Modal, Fly.io, etc.) so the app is not limited to Apple Silicon
- [ ] **Graph visualization** — Display the knowledge graph subgraph used to answer each query
- [ ] **Agentic legislative workflows** — Build multi-step AI agents that can plan new legislation (drafting sections, identifying conflicts with existing law) and search the web for policy research and precedent
- [ ] **Evaluation frameworks** — Implement evaluation pipelines for all AI workflows and outputs, including retrieval quality, answer faithfulness, and end-to-end response accuracy
