# Expense Chatbot API (v2.0)

A **production-grade conversational expense management backend** that allows users to:

- Log expenses using natural language  
- Query historical expenses with **strict numerical correctness**
- Receive deterministic, non-hallucinated answers
- Interact conversationally when queries are not expense-related

This system is intentionally **not a “chatbot toy”**.  
It is designed as a **reliability-first, audit-safe AI system** where:
- **LLMs never invent numbers**
- **Python is the sole authority for computation**
- **Every agent has a single, enforced responsibility**

---

## 🧠 Core Philosophy

> **LLMs assist. They do not decide. They do not compute. They do not hallucinate.**

This project follows three hard rules:

1. **Deterministic Execution First**
   - All numerical answers come from the database via Python logic
   - LLMs only extract intent or generate natural language wrappers

2. **Single Authority per Phase**
   - Routing, parsing, execution, and answering are strictly separated
   - No layer “fixes” or “guesses” outputs of another layer

3. **Failure Is Explicit**
   - Errors are returned in structured envelopes
   - No silent fallbacks or hidden defaults

---

## 🏗️ High-Level Architecture

```

User Input
↓
Router Agent (LLM)
↓
Intent Object
↓
Executor
├── Expense Executor
├── Query Executor
└── Conversation Executor
↓
Deterministic Response

````

Each stage is **observable, testable, and replaceable**.

---

## 📦 Major Components

### 1. Router Agent
Determines **what the user wants**, nothing more.

Routes input into one of:
- `expense` → logging a new expense
- `query` → querying historical data
- `conversation` → general chat

> Output is a **numeric route**, not free-form text.

---

### 2. Expense Pipeline

**Purpose:** Convert natural language into structured expense data.

**Flow:**
1. LLM extracts structured fields (amount, date, category, companions, etc.)
2. Schema validation via Pydantic
3. Friendly confirmation message generation
4. No database writes happen implicitly

**Guarantees:**
- No hallucinated fields
- Currency normalized (₹)
- Missing data defaults safely

---

### 3. Query Pipeline (Most Critical Part)

This is the **core differentiator** of the system.

#### Phases

1. **Pre-Parsing (Deterministic)**
   - Regex + rules extract dates, amounts, categories

2. **LLM Intent Hinting (Non-authoritative)**
   - LLM may suggest grouping, limits, columns
   - These hints are **never trusted blindly**

3. **Reconciliation Layer**
   - Deterministic rules override LLM suggestions
   - Semantic conflicts are resolved explicitly

4. **Query Shape Resolution**
   - Every query is classified as:
     - `LIST`
     - `AGGREGATE`
     - `GROUPED`
   - Execution is blocked if shape is unresolved

5. **Execution**
   - Prisma queries only
   - Python computes all aggregates

6. **Answer Generation**
   - LLM **only formats**
   - Never computes or infers numbers

---

### 4. Conversation Mode

Handles:
- Greetings
- Help
- General chat

This mode is **fully isolated** from expense or query logic.

---

## 🧪 Testing & Safety

This repository contains **serious tests**, not placeholders.

### Test Categories

- **Routing correctness**
- **Semantic invariants**
- **Failure envelopes**
- **Zero-data safety**
- **Query integrity**
- **System-wide contracts**

A query that could hallucinate or miscount **fails loudly**.

---

## 🗄️ Database Design

- PostgreSQL via Prisma
- Strong relational integrity
- Explicit enums for sender/source
- No polymorphic ambiguity

Key models:
- `User`
- `Expense`
- `Message`
- `ConversationState`

---

## ⚙️ Environment Setup

### Requirements
- Python 3.11+
- PostgreSQL
- Google Gemini API key

### Environment Variables

Create `.env` from `.env.example`:

```env
GOOGLE_API_KEY=your_key_here
DATABASE_URL=postgresql://...
DEBUG=false
PORT=8000
````

---

## ▶️ Running the Server

```bash
pip install -r requirements.txt
python API_LAYER/app.py
```

Health check:

```
GET /health
```

Main endpoint:

```
POST /process
{
  "text": "How much did I spend on food last month?",
  "user_id": "uuid"
}
```

---

## 📊 Observability

Built-in endpoints:

* `/health` → system status
* `/metrics` → request counts by intent
* Structured JSON logs (no print debugging)

---

## 🚫 Explicit Non-Goals

This system **does NOT**:

* Auto-correct user intent
* Guess missing filters
* Infer numbers from text
* Use embeddings for numeric queries
* “Sound confident” when data is missing

If data is missing → **the answer says so**

---

## 🧭 Who This Project Is For

This codebase is ideal if you care about:

* AI systems that **cannot lie**
* Financial correctness
* Agentic systems with boundaries
* Production-safe LLM usage
* Learning how to architect real AI backends

This is **not** a demo.
This is a **foundation**.

---

## 📌 Status

**Version:** 2.0
**Stability:** Production-ready core
**Next directions:**

* Multi-user auth layers
* External messaging integrations (Telegram already scaffolded)
* Read-only analytics dashboards

---

## 🧠 Final Note

> “If an AI system can hallucinate money, it should not touch money.”

This repository enforces that principle end-to-end.

---


