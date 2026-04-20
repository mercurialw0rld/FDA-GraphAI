# 🧬 Clinical Protocol Analyzer

> **Agentic pipeline for clinical trial protocol analysis powered by OpenFDA, LangGraph, and Gemini.**  
> Built as a project targeting clinical operations roles in regulated pharma environments.

---

## Overview

Clinical Protocol Analyzer is a multi-agent system that automates the pre-screening of pharmaceutical compounds for clinical trial feasibility. It ingests drug label data from the **OpenFDA API**, runs it through a **LangGraph** agentic workflow with automatic fallback logic, extracts structured **Adverse Event** profiles classified by GCP severity, and generates auditable clinical reports — all exposed through a **FastAPI** REST interface.

The system mirrors real workflows used in GCTO (Global Clinical Trial Operations) environments: multi-source data retrieval, data integrity validation, and audit-trail generation per ICH E6(R2) GCP standards.

---

## Architecture

```
User Request (Drug Name)
        │
        ▼
┌───────────────────┐
│   FastAPI Layer   │  ← REST endpoints + async handling
└────────┬──────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│                  LangGraph Workflow                  │
│                                                     │
│  fetch_fda ──► parse_adverse_events ──► analyze     │
│       ▲                                    │        │
│       │              quality_control ◄─────┘        │
│       │                    │                        │
│  [needs_more_info=True]    │ [needs_more_info=False] │
│       │                    ▼                        │
│  fallback_ct ◄──────  audit_export ──► END          │
│  (ClinicalTrials.gov)                               │
└─────────────────────────────────────────────────────┘
         │
         ▼
  Structured Report + Audit Trail (JSON)
```

**Nodes:**
| Node | Responsibility |
|---|---|
| `fetch_fda` | Queries OpenFDA Drug Label API with Pydantic validation |
| `parse_adverse_events` | LLM-powered structured extraction → `AdverseEvent[]` with severity |
| `analyze_protocol` | Generates 3-section clinical report (MoA / Risk / Monitoring) |
| `quality_control` | Detects missing critical fields, sets `needs_more_info` flag |
| `fallback_clinicaltrials` | Secondary source: ClinicalTrials.gov API v2 if FDA data incomplete |
| `audit_export` | SHA-256 hashed audit trail per node, GCP-compliant JSON output |

---

## Key Features

**Multi-source retrieval with automatic fallback**  
When OpenFDA returns incomplete records (missing `mechanism_of_action` or `adverse_reactions`), the graph automatically re-routes to ClinicalTrials.gov and merges the data before analysis. No silent failures.

**Structured Adverse Event extraction**  
Raw FDA adverse reaction text is parsed by the LLM into a typed Pydantic schema with severity classification (`Critical / Major / Minor`), organ system categorization, and automatic `red_flags` list — replicating real pharmacovigilance triage.

**GCP-compliant Audit Trail**  
Every node execution logs a timestamped entry with a SHA-256 hash of the data state. The final audit report is exportable as JSON and maps to ICH E6(R2) traceability requirements for inspection readiness.

**FastAPI REST Interface**  
Full async API with endpoints for single-drug analysis, batch processing, and audit trail retrieval.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agentic Workflow | LangGraph, LangChain |
| LLM | Google Gemini (via `langchain-google-genai`) |
| Data Validation | Pydantic v2 |
| API | FastAPI + Uvicorn |
| External Data | OpenFDA Drug Label API, ClinicalTrials.gov API v2 |
| Language | Python 3.11+ |

---

## Getting Started

**1. Clone and install**
```bash
git clone https://github.com/mercurialw0rld/FDA-RAG
cd FDA-RAG
pip install -r requirements.txt
```

**2. Configure environment**
```bash
cp .env.example .env
# Add your GOOGLE_API_KEY to .env
```

**3. Run the API**
```bash
uvicorn app.main:app --reload
```

**4. Analyze a drug**
```bash
curl -X POST "http://localhost:8000/analyze" \
  -H "Content-Type: application/json" \
  -d '{"drug_name": "Atorvastatin"}'
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/analyze` | Run full pipeline for a single drug |
| `GET` | `/audit/{drug_name}` | Retrieve audit trail for last analysis |
| `GET` | `/health` | API health check |

**Example response**
```json
{
  "drug": "Atorvastatin",
  "status": "complete",
  "data_sources_used": ["OpenFDA"],
  "adverse_events": {
    "total_critical": 2,
    "red_flags": ["rhabdomyolysis", "hepatotoxicity"],
    "events": [...]
  },
  "clinical_report": "...",
  "audit_trail_id": "audit_Atorvastatin_20260415.json"
}
```

---

## Clinical Context

This project models workflows used in **GCTO (Global Clinical Trial Operations)**:

- **Pre-screening phase**: Before a protocol is finalized, the safety profile of the investigational compound is reviewed against known adverse events. This tool automates that first-pass review.
- **Audit readiness**: The audit trail feature mirrors the documentation requirements inspectors expect under **ICH E6(R2) GCP** — traceability of what data was used, when, and by which process.
- **Data integrity**: The `quality_control` node flags missing or incomplete safety data, preventing silent propagation of gaps into clinical reports — a core concern in regulated environments.

---

## Limitations & Disclaimer

- OpenFDA data reflects approved drug labels and may not include post-marketing updates.
- Generated reports are for **research and portfolio demonstration purposes only** and do not constitute medical or regulatory advice.
- The fallback mechanism queries ClinicalTrials.gov public data; access to proprietary study data requires separate authorization.

---

## Author

**Facundo Kisielus**  
AI Engineer · CS Student @ Universidad de Buenos Aires  
[GitHub](https://github.com/mercurialw0rld) · facundokisielus@gmail.com