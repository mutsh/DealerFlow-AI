import json
import torch
from pydantic import ValidationError
from transformers import AutoModelForCausalLM, AutoTokenizer

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


class LocalRouter:
    def __init__(self):
        settings = get_settings()
        self.model_id = settings.model_id

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

        with torch.inference_mode():
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
