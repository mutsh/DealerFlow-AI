import os
import uuid

# Smoke tests must stay lightweight even if a developer's local .env enables Qwen.
os.environ["ROUTER_MODE"] = "rules"

from fastapi.testclient import TestClient

from app.main import app


def test_customer_booking_manager_and_handoff_smoke():
    customer_id = "smoke-" + uuid.uuid4().hex[:10]

    with TestClient(app) as client:
        # Service health and UI routes.
        assert client.get("/health").status_code == 200
        assert client.get("/ready").json()["status"] == "ready"
        assert client.get("/").status_code == 200
        assert client.get("/manager").status_code == 200

        # Multi-turn booking flow.
        first = client.post(
            "/api/v1/chat",
            json={
                "customer_id": customer_id,
                "channel": "web",
                "message": "I want to book an oil change on 2026-09-18 at 09:00",
            },
        )
        assert first.status_code == 200
        first_body = first.json()
        assert first_body["status"] == "awaiting_confirmation"

        confirmed = client.post(
            "/api/v1/chat",
            json={
                "customer_id": customer_id,
                "channel": "web",
                "message": "YES",
            },
        )
        assert confirmed.status_code == 200
        confirmed_body = confirmed.json()
        assert confirmed_body["status"] == "confirmed"
        assert confirmed_body["booking_id"].startswith("BK-")

        # Manager can see operational state.
        manager_headers = {"X-Manager-Key": "change-me"}
        summary = client.get(
            "/api/v1/manager/summary",
            headers=manager_headers,
        )
        assert summary.status_code == 200
        assert summary.json()["confirmed_bookings"] >= 1

        bookings = client.get(
            "/api/v1/manager/bookings",
            headers=manager_headers,
        )
        assert bookings.status_code == 200
        assert any(
            item["booking_id"] == confirmed_body["booking_id"]
            for item in bookings.json()["bookings"]
        )

        # Safety-sensitive input must hand off instead of autonomously proceeding.
        unsafe = client.post(
            "/api/v1/chat",
            json={
                "customer_id": "safety-" + uuid.uuid4().hex[:10],
                "channel": "web",
                "message": "My brakes failed and the car will not stop",
            },
        )
        assert unsafe.status_code == 200
        assert unsafe.json()["status"] == "handoff"
        assert unsafe.json()["handoff_id"].startswith("HO-")
