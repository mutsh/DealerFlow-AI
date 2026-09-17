from typing import Literal, Optional
from pydantic import BaseModel, Field

Channel = Literal["web", "sms", "whatsapp", "voice"]
Intent = Literal[
    "check_price",
    "check_availability",
    "start_booking",
    "confirm_booking",
    "check_booking",
    "cancel_booking",
    "human_handoff",
    "general_question",
]

class RouterDecision(BaseModel):
    intent: Intent
    service: Optional[str] = None
    requested_date: Optional[str] = None
    requested_time: Optional[str] = None
    booking_id: Optional[str] = None
    wants_human: bool = False
    missing_information: list[str] = Field(default_factory=list)

class ChatRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=128)
    channel: Channel = "web"
    message: str = Field(min_length=1, max_length=4000)

class ChatResponse(BaseModel):
    session_id: str
    trace_id: str
    response: str
    status: str
    booking_id: Optional[str] = None
    handoff_id: Optional[str] = None
