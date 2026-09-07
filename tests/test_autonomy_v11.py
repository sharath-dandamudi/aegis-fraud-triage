import json
from pathlib import Path

from aegis_fraud_triage.agent import AegisFraudTriageAgent
from aegis_fraud_triage.models import TriageRequest
from aegis_fraud_triage.tool_authorisation import local_demo_context


ROOT = Path(__file__).parents[1]


def request(message: str) -> TriageRequest:
    reference = "autonomy-test-customer"
    return TriageRequest(message, customer_reference=reference, tool_authorisation=local_demo_context(reference, "autonomy-test-session"))


def test_urgent_override_regression_pack(tmp_path):
    cases = [json.loads(line) for line in (ROOT / "data" / "urgent_override_regression_v1.jsonl").read_text().splitlines() if line]
    agent = AegisFraudTriageAgent(tmp_path)
    override_count = 0
    for case in cases:
        result = agent.run(request(case["message"]))
        if case["expected_urgent"]:
            assert result.route.value == "urgent_fraud", case["case_id"]
            assert result.escalation_required, case["case_id"]
            override_count += result.urgent_override_triggered
        else:
            assert not result.urgent_override_triggered, case["case_id"]
    assert override_count >= 10


def test_review_case_package_is_complete_and_redacted(tmp_path):
    result = AegisFraudTriageAgent(tmp_path).run(request("I just sent a PayID transfer and shared code 123456 with the caller."))
    assert result.review_required
    assert result.case_package and result.case_package["completeness"]
    assert result.case_package["status"] == "ready_for_human_review"
    assert "[REDACTED_CODE]" in result.case_package["redacted_case_summary"]
    assert result.case_package["boundary"].startswith("Internal review package")


def test_response_contract_is_evidence_backed_and_server_validated(tmp_path):
    result = AegisFraudTriageAgent(tmp_path).run(request("How can I stay safe when using PayID to buy something online?"))
    assert result.response_contract and result.response_contract.schema_valid
    assert result.response_contract.evidence_backed
    assert result.response_contract.citations
    assert any(gate.name == "structured_response_contract" and gate.passed for gate in result.gates)
