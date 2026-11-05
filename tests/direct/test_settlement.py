"""Phase 5: verdict payout, challenge window, and settlement."""

from datetime import datetime, timezone
import hashlib
import json
import re

import pytest


ESCROW = 10**18 + 7
CHALLENGE_WINDOW = 3_600


def transaction_now(vm) -> int:
    return int(datetime.fromisoformat(vm._datetime.replace("Z", "+00:00")).timestamp())


def set_transaction_time(vm, timestamp: int) -> None:
    vm._datetime = datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def make_manifest() -> str:
    criteria = []
    for criterion_id, weight, url in (
        ("C1", 72, "https://api.example.com/ok"),
        ("C2", 28, "https://api.example.com/fail"),
    ):
        criteria.append(
            {
                "id": criterion_id,
                "title": criterion_id,
                "kind": "objective",
                "check": "http_status",
                "weight": weight,
                "mandatory": False,
                "params": {"url": url, "expected_status": 200},
            }
        )
    return json.dumps(
        {
            "schema": "presense.manifest.v1",
            "version": 1,
            "title": "Settlement test",
            "description": "A manifest for Phase 5 settlement tests.",
            "criteria": criteria,
            "decision_policy": {
                "accept_threshold": 80,
                "partial_threshold": 50,
                "mandatory_must_pass": True,
                "missing_evidence": "REJECT",
                "partial_payout": "pro_rata",
                "score_rounding": "floor",
            },
            "evidence_policy": {
                "allowed_domains": ["api.example.com"],
                "require_https": True,
                "max_bytes_per_source": 2_000_000,
                "max_total_bytes": 10_000_000,
                "max_sources_per_criterion": 5,
                "allow_redirects": True,
                "max_redirects": 3,
            },
        }
    )


def submitted_agreement(contract, vm, buyer, seller, agreement_id="agreement_1"):
    now = transaction_now(vm)
    vm.sender = buyer
    vm.value = ESCROW
    contract.create_agreement(
        agreement_id=agreement_id,
        seller=seller,
        manifest_json=make_manifest(),
        manifest_url="",
        deadline=now + 86_400,
        challenge_window=CHALLENGE_WINDOW,
        metadata_url="",
    )
    vm.sender = seller
    contract.accept_agreement(agreement_id)
    contract.submit_delivery(
        agreement_id,
        ["https://api.example.com/delivery"],
        [""],
        "Delivered artifact.",
    )
    vm.mock_web(
        re.escape("https://api.example.com/ok"),
        {"method": "GET", "response": {"status": 200, "headers": {}, "body": b"ok"}},
    )
    vm.mock_web(
        re.escape("https://api.example.com/fail"),
        {"method": "GET", "response": {"status": 503, "headers": {}, "body": b"no"}},
    )
    return now


def assert_error(call, code):
    with pytest.raises(Exception) as exc:
        call()
    assert code in str(exc.value)


