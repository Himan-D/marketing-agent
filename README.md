# Mirrorfit AI Marketing Agent

Automated B2B outreach agent for Mirrorfit.ai — researches fashion-industry leads, sends personalized virtual-try-on pitches via Brevo, and syncs all activity to Twenty CRM.

## Architecture

```
FastAPI app ←→ PostgreSQL (leads, campaigns, emails)
         ←→ Redis + ARQ (async task queue)
         ←→ Twenty CRM (REST API — people, companies, opportunities)
         ←→ Brevo API (email delivery + webhook tracking)
         ←→ Apify (LinkedIn profile scraping)
         ←→ vLLM (local LLM for email composition)
```

## Quick Start

### Prerequisites

- Python 3.12+
- Docker + Docker Compose
- GitHub account (for Apify)

### 1. Clone & Environment

```bash
cp .env.example .env
# Fill in your API keys:
#   TWENTY_API_KEY       — Twenty CRM API key (JWT)
#   TWENTY_BASE_URL      — http://localhost:3000
#   BREVO_API_KEY        — Brevo SMTP/API key
#   APIFY_API_TOKEN      — Apify API token
#   LLM_BASE_URL         — http://localhost:8000/v1 (vLLM)
```

### 2. Start Dependencies

```bash
docker compose up -d db redis
```

### 3. Start the Agent

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8084
```

### 4. Start Twenty CRM (separate)

```bash
cd twenty-crm
docker compose up -d
# Access UI at http://localhost:3000
```

## API Endpoints

### Campaigns
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/campaigns` | Create campaign |
| GET | `/api/v1/campaigns` | List campaigns |
| GET | `/api/v1/campaigns/{id}` | Get campaign |
| POST | `/api/v1/campaigns/{id}/start` | Run research + queue emails |
| DELETE | `/api/v1/campaigns/{id}` | Delete campaign |

### Leads
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/leads` | List all leads |
| GET | `/api/v1/leads?campaign_id={id}` | Filter by campaign |
| PATCH | `/api/v1/leads/{id}/stage` | Update pipeline stage |
| POST | `/api/v1/leads/{id}/compose-preview` | Preview email for lead |
| POST | `/api/v1/twenty/trigger-email` | Trigger email from Twenty CRM |

### Emails
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/emails/send` | Send email to lead |
| GET | `/api/v1/emails/logs` | List email logs |

### Webhooks
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/webhooks/brevo` | Brevo event webhook |

### Pipeline
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/pipeline/leads` | Leads grouped by stage |
| PATCH | `/api/v1/pipeline/lead/{id}` | Move lead to stage |

## Custom Fields (Twenty CRM)

On the Person object:
- `mirrorfitStatus` (SELECT) — Queued → Sent → Opened → Clicked → Replied → Bounced → Failed
- `mirrorfitSentAt` (DATE_TIME) — When email was sent
- `mirrorfitSubject` (TEXT) — Email subject line
- `mirrorfitOpens` (NUMBER) — Open count
- `mirrorfitScore` (NUMBER) — Lead score

## Pipeline Stages

```
LEAD → CONTACTED → OPENED → REPLIED → QUALIFIED → PROPOSAL → NEGOTIATION → CLOSED_WON/CLOSED_LOST
```

## Email Flow

1. Twenty CRM person → `POST /api/v1/twenty/trigger-email`
2. LLM composes personalized Mirrorfit email (or generic fallback)
3. Brevo sends the email
4. Brevo webhook → updates `mirrorfitStatus` in Twenty CRM in real-time

## Trigger Email from Twenty

Call the trigger-email endpoint with a Twenty person ID:

```bash
curl -X POST http://localhost:8084/api/v1/twenty/trigger-email \
  -H "Content-Type: application/json" \
  -d '{"person_id": "<twenty-person-uuid>", "preview_only": true}'
```

Set `"send_immediately": true` to send via Brevo.
