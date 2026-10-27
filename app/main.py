from fastapi import FastAPI
from app.schemas import GrievanceCategory, GrievanceSubmission, RoutingDecision

app = FastAPI(
    title="Securities Investor Grievance Routing API",
    description="Multi-agent AI service for securities investor grievance classification and evidence-grounded routing.",
    version="0.1.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "securities-investor-grievance-routing"}


@app.post("/api/v1/grievances/route", response_model=RoutingDecision)
def route_grievance(submission: GrievanceSubmission) -> RoutingDecision:
    text = submission.complaint_text.lower()
    if any(k in text for k in ("broker", "margin", "unauthorized trade", "contract note")):
        category = GrievanceCategory.BROKER_CONDUCT
        authority = "Stock Exchange Investor Grievance Redressal Panel (IGRP)"
    elif any(k in text for k in ("dividend", "bonus", "split", "rights issue")):
        category = GrievanceCategory.CORPORATE_ACTION
        authority = "Listed Issuer / SCORES Corporate Action Cell"
    elif any(k in text for k in ("demat", "pledge", "depository", "cdsl", "nsdl")):
        category = GrievanceCategory.DEPOSITORY_DEMAT
        authority = "Depository Grievance Cell (NSDL / CDSL)"
    else:
        category = GrievanceCategory.UNCLASSIFIED
        authority = "Centralized Investor Triage Desk"

    return RoutingDecision(
        category=category,
        target_authority=authority,
        priority="HIGH" if category == GrievanceCategory.BROKER_CONDUCT else "MEDIUM",
        confidence=0.85,
        rationale=f"Classified grievance against {submission.entity_name} as {category.value}.",
        regulatory_citations=["Master Circular on Online Resolution of Disputes in the Indian Securities Market"],
    )
