# Agentic AI IT Support & Ticket Resolution System

A Python-based IT support application that combines an AI troubleshooting workflow with role-based ticket management and human review. Built as a portfolio project to demonstrate practical GenAI, RAG, and support automation.

## Features

- **Employee portal:** Sign in, submit IT incidents, and view your own tickets.
- **AI-assisted ticket handling:** Classify incidents and generate troubleshooting recommendations using an LLM and retrieval-augmented generation (RAG).
- **IT Support portal:** Review tickets, record employee contact, manage support cases, and resolve confirmed issues.
- **IT Admin portal:** Review escalated cases and manage employee accounts.
- **Ticket lifecycle:** Support-case history, escalation, human review, and dashboard counts.
- **Access controls:** Role-based access for employee, IT support, and IT admin.

## Tech stack

| Area | Technologies |
| --- | --- |
| Application | Python, Streamlit |
| LLM and orchestration | Groq, LangChain, LangGraph |
| Retrieval | RAG, ChromaDB, Hugging Face sentence-transformers |
| Database | PostgreSQL, SQLAlchemy, psycopg2 |
| Data validation | Pydantic |
| Documents | PDF and text/document processing libraries |

## High-level workflow

```text
Employee submits issue
         |
         v
Validation + AI workflow (LangGraph)
         |
         +--> Classification / priority
         |
         +--> RAG troubleshooting retrieval
         |
         v
Ticket saved in PostgreSQL
         |
         v
IT Support reviews and contacts employee
         |
         +--> Confirmed fixed --> Resolved
         |
         +--> Unresolved --> Escalation --> IT Admin human review
```

The AI workflow status and human support-case status are tracked separately.

## Run locally

### 1. Clone the repository

```bash
git clone https://github.com/Ganjikunta-sai/Agentic-AI-IT-Support-System.git
cd Agentic-AI-IT-Support-System
```

### 2. Create a Python virtual environment

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Configure services

Set up a PostgreSQL database and a Groq API key. Store credentials in a local `.env` file or another secure configuration source; **never commit secrets**.

Example placeholders (adjust variable names to the project's configuration):

```dotenv
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:5432/DATABASE
GROQ_API_KEY=YOUR_GROQ_API_KEY
```

Database tables, role accounts, and the document/vector knowledge base must be initialized for your environment before the complete workflow can be used.

### 4. Start the app

```powershell
python -m streamlit run app.py
```

Open the local URL displayed in the terminal.

## Main application areas

- **Employee:** Submit Ticket, My Tickets
- **IT Support:** Overview, Ticket Management, Escalation Center, Workflow Diagnostics
- **IT Admin:** Human Review, Employee Management

## Deployment notes

A public deployment requires more than publishing Streamlit:
- A reachable, hosted PostgreSQL instance instead of a local `localhost` database
- Secure cloud configuration for the Groq API key and database credentials
- Initialized user accounts and tables
- A suitable strategy for ChromaDB persistence and RAG knowledge-base initialization
- Persistent LangGraph workflow checkpoints if workflows must survive restarts

Do not publish real employee tickets, passwords, tokens, or local database dumps.

## Project status

The repository contains a working local-project implementation; cloud deployment and end-to-end production hardening should be verified separately. This is a portfolio/demo application, not a claim of production readiness.

## Author

[GitHub — Ganjikunta-sai](https://github.com/Ganjikunta-sai) · [LinkedIn](https://www.linkedin.com/in/leelavenkatasaiganjikunta/)
