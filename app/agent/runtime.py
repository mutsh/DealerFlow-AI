import uuid

from app.agent.guardrails import requires_human
from app.agent.router import LocalRouter
from app.core.config import get_settings
from app.domain.schemas import ChatRequest, ChatResponse
from app.observability.tracing import Trace
from app.services.database import (
    create_handoff,
    get_session,
    save_session,
)
from app.services.dealership import DealershipService


YES_WORDS = {"yes", "y", "confirm", "confirmed", "ok", "okay", "go ahead"}

class DealerAfterSalesAgent:
    def __init__(self):
        self.router = LocalRouter()
        self.dealership = DealershipService()
        self.settings = get_settings()

    def _session_id(self, customer_id: str) -> str:
        # Stable cross-channel session for the pilot.
        return "S-" + uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"dealer-agent:{customer_id}",
        ).hex[:16]

    def _load_state(self, session_id: str, customer_id: str, channel: str):
        existing = get_session(session_id)
        if existing:
            return existing["state"], False

        state = {
            "service": None,
            "requested_date": None,
            "requested_time": None,
            "awaiting_confirmation": False,
            "disclosure_sent": False,
            "failure_count": 0,
        }
        save_session(session_id, customer_id, channel, state)
        return state, True

    def _handoff(self, session_id: str, customer_id: str, reason: str):
        handoff_id = "HO-" + uuid.uuid4().hex[:8].upper()
        create_handoff({
            "handoff_id": handoff_id,
            "session_id": session_id,
            "customer_id": customer_id,
            "reason": reason,
        })
        return handoff_id

    def handle(self, req: ChatRequest) -> ChatResponse:
        session_id = self._session_id(req.customer_id)
        state, is_new = self._load_state(
            session_id,
            req.customer_id,
            req.channel,
        )
        trace = Trace(session_id, req.channel)
        trace.event("request_received", message=req.message)

        prefix = ""
        if is_new or not state.get("disclosure_sent"):
            prefix = self.settings.ai_disclosure + "\n\n"
            state["disclosure_sent"] = True

        if requires_human(req.message):
            handoff_id = self._handoff(
                session_id,
                req.customer_id,
                "guardrail_escalation",
            )
            state["failure_count"] = 0
            save_session(session_id, req.customer_id, req.channel, state)
            trace.event("handoff", reason="guardrail_escalation")
            trace.finish("handoff")
            return ChatResponse(
                session_id=session_id,
                trace_id=trace.trace_id,
                response=prefix + (
                    "I’m handing this to a dealership colleague because it "
                    "needs human review. Please do not rely on the AI assistant "
                    "for an urgent vehicle-safety issue."
                ),
                status="handoff",
                handoff_id=handoff_id,
            )

        normalized = req.message.strip().lower()

        # Deterministic confirmation boundary: the LLM cannot commit a booking.
        if state.get("awaiting_confirmation") and normalized in YES_WORDS:
            result = self.dealership.create_booking(
                customer_id=req.customer_id,
                service=state["service"],
                date=state["requested_date"],
                time=state["requested_time"],
                idempotency_seed=(
                    f"{session_id}:{state['service']}:"
                    f"{state['requested_date']}:{state['requested_time']}"
                ),
            )
            trace.event(
                "tool_call",
                tool="create_booking",
                success=result.get("success", False),
            )

            if result.get("success"):
                booking_id = result["booking_id"]
                state.update({
                    "service": None,
                    "requested_date": None,
                    "requested_time": None,
                    "awaiting_confirmation": False,
                    "failure_count": 0,
                })
                save_session(session_id, req.customer_id, req.channel, state)
                trace.finish("success")
                return ChatResponse(
                    session_id=session_id,
                    trace_id=trace.trace_id,
                    response=prefix + (
                        f"Your appointment is confirmed for "
                        f"{result['appointment_date']} at "
                        f"{result['appointment_time']}. "
                        f"Booking ID: {booking_id}."
                    ),
                    status="confirmed",
                    booking_id=booking_id,
                )

            state["failure_count"] += 1
            save_session(session_id, req.customer_id, req.channel, state)
            trace.finish("tool_error")
            return ChatResponse(
                session_id=session_id,
                trace_id=trace.trace_id,
                response=prefix + (
                    "I could not complete the booking. "
                    "I can retry or hand this to the service team."
                ),
                status="error",
            )

        decision, raw = self.router.decide(req.message, state)
        trace.event(
            "router_decision",
            intent=decision.intent,
            raw_output=raw,
        )

        if decision.wants_human or decision.intent == "human_handoff":
            handoff_id = self._handoff(
                session_id,
                req.customer_id,
                "customer_or_router_handoff",
            )
            save_session(session_id, req.customer_id, req.channel, state)
            trace.finish("handoff")
            return ChatResponse(
                session_id=session_id,
                trace_id=trace.trace_id,
                response=prefix + (
                    "I’ll hand this conversation to a dealership colleague."
                ),
                status="handoff",
                handoff_id=handoff_id,
            )

        # Merge newly extracted fields into working memory.
        for field in ("service", "requested_date", "requested_time"):
            value = getattr(decision, field)
            if value:
                state[field] = value

        if decision.intent == "check_price":
            if not state.get("service"):
                response = "Which service would you like a price for?"
                status = "waiting_for_user"
            else:
                result = self.dealership.get_service_price(state["service"])
                trace.event("tool_call", tool="get_service_price", success=result.get("success"))
                if result.get("success"):
                    response = (
                        f"The listed price for {state['service'].replace('_', ' ')} "
                        f"is {result['price']} {result['currency']}."
                    )
                    status = "success"
                else:
                    response = "I could not find that service in the current catalogue."
                    status = "unsupported"

        elif decision.intent in {"check_availability", "start_booking"}:
            if not state.get("service"):
                response = "Which service do you need?"
                status = "waiting_for_user"
            elif not state.get("requested_date"):
                response = "What date would you like? Please use YYYY-MM-DD."
                status = "waiting_for_user"
            else:
                result = self.dealership.check_availability(
                    state["service"],
                    state["requested_date"],
                )
                trace.event("tool_call", tool="check_availability", success=result.get("success"))
                if not result.get("success"):
                    response = "I could not check that request. I can hand it to the service team."
                    status = "error"
                elif not result["slots"]:
                    response = (
                        f"There are no configured slots on {state['requested_date']}. "
                        "Please choose another date."
                    )
                    status = "waiting_for_user"
                elif state.get("requested_time"):
                    if state["requested_time"] not in result["slots"]:
                        response = (
                            "That time is not available. Available times are: "
                            + ", ".join(result["slots"])
                        )
                        status = "waiting_for_user"
                    else:
                        state["awaiting_confirmation"] = True
                        response = (
                            f"I can book {state['service'].replace('_', ' ')} on "
                            f"{state['requested_date']} at {state['requested_time']}. "
                            "Reply YES to confirm."
                        )
                        status = "awaiting_confirmation"
                else:
                    response = (
                        "Available times are: " + ", ".join(result["slots"]) +
                        ". Which time would you like?"
                    )
                    status = "waiting_for_user"

        elif decision.intent == "check_booking":
            if not decision.booking_id:
                response = "Please provide your booking ID."
                status = "waiting_for_user"
            else:
                result = self.dealership.get_booking(decision.booking_id)
                trace.event("tool_call", tool="get_booking", success=result.get("success"))
                if result.get("success"):
                    response = (
                        f"Booking {result['booking_id']} is {result['status']} for "
                        f"{result['appointment_date']} at {result['appointment_time']}."
                    )
                    status = "success"
                else:
                    response = "I could not find that booking."
                    status = "not_found"

        elif decision.intent == "cancel_booking":
            if not decision.booking_id:
                response = "Please provide the booking ID you want to cancel."
                status = "waiting_for_user"
            else:
                result = self.dealership.cancel_booking(decision.booking_id)
                trace.event("tool_call", tool="cancel_booking", success=result.get("success"))
                if result.get("success"):
                    response = f"Booking {decision.booking_id.upper()} is cancelled."
                    status = "cancelled"
                else:
                    response = "I could not find that booking."
                    status = "not_found"

        else:
            response = (
                "I can help with service prices, appointment availability, "
                "bookings, booking status, cancellations, or connect you with a person."
            )
            status = "success"

        save_session(session_id, req.customer_id, req.channel, state)
        trace.finish(status)

        return ChatResponse(
            session_id=session_id,
            trace_id=trace.trace_id,
            response=prefix + response,
            status=status,
        )
