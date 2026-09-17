# Azure Production Deployment Path

This guide describes the recommended evolution from the local production pilot
to a real customer-facing deployment.

## Target Azure architecture

```text
Internet / Customer Channels
        |
        v
Azure Front Door / WAF
        |
        v
Azure Container Apps
  - FastAPI
  - customer web app
  - manager web app
  - Twilio webhooks
        |
        +--------------------------+
        |                          |
        v                          v
Model endpoint                PostgreSQL Flexible Server
(Azure Foundry /              - sessions
 managed inference /          - bookings
 GPU model service)           - handoffs
        |
        v
Dealer DMS / CRM / workshop scheduler

Cross-cutting:
- Microsoft Entra ID / managed identity
- Azure Key Vault
- Application Insights / OpenTelemetry
- Log Analytics
- Azure Monitor alerts
- Container Registry
- GitHub Actions / Azure DevOps
```

## Phase 1 — Containerize and prove staging

1. Run all unit and agent regression tests locally.
2. Build the included Dockerfile.
3. Push the image to Azure Container Registry.
4. Create a staging Azure Container Apps environment.
5. Deploy the FastAPI/UI container.
6. Configure `/health` and `/ready` probes.
7. Keep the staging system disconnected from real dealership write APIs until
   the integration contract tests pass.

## Phase 2 — Replace SQLite

Do not use the local SQLite database for multi-instance production.

Move:
- sessions
- appointments
- handoffs
- manager-review data

to Azure Database for PostgreSQL Flexible Server.

Use a production compute tier, private networking where practical, automated
backups, and high availability appropriate to the dealership SLA.

## Phase 3 — Move secrets and identity

Do not store Twilio credentials, DMS keys, database passwords or model keys
inside `.env` files in production.

Use:
- Azure Key Vault
- managed identities
- RBAC / least privilege

The Container App should retrieve secrets through managed identity.

## Phase 4 — Separate model serving

Do not scale the application API and the LLM as one process indefinitely.

Production shape:

```text
FastAPI / Agent Runtime
       |
       v
Model Adapter
       |
       +--> managed model endpoint
       |
       +--> fallback endpoint
```

For Azure, evaluate:
- Microsoft Foundry model deployment / managed model endpoint
- a dedicated GPU inference service if the selected open model must be hosted
  directly

The model adapter should support:
- request timeout
- retry policy
- model version
- fallback model
- token/latency metrics
- circuit breaker
- kill switch

## Phase 5 — Observability

Instrument every customer request with a correlation/trace ID.

Capture:
- channel
- intent
- tool selected
- tool latency
- model latency
- total latency
- booking success
- handoff
- retry/fallback
- errors
- token/cost metrics where applicable

Do not put unrestricted customer PII into telemetry.

Send application telemetry through OpenTelemetry to Application Insights /
Azure Monitor.

Create alerts for:
- API 5xx rate
- `/ready` failures
- model endpoint errors
- DMS/booking API errors
- booking write failures
- duplicate booking attempts
- handoff spikes
- P95 latency
- database saturation

## Phase 6 — Secure the manager surface

The pilot uses an API key to make the workflow easy to test.

For production replace it with:
- Microsoft Entra ID authentication
- role-based authorization
- dealership/tenant scoping
- audit logs

A dealership manager must never be able to see another dealership's customers.

## Phase 7 — Real dealership integration

Create an adapter for each DMS/CRM/scheduler rather than putting vendor logic
inside the agent.

```text
Agent
  |
BookingService
  |
DealerAdapter interface
  |
  +-- Vendor A
  +-- Vendor B
  +-- Vendor C
```

For write operations implement:
- idempotency keys
- timeouts
- bounded retries
- conflict detection
- transaction status reconciliation
- human fallback

Do not retry a non-idempotent booking operation blindly.

## Phase 8 — Messaging channels

### SMS / WhatsApp
Configure Twilio to point to:

`https://<your-domain>/webhooks/twilio/messaging`

In production:
- configure the Twilio auth token in Key Vault
- validate every webhook signature
- use the official WhatsApp onboarding/opt-in process
- design template-message workflows where required

### Voice
Add a voice adapter that feeds recognized customer text into the same
`ChatRequest` / agent runtime.

Do not duplicate business logic for voice.

## Phase 9 — Deployment pipeline

Recommended CI/CD:

```text
Pull Request
  |
  +--> lint / static checks
  +--> unit tests
  +--> tool contract tests
  +--> guardrail tests
  +--> agent regression evals
  +--> Docker build
  |
Merge
  |
  +--> deploy staging
  +--> smoke tests
  +--> dealership integration tests
  +--> approval
  |
  +--> production canary
  +--> monitor
  +--> full rollout
```

Production deployment should be automatically blocked if critical evaluation
or integration thresholds fail.

## Phase 10 — Customer pilot gates

Before real customers:

- written dealership approval
- staging/sandbox DMS verification
- GDPR/data-processing review
- privacy notice and retention rules
- AI disclosure
- customer-to-dealership tenant isolation
- human escalation runbook
- operational owner/on-call contact
- incident rollback/kill switch
- backup/restore test
- load test
- manager training
- agreed KPI baseline

## Core business KPIs

Track:
- booking completion rate
- appointment write success
- duplicate booking rate
- manager correction rate
- handoff rate
- customer abandonment
- P50/P95 latency
- DMS/API failure rate
- cancellation success
- dealership manager acceptance
- customer arrival / no-show where the DMS exposes it
