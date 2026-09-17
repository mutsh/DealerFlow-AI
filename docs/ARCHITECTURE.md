# DealerFlow AI Architecture

```mermaid
flowchart TD
    A[Customer] --> B{Channel}
    B -->|Web Chat| C[FastAPI]
    B -->|SMS / WhatsApp| D[Twilio Adapter]
    B -->|Voice - planned| E[Voice Adapter]
    D --> C
    E --> C
    C --> F[Session + Working Memory]
    F --> G[Input Guardrails]
    G --> H[Local Hugging Face Router]
    H --> I[Agent Runtime / Policy]
    I --> J[Pricing Tool]
    I --> K[Availability Tool]
    I --> L[Booking Tool]
    L --> M[Confirmation + Idempotency]
    J --> N[Dealership Service Adapter]
    K --> N
    M --> N
    N --> O[(DMS / CRM / Calendar)]
    I --> P[Human Handoff]
    C --> Q[Tracing / Metrics]
    C --> R[Manager Dashboard]
```

## Design principles

- The LLM interprets language; deterministic services own business truth.
- Booking writes require explicit confirmation.
- Idempotency protects against duplicate appointment creation.
- High-risk/safety issues are escalated to humans.
- Channel adapters share one runtime instead of duplicating business logic.
- Traces support debugging and future evaluation/monitoring.
