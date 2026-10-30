from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Complainant(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    investor_category: Literal["retail", "institutional"] = "retail"


class GrievanceSubmission(StrictModel):
    complaint_text: str = Field(min_length=20, max_length=5000)
    entity_name: str = Field(min_length=1, max_length=200)
    complainant: Complainant | None = None
    investor_id: str | None = Field(default=None, min_length=1, max_length=100)
    supporting_refs: list[str] = Field(default_factory=list, max_length=20)
    named_regulator: Literal["SEBI", "RBI", "unknown"] = "unknown"
    entity_type_claimed: Literal["bank", "amc", "broker", "depository", "rta", "listed_company", "unknown"] = "unknown"
    channel: Literal["web", "api"] = "web"
    incident_date: date | None = None
    approached_entity_first: bool = False
    entity_complaint_date: date | None = None
    entity_response: Literal["none", "pending", "rejected", "unsatisfactory", "resolved"] = "none"
    entity_response_date: date | None = None
    amount_involved_inr: float | None = Field(default=None, ge=0, le=1_000_000_000, allow_inf_nan=False)

    @field_validator("incident_date", "entity_complaint_date", "entity_response_date")
    @classmethod
    def plausible_date(cls, value):
        # Application input sanity limit, not a regulatory filing deadline.
        if value and value < date(1900, 1, 1):
            raise ValueError("Enter a date on or after 1 January 1900")
        if value and value > datetime.now(timezone.utc).date():
            raise ValueError("Dates must not be in the future")
        return value

    @model_validator(mode="after")
    def dates_and_prior_complaint(self):
        if not self.approached_entity_first and (self.entity_complaint_date or self.entity_response != "none" or self.entity_response_date):
            raise ValueError("Select 'I already complained in writing to the entity' before adding prior complaint details")
        if self.entity_complaint_date and self.incident_date and self.entity_complaint_date < self.incident_date:
            raise ValueError("Entity complaint date must not precede incident date")
        if self.entity_response_date and not self.entity_complaint_date:
            raise ValueError("Response date requires an entity complaint date")
        if self.entity_response_date and self.entity_response_date < self.entity_complaint_date:
            raise ValueError("Response date must not precede complaint date")
        return self


class Citation(StrictModel):
    chunk_id: str
    document_id: str
    document_title: str
    filename: str
    page: int = Field(ge=1)
    section: str
    quote: str = Field(min_length=1)
    sha256: str


class AgentEvent(StrictModel):
    agent: Literal["investigator", "verifier"]
    action: str
    detail: str


class RoutingDecision(StrictModel):
    domain: Literal["out_of_jurisdiction", "mutual_fund", "unclassified"]
    routing: Literal["refer_to_other_regulator", "assign_to_entity", "escalate_to_human"]
    target_authority: str
    immediate_action: str
    product: str
    entity_type: str
    rationale: str
    regulatory_citations: list[Citation] = Field(default_factory=list)
    next_steps: list[str]
    uncertain: bool = False
    eligibility: Literal["bank_first", "waiting_period", "potentially_eligible", "needs_review", "not_applicable"] = "not_applicable"
    timeline_days: int | None = None
    verification: str
    prompt_version: str = "phase0-v1"
    agent_trace: list[AgentEvent] = Field(default_factory=list)


class JobAccepted(StrictModel):
    run_id: str
    status: str
    status_url: str
    result_url: str


class JobStatus(StrictModel):
    run_id: str
    status: str
    error: str | None = None
