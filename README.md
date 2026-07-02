# Bug Whisperer

![Bug Whisperer Preview](preview.png)

An AI debugger with persistent memory that gets smarter every time you fix a bug.

Built for **"The Hangover Part AI" Hackathon** by WeMakeDevs x Cognee.

> **AI Assistant Disclosure (Rule 8):** This project was built with assistance from Claude (Anthropic) via the pi coding agent for architecture design, code generation, and debugging. All core logic, Cognee integration patterns, and demo flow were human-directed and reviewed.

**Track:** Best Use of Open Source (Self-Hosted Cognee) — MacBook Neo

---

## What It Does

Bug Whisperer uses **Cognee's hybrid graph-vector memory** to build a knowledge graph of every bug you encounter. When you hit a similar error, it recalls the root cause and fix — getting smarter with every session.

### Three Ways to Use It

| Interface | Command | Best For |
|-----------|---------|----------|
| CLI | `bw "NullPointerException in auth.ts"` | Terminal-first devs, CI/CD pipelines |
| Web Dashboard | `bun run dev` -> localhost:3000 | Visual debugging, exploring memory |
| Python API | `from bug_whisperer import analyze` | Code integration, scripts |

---

## Quick Start

```bash
git clone git@github.com:imadnan4/Bug-Whisperer.git
cd Bug-Whisperer

# 1. Backend
cd backend
cp .env.example .env   # Edit with your API key
uv venv && source .venv/bin/activate
uv pip install cognee fastapi uvicorn pydantic python-dotenv httpx "cognee[fastembed]"
uvicorn src.main:app --port 8000

# 2. CLI (new terminal)
cd backend && source .venv/bin/activate
uv pip install -e .    # Installs `bw` command
bw "TypeError: Cannot read properties of null"

# 3. Web Dashboard (new terminal)
cd frontend && bun install && bun run dev
# Open http://localhost:3000
```

---

## Project Structure

```
Bug-Whisperer/
  backend/               FastAPI + Cognee
    src/
      main.py            API server
      memory.py          Cognee operations
      models.py          Data models
      cli.py             CLI tool (bw command)
    .env.example
    pyproject.toml
  frontend/              Next.js + Optics
    src/app/
      page.tsx           Dashboard
      layout.tsx
    src/components/optics/
  README.md
```

---

## How Cognee Powers This

| Cognee API | Usage |
|------------|-------|
| `remember()` | Stores bug -> root cause -> fix as graph nodes |
| `recall()` | Hybrid vector + graph search for similar past bugs |
| `improve()` | Feedback loop: did the fix work? |

### Knowledge Graph Structure
```
Error: "TypeError: Cannot read null.token"
  - Type: NullReferenceError
  - File: middleware/auth.ts
  - Root Cause: Missing null check
  - Fix: Add guard clause
  - Related Errors:
      "null has no property 'id'"
      "Cannot destructure property of null"
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Memory | Cognee (self-hosted) |
| LLM | DeepSeek v4 Pro |
| Embeddings | Fastembed (BAAI/bge-small) |
| Backend | FastAPI + Python 3.14 |
| CLI | Typer + Rich |
| Frontend | Next.js 16 + Optics Design System |

---

## License

MIT
