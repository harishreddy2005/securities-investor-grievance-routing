from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class GrievanceCategory(str, Enum):
    BROKER_CONDUCT = "broker_conduct"
    CORPORATE_ACTION = "corporate_action"
    DEPOSITORY_DEMAT = "depository_demat"
    RTA_SHARE_TRANSFER = "rta_share_transfer"
    MUTUAL_FUND = "mutual_fund"
    DISCLOSURE_GOVERNANCE = "disclosure_governance"
    UNCLASSIFIED = "unclassified"


class GrievanceSubmission(BaseModel):
    investor_id: str = Field(..., description="Unique identifier for the investor")
    entity_name: str = Field(..., description="Name of the intermediary or listed company")
    complaint_text: str = Field(..., min_length=10, description="Detailed grievance description")
    supporting_refs: Optional[List[str]] = Field(default=None, description="Reference IDs or document citations")


class RoutingDecision(BaseModel):
    category: GrievanceCategory
    target_authority: str
    priority: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: str
    regulatory_citations: List[str] = Field(default_factory=list)
