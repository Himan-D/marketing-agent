from pydantic import BaseModel, Field
from typing import Optional, Any
from uuid import UUID
from datetime import datetime


class CampaignCreate(BaseModel):
    name: str = Field(..., max_length=255)
    criteria: dict = Field(default_factory=lambda: {
        "titles": [],
        "industries": [],
        "locations": [],
        "seniorities": [],
        "company_domains": [],
        "max_leads": 100,
    })
    target_leads: int = 100


class CampaignResponse(BaseModel):
    id: UUID
    name: str
    status: str
    criteria: dict
    target_leads: int
    leads_found: int
    emails_sent: int
    emails_opened: int
    emails_clicked: int
    replies_received: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class LeadResponse(BaseModel):
    id: UUID
    campaign_id: Optional[UUID] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    headline: Optional[str] = None
    email: Optional[str] = None
    email_verified: bool = False
    title: Optional[str] = None
    company: Optional[str] = None
    company_domain: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
    about: Optional[str] = None
    category: Optional[str] = None
    source: str = "apify_linkedin"
    source_campaign: Optional[str] = None
    stage: str = "LEAD"
    score: int = 0
    enriched: bool = False
    engagement_opened: bool = False
    engagement_clicked: bool = False
    engagement_replied: bool = False
    twenty_person_id: Optional[str] = None
    twenty_company_id: Optional[str] = None
    twenty_opportunity_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StageUpdate(BaseModel):
    stage: str = Field(..., pattern=r"^(LEAD|CONTACTED|OPENED|REPLIED|QUALIFIED|PROPOSAL|NEGOTIATION|CLOSED_WON|CLOSED_LOST)$")


class PipelineStage(BaseModel):
    stage: str
    count: int
    leads: list[LeadResponse] = []


class PipelineResponse(BaseModel):
    stages: list[PipelineStage]


class EmailSend(BaseModel):
    subject: str = Field(..., max_length=500)
    body: str


class EmailComposePreview(BaseModel):
    lead_id: UUID
    subject: str
    body: str
    recipient: Optional[str] = None


class TwentyTriggerEmail(BaseModel):
    person_id: str
    send_immediately: bool = True
    preview_only: bool = False


class TwentyEmailResult(BaseModel):
    person_id: str
    lead_id: Optional[str] = None
    status: str
    subject: Optional[str] = None
    body_preview: Optional[str] = None
    message_id: Optional[str] = None
    error: Optional[str] = None


class EmailEvent(BaseModel):
    event: str
    msg: dict
    ts: int
    _id: str


class BrevoWebhookEvent(BaseModel):
    event: str
    email: str
    id: int
    date: str
    ts: Optional[int] = None
    ts_event: Optional[int] = None
    message_id: Optional[int] = None
    subject: Optional[str] = None
    campaign_id: Optional[int] = None
    tag: Optional[str] = None
    sending_ip: Optional[str] = None
    ts_epoch: Optional[int] = None
    link: Optional[str] = None
    reason: Optional[str] = None
    status: Optional[str] = None


class InteractionLogResponse(BaseModel):
    id: UUID
    campaign_id: Optional[UUID] = None
    lead_id: Optional[UUID] = None
    agent_name: str
    action: str
    input_data: Optional[dict] = None
    output_data: Optional[dict] = None
    status: str
    duration_ms: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    model_used: Optional[str] = None
    created_at: datetime


class HealthResponse(BaseModel):
    status: str = "ok"
