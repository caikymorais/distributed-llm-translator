import json
import sys
from datetime import datetime, timezone
from typing import Any


def log_event(level: str, event: str, **fields: Any) -> None:
    """Imprime log estruturado em JSON para aparecer no terminal e no CloudWatch Logs."""
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level.upper(),
        "event": event,
        **fields,
    }
    print(json.dumps(payload, ensure_ascii=False), flush=True)
    sys.stdout.flush()