def test_partial_payout_preview_and_settlement_are_conservative(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/Presense.py")
    buyer = direct_alice
    seller = direct_bob
    now = submitted_agreement(contract, direct_vm, buyer, seller)

    verdict_id = contract.evaluate("agreement_1")
    verdict = contract.get_verdict("agreement_1")
    expected_seller = (ESCROW * 72) // 100
    expected_buyer = ESCROW - expected_seller

    assert verdict_id == "agreement_1:verdict:1"
    assert verdict["decision"] == "PARTIAL"
    assert verdict["score"] == 72
    assert verdict["payout_seller"] == expected_seller
    assert verdict["payout_buyer"] == expected_buyer
    assert verdict["payout_buyer"] + verdict["payout_seller"] == ESCROW
    assert contract.get_verdict(verdict_id)["id"] == verdict_id
    assert json.loads(contract.get_verdict_json(verdict_id))["id"] == verdict_id
    assert json.loads(contract.get_verdict_json("agreement_1"))["id"] == verdict_id
    assert contract.preview_payout("agreement_1") == {
        "decision": "PARTIAL",
        "score": 72,
        "payout_buyer": expected_buyer,
        "payout_seller": expected_seller,
        "escrow": ESCROW,
    }

    assert_error(lambda: contract.settle("agreement_1"), "E_CHALLENGE_WINDOW_OPEN")
    set_transaction_time(direct_vm, now + CHALLENGE_WINDOW + 1)
    direct_vm.sender = bytes.fromhex("34" * 20)
    contract.settle("agreement_1")

    assert contract.get_status("agreement_1") == "SETTLED"
    assert int(contract.get_claim(buyer)) == expected_buyer
    assert int(contract.get_claim(seller)) == expected_seller
    assert int(contract.get_claim(buyer)) + int(contract.get_claim(seller)) == ESCROW
    assert int(contract.get_totals()["total_locked"]) == ESCROW
    assert_error(lambda: contract.settle("agreement_1"), "E_INVALID_STATE")

    direct_vm.sender = buyer
    contract.withdraw("evm")
    direct_vm.sender = seller
    contract.withdraw("evm")
    assert int(contract.get_claim(buyer)) == 0
    assert int(contract.get_claim(seller)) == 0
    assert int(contract.get_totals()["total_locked"]) == 0


def test_challenge_validates_and_re_evaluates_once(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/Presense.py")
    buyer = direct_alice
    seller = direct_bob
    now = submitted_agreement(contract, direct_vm, buyer, seller)
    contract.evaluate("agreement_1")

    direct_vm.sender = bytes.fromhex("12" * 20)
    assert_error(
        lambda: contract.challenge(
            "agreement_1",
            "Counter evidence",
            ["https://api.example.com/counter"],
            [""],
        ),
        "E_UNAUTHORIZED",
    )

    direct_vm.sender = buyer
    assert_error(
        lambda: contract.challenge("agreement_1", "", ["https://api.example.com/counter"], [""]),
        "E_REASON_INVALID",
    )
    assert_error(
        lambda: contract.challenge("agreement_1", "Counter evidence", [], []),
        "E_ARTIFACT_COUNT",
    )
    assert_error(
        lambda: contract.challenge(
            "agreement_1",
            "Counter evidence",
            ["https://api.example.com/counter"],
            [],
        ),
        "E_ARTIFACT_MISMATCH",
    )
    assert_error(
        lambda: contract.challenge(
            "agreement_1",
            "Counter evidence",
            ["https://api.example.com/counter"],
            ["bad"],
        ),
        "E_BAD_HASH",
    )
    assert_error(
        lambda: contract.challenge(
            "agreement_1",
            "Counter evidence",
            ["https://evil.example/counter"],
            [""],
        ),
        "E_EVIDENCE_DOMAIN",
    )

    challenge_id = contract.challenge(
        "agreement_1",
        "The response changed after the verdict.",
        ["https://api.example.com/counter"],
        [""],
    )
    agreement = contract.get_agreement("agreement_1")
    challenge = contract.get_challenge(challenge_id)
    assert challenge_id == "agreement_1:challenge"
    assert agreement["status"] == "DISPUTED"
    assert agreement["challenge_id"] == challenge_id
    assert agreement["challenge_count"] == 1
    assert challenge["reason"] == "The response changed after the verdict."
    assert challenge["evidence_urls"] == ["https://api.example.com/counter"]

    set_transaction_time(direct_vm, now + CHALLENGE_WINDOW + 1)
    second_verdict_id = contract.evaluate("agreement_1")
    assert second_verdict_id == "agreement_1:verdict:2"
    assert contract.get_status("agreement_1") == "EVALUATED"
    assert_error(
        lambda: contract.challenge(
            "agreement_1",
            "A second challenge.",
            ["https://api.example.com/counter"],
            [""],
        ),
        "E_CHALLENGE_LIMIT",
    )
    assert_error(lambda: contract.settle("agreement_1"), "E_CHALLENGE_WINDOW_OPEN")
    set_transaction_time(direct_vm, now + (2 * CHALLENGE_WINDOW) + 2)
    contract.settle("agreement_1")
    assert contract.get_status("agreement_1") == "SETTLED"
    assert int(contract.get_claim(buyer)) + int(contract.get_claim(seller)) == ESCROW


def test_challenge_window_closes_at_the_documented_boundary(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/Presense.py")
    now = submitted_agreement(contract, direct_vm, direct_alice, direct_bob)
    contract.evaluate("agreement_1")
    set_transaction_time(direct_vm, now + CHALLENGE_WINDOW + 1)
    direct_vm.sender = direct_bob

    assert_error(
        lambda: contract.challenge(
            "agreement_1",
            "Too late.",
            ["https://api.example.com/counter"],
            [""],
        ),
        "E_CHALLENGE_WINDOW_CLOSED",
    )


def test_duplicate_evidence_url_with_conflicting_hash_fails_closed(
    direct_vm, direct_deploy
):
    contract = direct_deploy("contracts/Presense.py")
    counter_url = "https://api.example.com/counter"
    counter_body = b"Counter evidence is content-addressed for this test."
    criterion = {
        "id": "C1",
        "title": "Evidence hash consistency",
        "kind": "subjective",
        "check": "llm_rubric",
        "weight": 100,
        "mandatory": True,
        "params": {
            "evidence_url": "https://api.example.com/base",
            "rubric": "Evidence must be consistent across all submitted references.",
            "threshold": 7,
        },
    }
    evidence_policy = {
        "allowed_domains": ["api.example.com"],
        "max_bytes_per_source": 2_000_000,
        "max_total_bytes": 10_000_000,
        "max_sources_per_criterion": 5,
        "allow_redirects": True,
        "max_redirects": 3,
    }
    direct_vm.mock_web(
        re.escape("https://api.example.com/base"),
        {"method": "GET", "response": {"status": 200, "headers": {}, "body": b"Base evidence."}},
    )
    direct_vm.mock_web(
        re.escape(counter_url),
        {"method": "GET", "response": {"status": 200, "headers": {}, "body": counter_body}},
    )
    actual_hash = hashlib.sha256(counter_body).hexdigest()

    result = contract._run_subjective(
        criterion,
        evidence_policy,
        [
            {"url": counter_url, "sha256": actual_hash},
            {"url": counter_url, "sha256": "0" * 64},
        ],
        {"bytes_used": 0},
    )

    assert result["status"] == "MISSING"
    assert result["reason"] == "Evidence hash did not match the submitted hash"


def test_reevaluation_uses_challenge_counter_evidence(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/Presense.py")
    buyer = direct_alice
    seller = direct_bob
    now = transaction_now(direct_vm)
    manifest = {
        "schema": "presense.manifest.v1",
        "version": 1,
        "title": "Documentation delivery",
        "description": "A subjective criterion for evidence re-evaluation.",
        "criteria": [
            {
                "id": "C1",
                "title": "Documentation includes an example",
                "kind": "subjective",
                "check": "llm_rubric",
                "weight": 100,
                "mandatory": True,
                "params": {
                    "evidence_url": "https://api.example.com/base",
                    "rubric": "Documentation explains authentication and includes an example request.",
                    "threshold": 7,
                },
            }
        ],
        "decision_policy": {
            "accept_threshold": 80,
            "partial_threshold": 50,
            "mandatory_must_pass": True,
            "missing_evidence": "REJECT",
            "partial_payout": "pro_rata",
            "score_rounding": "floor",
        },
        "evidence_policy": {
            "allowed_domains": ["api.example.com"],
            "require_https": True,
            "max_bytes_per_source": 2_000_000,
            "max_total_bytes": 10_000_000,
            "max_sources_per_criterion": 5,
            "allow_redirects": True,
            "max_redirects": 3,
        },
    }
    direct_vm.sender = buyer
    direct_vm.value = ESCROW
    contract.create_agreement(
        agreement_id="agreement_counter",
        seller=seller,
        manifest_json=json.dumps(manifest),
        manifest_url="",
        deadline=now + 86_400,
        challenge_window=CHALLENGE_WINDOW,
        metadata_url="",
    )
    direct_vm.sender = seller
    contract.accept_agreement("agreement_counter")
    contract.submit_delivery(
        "agreement_counter",
        ["https://api.example.com/delivery"],
        [""],
        "Submitted documentation.",
    )
    direct_vm.mock_web(
        re.escape("https://api.example.com/base"),
        {
            "method": "GET",
            "response": {
                "status": 200,
                "headers": {},
                "body": b"Evidence only lacks the required example.",
            },
        },
    )
    direct_vm.mock_web(
        re.escape("https://api.example.com/delivery"),
        {
            "method": "GET",
            "response": {
                "status": 200,
                "headers": {},
                "body": b"Submitted artifact without documentation detail.",
            },
        },
    )
    direct_vm.mock_web(
        re.escape("https://api.example.com/counter"),
        {
            "method": "GET",
            "response": {
                "status": 200,
                "headers": {},
                "body": b"Counter evidence proves authentication uses the X-API-Key header and includes an example request.",
            },
        },
    )
    direct_vm.mock_llm(
        r".*Counter evidence proves authentication.*",
        '{"score":9,"pass":true,"reason":"Counter evidence satisfies the rubric.","evidence_quote":"Counter evidence proves authentication uses the X-API-Key header and includes an example request."}',
    )
    direct_vm.mock_llm(
        r".*Evidence only lacks the required example.*",
        '{"score":2,"pass":false,"reason":"The example is missing.","evidence_quote":""}',
    )

    contract.evaluate("agreement_counter")
    assert contract.get_verdict("agreement_counter")["decision"] == "REJECT"

    direct_vm.sender = buyer
    contract.challenge(
        "agreement_counter",
        "Counter-evidence contains the required example.",
        ["https://api.example.com/counter"],
        [""],
    )
    contract.evaluate("agreement_counter")

    verdict = contract.get_verdict("agreement_counter")
    assert verdict["id"] == "agreement_counter:verdict:2"
    assert verdict["results"][0]["reason"] == "Counter evidence satisfies the rubric.", verdict["results"][0]
    assert verdict["decision"] == "ACCEPT"
    assert "Counter evidence proves authentication" in verdict["results"][0]["evidence_quote"]
    assert verdict["results"][0]["evidence_url"] == "https://api.example.com/counter"