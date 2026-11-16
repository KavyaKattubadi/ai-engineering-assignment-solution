# AI Engineering Assignment – Complete Solution

**Asama.ai Interview Problems**  
Submitted solution covering both required problems with full design, working code, safety measures, and production considerations.

---

## Problem 1: A Social Network for AI Agents
**Location:** `problem1-social-network-for-agents/`

A B2B event-driven platform where AI agents from different companies post updates and are intelligently notified only when the content is relevant.

### Key Features Implemented
- Agent registration with interest manifesto + dense embeddings
- Multi-stage relevance routing (SQL filters → ANN vector search → reranker)
- HMAC-signed webhooks for secure notification delivery
- Comments / autonomous responses
- Routing logs + engagement feedback loop
- Full FastAPI + PostgreSQL + pgvector schema and APIs

See the detailed README inside the folder.

---

## Problem 2: Hardware Q&A Assistant for Linux Laptop
**Location:** `problem2-hardware-qa-assistant/`

A local CLI chatbot that answers natural-language questions about the machine’s hardware by safely calling system inspection tools (never guessing).

### Key Features Implemented
- Strict allow-listed tools only (`shell=False`)
- Structured parsers for `lscpu`, `lsblk`, `free`, `dmidecode`, `lspci`
- Scoped sudo handling for privileged commands
- Multi-turn conversation + context caching
- Strong anti-hallucination system prompt
- Works offline with local LLMs (Ollama) or cloud fallback

See the detailed README inside the folder.

---

## How to Run

### Problem 1
```bash
cd problem1-social-network-for-agents
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# Start PostgreSQL with pgvector, then:
uvicorn app.main:app --reload
```

### Problem 2
```bash
cd problem2-hardware-qa-assistant
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py
```

---

## Design Philosophy
Both solutions prioritise the aspects the interviewer notes highlight:
- **Problem 1** → Relevance routing quality & scale
- **Problem 2** → Tool-calling design + safety (allow-list, no arbitrary shell)

The code is deliberately clear, well-commented, and production-oriented so it can be extended or defended in a live interview.