"""Phase 4/6: adversarial checks against the independent validator."""

import copy
import json
from datetime import datetime


AGREEMENT_ID = "validator_hardening"


def _prepare_validator_case(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/Presense.py")
    direct_vm.mock_web(
        r"https://api\.example\.com/health",
        {"method": "GET", "status": 200, "body": "ok"},
    )
    direct_vm.mock_web(
        r"https://docs\.example\.com/overview",
        {
            "method": "GET",
            "status": 200,
            "body": "Authentication uses the X-API-Key header. Example request: curl -H 'X-API-Key: secret' https://api.example.com/health",
        },
    )
    direct_vm.mock_llm(
        r".*Authentication.*X-API-Key.*",
        '{"score":9,"pass":true,"reason":"The docs explain authentication and show an example request.","evidence_quote":"Authentication uses the X-API-Key header."}',
    )

    now = int(
        datetime.fromisoformat(
            direct_vm._datetime.replace("Z", "+00:00")
        ).timestamp()
    )
    direct_vm.sender = direct_alice
    direct_vm.value = 1_000
    contract.create_agreement(
        agreement_id=AGREEMENT_ID,
        seller=direct_bob,
        manifest_json=json.dumps(
            {
                "schema": "presense.manifest.v1",
                "version": 1,
                "title": "Validator checks",
                "description": "Exercise the validator's decision-critical fields.",
                "criteria": [
                    {
                        "id": "C1",
                        "title": "Health endpoint",
                        "kind": "objective",
                        "check": "http_status",
                        "weight": 60,
                        "mandatory": True,
                        "params": {
                            "url": "https://api.example.com/health",
                            "expected_status": 200,
                        },
                    },
                    {
                        "id": "C2",
                        "title": "Documentation quality",
                        "kind": "subjective",
                        "check": "llm_rubric",
                        "weight": 40,
                        "mandatory": True,
                        "params": {
                            "evidence_url": "https://docs.example.com/overview",
                            "rubric": "The documentation must explain authentication and include an example request.",
                            "threshold": 7,
                            "max_chars": 4_000,
                        },
                    },
                ],
                "decision_policy": {
                    "accept_threshold": 80,
                    "partial_threshold": 50,
                    "mandatory_must_pass": True,
                    "missing_evidence": "UNDETERMINED",
                    "partial_payout": "pro_rata",
                    "score_rounding": "floor",
                },
                "evidence_policy": {
                    "allowed_domains": ["api.example.com", "docs.example.com"],
                    "require_https": True,
                    "max_bytes_per_source": 2_000_000,
                    "max_total_bytes": 10_000_000,
                    "max_sources_per_criterion": 5,
                    "allow_redirects": True,
                    "max_redirects": 3,
                },
            }
        ),
        manifest_url="",
        deadline=now + 86_400,
        challenge_window=3_600,
        metadata_url="",
    )
    direct_vm.sender = direct_bob
    contract.accept_agreement(AGREEMENT_ID)
    contract.submit_delivery(
        AGREEMENT_ID,
        ["https://docs.example.com/overview"],
        [""],
        "Completed docs.",
    )
    contract.evaluate(AGREEMENT_ID)

    agreement = contract._require_agreement(AGREEMENT_ID)
    submission = contract.submissions[agreement.submission_id]
    supplemental_sources = [
        {
            "url": submission.artifact_urls[index],
            "sha256": submission.artifact_hashes[index],
        }
        for index in range(len(submission.artifact_urls))
    ]
    payload = contract._build_verdict_payload(
        json.loads(agreement.manifest_json),
        agreement.manifest_hash,
        supplemental_sources,
    )
    return contract, payload


def test_validator_rejects_wrong_decision(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    _contract, payload = _prepare_validator_case(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    leader = copy.deepcopy(payload)
    leader["decision"] = "REJECT"

    assert direct_vm.run_validator(leader_result=leader) is False


def test_validator_rejects_wrong_objective_pass(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    _contract, payload = _prepare_validator_case(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    leader = copy.deepcopy(payload)
    leader["results"][0]["passed"] = False

    assert direct_vm.run_validator(leader_result=leader) is False


def test_validator_rejects_subjective_pass_mismatch(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    _contract, payload = _prepare_validator_case(
        direct_vm, direct_deploy, direct_alice, direct_bob
    )
    leader = copy.deepcopy(payload)
    leader["results"][1]["passed"] = False

    assert direct_vm.run_validator(leader_result=leader) is False