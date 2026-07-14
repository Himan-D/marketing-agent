import asyncio
import logging
import re
import time
from openai import AsyncOpenAI
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.core.mirrorfit_profile import get_mirrorfit_system_prompt
from app.core.email_strategy import get_category_prompt
from app.models.db import InteractionLog

logger = logging.getLogger(__name__)


def strip_llm_thinking(text: str) -> str:
    lines = text.split("\n")
    subject_idxs = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r"^subject\s*:", stripped, re.IGNORECASE):
            val = line.split(":", 1)[1].strip()
            if not val or val == "<line>":
                continue
            subject_idxs.append(i)
    if subject_idxs:
        text = "\n".join(lines[subject_idxs[-1]:])
    return text.strip()


class LLMService:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=15,
        )
        self.model = settings.llm_model_name

    async def compose_email(self, *, db: AsyncSession | None = None,
                            lead_id=None, campaign_id=None,
                            first_name: str = "", last_name: str = "",
                            title: str = "", company: str = "",
                            industry: str = "", about: str = "",
                            company_description: str = "",
                            category: str = "") -> tuple[str, str]:
        name = f"{first_name} {last_name}".strip() or "there"

        memory_context = ""
        campaign_stats = ""
        previous_subjects = ""
        if db and lead_id:
            memory_context = await self._get_lead_memory(db, lead_id)
        if db and campaign_id:
            campaign_stats, previous_subjects = await self._get_campaign_stats(db, campaign_id)

        system_prompt = get_mirrorfit_system_prompt() if settings.mirrorfit_mode else (
            "You are a B2B sales email writer. Write concise, personalized cold emails. "
            "Keep subject under 60 chars, body under 150 words. Professional but warm."
        )
        category_prompt = get_category_prompt(category)
        if category_prompt:
            system_prompt += category_prompt

        system_prompt += "\n\nOUTPUT ONLY THE EMAIL. First line must be 'Subject:'."

        user_prompt = f"""Write a cold email.

LEAD: {name}
ROLE: {title}
COMPANY: {company}
INDUSTRY: {industry}

{memory_context}
{campaign_stats}
{previous_subjects}

Output format:
Subject: <line>
Body: <content>"""

        start = time.time()
        try:
            resp = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                    max_tokens=2048,
                ),
                timeout=20,
            )
            duration = int((time.time() - start) * 1000)
            text = resp.choices[0].message.content or ""
            usage = resp.usage
            prompt_tokens = usage.prompt_tokens if usage else None
            completion_tokens = usage.completion_tokens if usage else None

            text = self._clean_llm_output(text)

            subject, body = self._extract_subject_body(text, company)

            if not subject:
                subject = f"Quick question about {company}" if company else "Quick question"

            if db and lead_id:
                await self._log_interaction(
                    db=db, lead_id=lead_id, campaign_id=campaign_id,
                    agent="emailer", action="compose",
                    input_data={"first_name": first_name, "last_name": last_name,
                                "title": title, "company": company, "industry": industry},
                    output_data={"subject": subject, "body_preview": body[:200]},
                    status="success", duration_ms=duration,
                    prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                )

            return subject, body

        except Exception as e:
            logger.error("LLM compose failed: %s", e)
            if db and lead_id:
                await self._log_interaction(
                    db=db, lead_id=lead_id, campaign_id=campaign_id,
                    agent="emailer", action="compose",
                    input_data={"error": str(e)},
                    output_data={}, status="failed",
                    duration_ms=int((time.time() - start) * 1000),
                )
            subject = f"Quick question about {company}" if company else "Hello"
            body = f"Hi {name},\n\nI came across {company} and thought we might be able to help. Would you be open to a quick chat?\n\nBest regards"
            return subject, body

    async def _get_lead_memory(self, db: AsyncSession, lead_id) -> str:
        result = await db.execute(
            select(InteractionLog)
            .where(InteractionLog.lead_id == lead_id)
            .order_by(desc(InteractionLog.created_at))
            .limit(10)
        )
        logs = result.scalars().all()
        if not logs:
            return ""

        lines = []
        for log in reversed(logs):
            ts = log.created_at.strftime("%Y-%m-%d %H:%M") if log.created_at else ""
            inp = log.input_data or {}
            out = log.output_data or {}
            if log.action == "compose":
                lines.append(f"[{ts}] Email composed: subject='{out.get('subject', '')}'")
            elif log.action == "send":
                lines.append(f"[{ts}] Email sent: status={log.status}")
            elif log.action == "search":
                lines.append(f"[{ts}] Research found leads: {inp.get('count', '?')}")
            elif log.action == "stage_change":
                lines.append(f"[{ts}] Stage changed: {inp.get('from', '?')} → {inp.get('to', '?')}")
            else:
                lines.append(f"[{ts}] {log.action}: {log.status}")
        return "\n".join(lines)

    async def _get_campaign_stats(self, db: AsyncSession, campaign_id) -> tuple[str, str]:
        from app.models.db import EmailLog, Lead
        result = await db.execute(
            select(EmailLog).where(EmailLog.campaign_id == campaign_id)
            .order_by(desc(EmailLog.created_at)).limit(20)
        )
        logs = result.scalars().all()
        subjects = [l.subject for l in logs if l.subject]
        unique = list(dict.fromkeys(subjects))
        stats = f"Total emails sent in campaign: {len(logs)}"
        return stats, "; ".join(unique[-5:]) if unique else ""

    @staticmethod
    def _clean_llm_output(text: str) -> str:
        text = strip_llm_thinking(text)
        return text

    @staticmethod
    def _extract_subject_body(text: str, company: str = "") -> tuple[str, str]:
        subject = ""
        body = text
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if re.match(r"^subject\s*:", line.strip(), re.IGNORECASE):
                subject = line.split(":", 1)[1].strip()
                body_lines = [l for j, l in enumerate(lines) if j != i]
                body = "\n".join(body_lines).strip()
                break
        body = re.sub(r"^body\s*:\s*", "", body, flags=re.IGNORECASE).strip()
        if not subject:
            subject = f"Quick question about {company}" if company else "Quick question"
        return subject, body

    async def _log_interaction(self, *, db: AsyncSession, lead_id=None, campaign_id=None,
                                agent: str, action: str, input_data: dict | None = None,
                                output_data: dict | None = None, status: str = "success",
                                duration_ms: int | None = None,
                                prompt_tokens: int | None = None,
                                completion_tokens: int | None = None):
        log = InteractionLog(
            lead_id=lead_id, campaign_id=campaign_id,
            agent_name=agent, action=action,
            input_data=input_data, output_data=output_data,
            status=status, duration_ms=duration_ms,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            model_used=self.model,
        )
        db.add(log)
        try:
            await db.commit()
        except Exception as e:
            logger.warning("Failed to save interaction log: %s", e)
            await db.rollback()
