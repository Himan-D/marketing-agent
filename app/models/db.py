import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Float, Enum, ForeignKey, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.utcnow()


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="draft")  # draft, running, completed, paused, failed
    criteria = Column(JSON, nullable=False, default=dict)

    target_leads = Column(Integer, default=100)
    leads_found = Column(Integer, default=0)
    emails_sent = Column(Integer, default=0)
    emails_opened = Column(Integer, default=0)
    emails_clicked = Column(Integer, default=0)
    replies_received = Column(Integer, default=0)

    created_at = Column(DateTime, default=utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class Lead(Base):
    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True)

    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    headline = Column(Text, nullable=True)
    email = Column(String(255), nullable=True)
    email_verified = Column(Boolean, default=False)
    title = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)
    company_domain = Column(String(255), nullable=True)
    industry = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    phone = Column(String(50), nullable=True)
    about = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)
    source = Column(String(50), nullable=False, default="apify_linkedin")
    source_campaign = Column(String(255), nullable=True)

    stage = Column(String(50), nullable=False, default="LEAD")
    score = Column(Integer, default=0)
    enriched = Column(Boolean, default=False)

    engagement_opened = Column(Boolean, default=False)
    engagement_clicked = Column(Boolean, default=False)
    engagement_replied = Column(Boolean, default=False)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    replied_at = Column(DateTime, nullable=True)

    twenty_person_id = Column(String(100), nullable=True)
    twenty_company_id = Column(String(100), nullable=True)
    twenty_opportunity_id = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True)

    subject = Column(String(500), nullable=True)
    body = Column(Text, nullable=True)
    message_id = Column(String(255), nullable=True, index=True)

    status = Column(String(50), nullable=False, default="queued")  # queued, sent, delivered, opened, clicked, bounced, failed
    mailchimp_id = Column(String(255), nullable=True)

    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    bounce_type = Column(String(50), nullable=True)

    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class InteractionLog(Base):
    __tablename__ = "interaction_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)

    agent_name = Column(String(100), nullable=False)  # researcher, emailer, scraper, funnel, orchestrator
    action = Column(String(100), nullable=False)      # search, compose, send, enrich, stage_change
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    status = Column(String(50), default="success")     # success, failed, skipped
    duration_ms = Column(Integer, nullable=True)

    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    model_used = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=utcnow)
