from app.agent.guardrails import requires_human

def test_vehicle_safety_issue_escalates():
    assert requires_human("My brakes failed and the car won't stop") is True

def test_normal_price_question_does_not_escalate():
    assert requires_human("How much is an oil change?") is False
