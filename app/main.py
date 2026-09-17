from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agent.runtime import DealerAfterSalesAgent
from app.channels.twilio_messaging import router as twilio_router
from app.core.config import get_settings
from app.domain.schemas import ChatRequest, ChatResponse
from app.services.database import (
    get_manager_summary,
    init_db,
    list_appointments,
    list_handoffs,
)

settings = get_settings()
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title=settings.app_name,
    version="0.2.0-production-pilot",
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

agent: DealerAfterSalesAgent | None = None


@app.on_event("startup")
def startup():
    global agent
    init_db()
    agent = DealerAfterSalesAgent()


def get_agent() -> DealerAfterSalesAgent:
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent is not ready")
    return agent


def manager_auth(x_manager_key: str = Header(default="")):
    if x_manager_key != settings.manager_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


@app.get("/", include_in_schema=False)
def customer_app():
    return FileResponse(STATIC_DIR / "customer.html")


@app.get("/manager", include_in_schema=False)
def manager_app():
    return FileResponse(STATIC_DIR / "manager.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    return {"status": "ready" if agent is not None else "loading"}


@app.post("/api/v1/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    runtime: DealerAfterSalesAgent = Depends(get_agent),
):
    return runtime.handle(request)


@app.get("/api/v1/manager/summary")
def manager_summary(_: bool = Depends(manager_auth)):
    return get_manager_summary()


@app.get("/api/v1/manager/bookings")
def manager_bookings(_: bool = Depends(manager_auth)):
    return {"bookings": list_appointments()}


@app.get("/api/v1/manager/handoffs")
def manager_handoffs(_: bool = Depends(manager_auth)):
    return {"handoffs": list_handoffs()}


app.include_router(twilio_router)
