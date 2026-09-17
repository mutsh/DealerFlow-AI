from fastapi import APIRouter, Form, Request, Response
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from app.agent.runtime import DealerAfterSalesAgent
from app.core.config import get_settings
from app.domain.schemas import ChatRequest

router = APIRouter(prefix="/webhooks/twilio", tags=["twilio"])
_agent = None

def _get_agent():
    global _agent
    if _agent is None:
        _agent = DealerAfterSalesAgent()
    return _agent

def _is_valid_twilio_request(request: Request, form_data: dict) -> bool:
    settings = get_settings()
    # In development, allow requests when no token is configured.
    if not settings.twilio_auth_token:
        return settings.environment == "development"
    signature = request.headers.get("X-Twilio-Signature", "")
    validator = RequestValidator(settings.twilio_auth_token)
    return validator.validate(str(request.url), form_data, signature)

@router.post("/messaging")
async def messaging_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
):
    form_data = dict(await request.form())
    if not _is_valid_twilio_request(request, form_data):
        return Response(status_code=403, content="Invalid Twilio signature")

    channel = "whatsapp" if From.startswith("whatsapp:") else "sms"
    customer_id = From.replace("whatsapp:", "")

    result = _get_agent().handle(
        ChatRequest(
            customer_id=customer_id,
            channel=channel,
            message=Body,
        )
    )

    twiml = MessagingResponse()
    twiml.message(result.response)
    return Response(content=str(twiml), media_type="application/xml")
