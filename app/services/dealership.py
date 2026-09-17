import hashlib
import uuid
from datetime import datetime

from app.services.database import (
    cancel_appointment,
    create_appointment,
    get_appointment,
)

SERVICES = {
    "oil_change": {"price": 1200, "currency": "DKK"},
    "brake_service": {"price": 2500, "currency": "DKK"},
    "tire_change": {"price": 800, "currency": "DKK"},
}

SLOTS = {
    "2026-09-18": ["09:00", "11:30", "14:00"],
    "2026-09-19": ["10:00", "13:00"],
    "2026-09-20": ["08:30", "12:30", "15:00"],
}

class DealershipService:
    def get_service_price(self, service: str) -> dict:
        item = SERVICES.get(service)
        if not item:
            return {"success": False, "error": "SERVICE_NOT_FOUND"}
        return {"success": True, "service": service, **item}

    def check_availability(self, service: str, date: str) -> dict:
        if service not in SERVICES:
            return {"success": False, "error": "SERVICE_NOT_FOUND"}
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return {"success": False, "error": "INVALID_DATE_FORMAT"}
        slots = SLOTS.get(date, [])
        return {
            "success": True,
            "service": service,
            "date": date,
            "available": bool(slots),
            "slots": slots,
        }

    def create_booking(
        self,
        customer_id: str,
        service: str,
        date: str,
        time: str,
        idempotency_seed: str,
    ) -> dict:
        availability = self.check_availability(service, date)
        if not availability.get("success"):
            return availability
        if time not in availability["slots"]:
            return {"success": False, "error": "SLOT_NOT_AVAILABLE"}

        idem = hashlib.sha256(idempotency_seed.encode()).hexdigest()[:24]
        record = {
            "booking_id": "BK-" + uuid.uuid4().hex[:8].upper(),
            "customer_id": customer_id,
            "service": service,
            "appointment_date": date,
            "appointment_time": time,
            "status": "confirmed",
            "idempotency_key": idem,
        }
        stored = create_appointment(record)
        return {"success": True, **stored}

    def get_booking(self, booking_id: str) -> dict:
        item = get_appointment(booking_id)
        if not item:
            return {"success": False, "error": "BOOKING_NOT_FOUND"}
        return {"success": True, **item}

    def cancel_booking(self, booking_id: str) -> dict:
        item = get_appointment(booking_id)
        if not item:
            return {"success": False, "error": "BOOKING_NOT_FOUND"}
        cancelled = cancel_appointment(booking_id)
        return {"success": True, **cancelled}
