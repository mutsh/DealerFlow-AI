import json
import re
import time
import uuid
from pathlib import Path
from app.core.config import get_settings

PHONE_RE = re.compile(r"\+?\d[\d\s\-]{7,}\d")
EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")

def redact(text: str) -> str:
    return EMAIL_RE.sub("[EMAIL]", PHONE_RE.sub("[PHONE]", text))

class Trace:
    def __init__(self, session_id: str, channel: str):
        self.trace_id = uuid.uuid4().hex
        self.started = time.perf_counter()
        self.data = {
            "trace_id": self.trace_id,
            "session_id": session_id,
            "channel": channel,
            "events": [],
        }

    def event(self, name: str, **fields):
        safe = {
            k: redact(v) if isinstance(v, str) else v
            for k, v in fields.items()
        }
        self.data["events"].append({
            "name": name,
            "t_ms": round((time.perf_counter() - self.started) * 1000, 2),
            **safe,
        })

    def finish(self, status: str):
        self.data["status"] = status
        self.data["total_ms"] = round(
            (time.perf_counter() - self.started) * 1000, 2
        )
        path = Path(get_settings().trace_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(self.data) + "\n")
