# securities-investor-grievance-routing

Multi-agent AI service for securities investor grievance classification, jurisdiction determination, and evidence-grounded complaint routing using RAG, FastAPI, and Docker.

## Overview

This system automates the intake, analysis, and routing of investor complaints in the securities market:
- **Grievance Classification**: Categorizes investor complaints (e.g., unauthorized trading, dividend/corporate action delays, demat/remat issues, disclosure violations, broker default).
- **Jurisdiction Determination**: Identifies the appropriate regulatory body, exchange, depository, or registrar/transfer agent (RTA).
- **Evidence-Grounded Routing (RAG)**: Grounds routing decisions in regulatory circulars and guidelines with verifiable citations.

## Project Structure

```text
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI application and endpoints
│   └── schemas.py       # Pydantic models for grievance intake and routing output
├── Dockerfile           # Container image definition
├── requirements.txt     # Python dependencies
└── README.md
```

## Quickstart

### Local Development

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Docker

```bash
docker build -t grievance-router .
docker run -p 8000:8000 grievance-router
```
