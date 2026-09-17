# DealerFlow AI

**Production-oriented AI agent platform for car dealership after-sales operations.**

DealerFlow AI is a channel-agnostic service-booking assistant designed around the real operational lifecycle of dealership after-sales teams: customer conversations, pricing and availability checks, appointment confirmation, booking writes, human handoff, manager visibility, and failure tracing.

It currently supports a customer-facing web chat and dealership manager dashboard, plus inbound SMS/WhatsApp adapters through Twilio. Voice and live DMS/CRM integrations are the next production integrations.

> **Current status:** production-pilot foundation. The booking workflow is real application logic, but `DealershipService` currently uses a deterministic pilot catalogue and slot backend rather than a live dealership DMS. This keeps the repository safe and easy to run locally while preserving the same integration boundary a real client deployment would use.

## Why this project exists

The goal is not to build another chatbot demo. DealerFlow AI is structured around the full lifecycle expected from an operational AI-agent system:

**build → test → deploy → monitor → debug → improve**

The LLM handles language understanding and routing. Critical business operations remain typed, deterministic, confirmed, and observable.

## Key capabilities

- Local Hugging Face / Qwen routing model
- Multi-turn session state and working memory
- Customer-facing web booking assistant
- Dealership manager dashboard
- Service pricing and workshop availability tools
- Explicit confirm-before-write booking flow
- Idempotent appointment creation
- Booking lookup and cancellation
- Safety/complaint guardrails and human handoff
- AI disclosure on first interaction
- PII-aware JSONL trace logging
- SMS/WhatsApp inbound Twilio adapter
- Dockerfile and Azure deployment path
- Unit tests and GitHub Actions CI

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

```text
Customer channels
  ├─ Web chat
  ├─ SMS / WhatsApp
  └─ Voice (planned)
          ↓
      FastAPI
          ↓
Session / Working Memory
          ↓
     Guardrails
          ↓
Local LLM Router
          ↓
Agent Runtime / Policy
          ↓
Deterministic Tools
  ├─ Pricing
  ├─ Availability
  └─ Booking
          ↓
Confirmation + Idempotency
          ↓
Dealership Adapter
          ↓
DMS / CRM / Workshop Scheduler
```

## 5-minute local run

### Windows PowerShell

```powershell
git clone https://github.com/mutsh/DealerFlow-AI.git
cd DealerFlow-AI
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\run.ps1
```

### macOS / Linux

```bash
git clone https://github.com/mutsh/DealerFlow-AI.git
cd DealerFlow-AI
./run.sh
```

The scripts create a virtual environment, install dependencies, create `.env` from `.env.example` if needed, and start the application.

The first launch downloads `Qwen/Qwen2.5-1.5B-Instruct`, so startup is slower the first time. CPU inference works but can be slow; an NVIDIA GPU is optional.

Open:

- Customer assistant: `http://127.0.0.1:8000/`
- Manager dashboard: `http://127.0.0.1:8000/manager`
- API docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`
- Readiness: `http://127.0.0.1:8000/ready`

The manager dashboard uses the `MANAGER_API_KEY` in `.env`.

## Manual setup

If you prefer not to use the run scripts:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m pytest -q
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Example booking flow

1. Customer: `I need an oil change on 2026-09-18 at 09:00`
2. Agent extracts the service/date/time and verifies availability.
3. Agent proposes the appointment and asks for confirmation.
4. Customer replies `YES`.
5. Only then can the deterministic booking service create the appointment.
6. The confirmed booking becomes visible in the manager dashboard.

A safety-sensitive message such as:

```text
My brakes failed and the car will not stop
```

is escalated to a human instead of being handled autonomously.

## Manager operations

The manager dashboard provides operational visibility into:

- total bookings
- confirmed bookings
- cancellations
- human handoffs
- open handoffs
- recent appointment records

The API also exposes:

```text
GET /api/v1/manager/summary
GET /api/v1/manager/bookings
GET /api/v1/manager/handoffs
```

with the `X-Manager-Key` header.

## SMS / WhatsApp

The Twilio webhook is:

```text
POST /webhooks/twilio/messaging
```

For a real deployment:

- configure `TWILIO_AUTH_TOKEN`
- set `ENVIRONMENT=production`
- use a public HTTPS endpoint
- enable signature validation
- complete WhatsApp Business onboarding, opt-in, and template setup where required

## Voice

Voice should reuse the same runtime rather than introducing a separate business brain. A voice adapter can convert speech events into the same `ChatRequest` contract used by web/SMS/WhatsApp, preserving one policy, memory, tool, and guardrail layer.

## Important pilot boundary

`app/services/dealership.py` is the integration seam. In a real dealership deployment, replace that adapter with the client's DMS/CRM/workshop scheduler while keeping the agent runtime stable.

Before real customer use, add:

- real customer identity/authentication
- dealership tenant isolation
- production secrets management
- encrypted persistent storage
- central observability and alerting
- retention/privacy policies
- full agent regression evaluation
- load and resilience testing
- backup/recovery testing
- documented human escalation and incident runbooks

## Production deployment

See [`DEPLOY_AZURE.md`](DEPLOY_AZURE.md) for the proposed Azure production path, including Container Apps, PostgreSQL, Key Vault, managed identity, model serving, observability, CI/CD, and staged rollout.

## Suggested real-customer KPIs

- booking completion rate
- successful appointment-write rate
- manager correction/override rate
- human handoff rate
- containment rate
- tool failure rate
- duplicate-booking rate
- P50/P95 latency
- customer abandonment rate
- manager acceptance of AI-booked appointments

The target duplicate-booking rate should be **0%**.

## Testing

```powershell
python -m pytest -q
```

The included tests cover core guardrail behavior and idempotent dealership booking operations. The next milestone is a full agent regression/evaluation suite covering routing, trajectory correctness, conversation quality, safety, and failure recovery.
