"""Run a local end-to-end MVP triage trace without any API key."""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=False)
except ImportError:
    pass

from aegis_fraud_triage.agent import AegisFraudTriageAgent
from aegis_fraud_triage.models import TriageRequest
from aegis_fraud_triage.tool_authorisation import local_demo_context


if __name__ == "__main__":
    message = " ".join(sys.argv[1:]).strip() or "I just sent a PayID transfer and now think it was a scam."
    root = Path(__file__).parent
    customer_reference = "cli-demo"
    result = AegisFraudTriageAgent(root / "logs").run(TriageRequest(message, customer_reference=customer_reference, channel="cli", tool_authorisation=local_demo_context(customer_reference, "local-cli-session")))
    print(json.dumps(result.as_dict(), indent=2, ensure_ascii=False))
