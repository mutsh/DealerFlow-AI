from pathlib import Path

from app.services import database
from app.services.dealership import DealershipService

def test_create_booking_is_idempotent(tmp_path, monkeypatch):
    test_db = tmp_path / "test.db"

    class FakeSettings:
        database_path = str(test_db)

    monkeypatch.setattr(database, "get_settings", lambda: FakeSettings())
    database.init_db()

    service = DealershipService()
    first = service.create_booking(
        customer_id="cust-1",
        service="oil_change",
        date="2026-09-18",
        time="09:00",
        idempotency_seed="same-operation",
    )
    second = service.create_booking(
        customer_id="cust-1",
        service="oil_change",
        date="2026-09-18",
        time="09:00",
        idempotency_seed="same-operation",
    )

    assert first["success"] is True
    assert second["success"] is True
    assert first["booking_id"] == second["booking_id"]
