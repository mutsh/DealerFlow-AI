import json
import re
from pydantic import ValidationError

from app.core.config import get_settings
from app.domain.schemas import RouterDecision


ROUTER_PROMPT = """
You are the routing layer for a European car-dealership after-sales assistant.

Return ONLY valid JSON.

INTENTS:
- check_price
- check_availability
- start_booking
- confirm_booking
- check_booking
- cancel_booking
- human_handoff
- general_question

SUPPORTED SERVICES:
- oil_change
- brake_service
- tire_change

RULES:
- Never invent prices, slots, bookings or customer data.
- Never call tools yourself.
- Extract only fields the customer actually supplied.
- Dates must be YYYY-MM-DD. If vague, leave null.
- Times must be HH:MM. If vague, leave null.
- Normalize obvious service wording.
- A request for a human, a complaint, a safety concern, a payment dispute,
  a warranty dispute, or repeated failure should use human_handoff.
- If the user simply says yes/confirm and context says a booking is awaiting
  confirmation, use confirm_booking.
- Return no prose and no markdown.

OUTPUT:
{
  "intent": "...",
  "service": null,
  "requested_date": null,
  "requested_time": null,
  "booking_id": null,
  "wants_human": false,
  "missing_information": []
}
""".strip()


class RuleBasedRouter:
    """Zero-key fallback router for easy local demos and CI."""

    SERVICE_PATTERNS = {
        "oil_change": ("oil change", "oil service", "engine oil"),
        "brake_service": ("brake service", "brakes", "brake"),
        "tire_change": ("tire change", "tyre change", "tires", "tyres", "tire", "tyre"),
    }

    def _service(self, text: str):
        for service, phrases in self.SERVICE_PATTERNS.items():
            if any(p in text for p in phrases):
                return service
        return None

    def decide(self, message: str, state: dict) -> tuple[RouterDecision, str]:
        text = message.strip().lower()
        service = self._service(text)

        date_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
        time_match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
        booking_match = re.search(r"\b(BK-[A-Z0-9]{6,})\b", message.upper())

        requested_date = date_match.group(1) if date_match else None
        requested_time = None
        if time_match:
            requested_time = f"{int(time_match.group(1)):02d}:{time_match.group(2)}"

        booking_id = booking_match.group(1) if booking_match else None

        human_terms = (
            "human", "person", "agent", "manager", "complaint",
            "payment dispute", "warranty dispute",
        )

        if any(term in text for term in human_terms):
            intent = "human_handoff"
            wants_human = True
        elif "cancel" in text:
            intent = "cancel_booking"
            wants_human = False
        elif any(term in text for term in ("booking status", "check booking", "find booking", "my booking")):
            intent = "check_booking"
            wants_human = False
        elif any(term in text for term in ("price", "cost", "how much")):
            intent = "check_price"
            wants_human = False
        elif any(term in text for term in ("available", "availability", "slot", "slots")):
            intent = "check_availability"
            wants_human = False
        elif any(term in text for term in ("book", "appointment", "schedule")):
            intent = "start_booking"
            wants_human = False
        elif service or requested_date or requested_time:
            # Supports natural multi-turn follow-ups such as "oil change",
            # "2026-09-18", then "09:00".
            intent = "start_booking"
            wants_human = False
        else:
            intent = "general_question"
            wants_human = False

        decision = RouterDecision(
            intent=intent,
            service=service,
            requested_date=requested_date,
            requested_time=requested_time,
            booking_id=booking_id,
            wants_human=wants_human,
            missing_information=[],
        )
        return decision, "rule_based_router"


class LocalLLMRouter:
    """Optional Hugging Face/Qwen router. Enable with ROUTER_MODE=local_llm."""

    def __init__(self):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        settings = get_settings()
        self.model_id = settings.model_id
        self.torch = torch

        print(f"Loading local routing model: {self.model_id}")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_id)

        if torch.cuda.is_available():
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                dtype="auto",
                device_map="auto",
                low_cpu_mem_usage=True,
            )
        else:
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                dtype=torch.float32,
                device_map={"": "cpu"},
                low_cpu_mem_usage=True,
            )

        self.model.eval()
        self.device = next(self.model.parameters()).device

    def _generate(self, messages: list[dict]) -> str:
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)

        with self.torch.inference_mode():
            output = self.model.generate(
                **inputs,
                max_new_tokens=220,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        completion = output[:, inputs["input_ids"].shape[1]:]
        return self.tokenizer.batch_decode(
            completion,
            skip_special_tokens=True,
        )[0].strip()

    @staticmethod
    def _json(text: str) -> dict:
        cleaned = text.replace("```json", "").replace("```", "").strip()
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end < start:
            raise ValueError("No JSON object in router output")
        return json.loads(cleaned[start:end + 1])

    def decide(self, message: str, state: dict) -> tuple[RouterDecision, str]:
        context = {
            "awaiting_confirmation": state.get("awaiting_confirmation", False),
            "pending_service": state.get("service"),
            "pending_date": state.get("requested_date"),
            "pending_time": state.get("requested_time"),
        }

        messages = [
            {"role": "system", "content": ROUTER_PROMPT},
            {
                "role": "user",
                "content": (
                    f"SESSION_CONTEXT:\n{json.dumps(context)}\n\n"
                    f"CUSTOMER_MESSAGE:\n{message}"
                ),
            },
        ]

        raw = self._generate(messages)

        try:
            decision = RouterDecision.model_validate(self._json(raw))
            return decision, raw
        except (ValidationError, ValueError, json.JSONDecodeError):
            return RouterDecision(
                intent="human_handoff",
                wants_human=True,
                missing_information=["router_validation_failed"],
            ), raw


class LocalRouter:
    """Router facade used by the runtime.

    Default mode is the lightweight rules fallback so the project starts on a
    normal laptop with no model download. Set ROUTER_MODE=local_llm to use Qwen.
    """

    def __init__(self):
        settings = get_settings()
        mode = settings.router_mode.strip().lower()

        if mode == "local_llm":
            self.backend = LocalLLMRouter()
        else:
            print("Using lightweight rule-based router (ROUTER_MODE=rules)")
            self.backend = RuleBasedRouter()

    def decide(self, message: str, state: dict) -> tuple[RouterDecision, str]:
        return self.backend.decide(message, state)
