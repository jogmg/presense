"""Phase 3: deterministic objective checks over mocked web responses."""

from datetime import datetime, timezone
import hashlib
import json
import re

import pytest


ESCROW = 1_000


def objective(criterion_id, check, params, weight):
    return {
        "id": criterion_id,
        "title": criterion_id,
        "kind": "objective",
        "check": check,
        "weight": weight,
        "mandatory": True,
        "params": params,
    }


def manifest_json(criteria, **policy_overrides):
    evidence_policy = {
        "allowed_domains": ["api.example.com", "docs.example.com"],
        "require_https": True,
        "max_bytes_per_source": 2_000,
        "max_total_bytes": 10_000,
        "max_sources_per_criterion": 5,
        "allow_redirects": True,
        "max_redirects": 3,
    }
    evidence_policy.update(policy_overrides)
    return json.dumps(
        {
            "schema": "presense.manifest.v1",
            "version": 1,
            "title": "Objective checks",
            "description": "A test manifest for deterministic checks.",
            "criteria": criteria,
            "decision_policy": {
                "accept_threshold": 80,
                "partial_threshold": 50,
                "mandatory_must_pass": True,
                "missing_evidence": "UNDETERMINED",
                "partial_payout": "pro_rata",
                "score_rounding": "floor",
            },
            "evidence_policy": evidence_policy,
        }
    )


def create_submitted_agreement(contract, vm, buyer, seller, raw_manifest):
    now = int(
        datetime.fromisoformat(vm._datetime.replace("Z", "+00:00")).timestamp()
    )
    vm.sender = buyer
    vm.value = ESCROW
    agreement_id = contract.create_agreement(
        agreement_id="objective_test",
        seller=seller,
        manifest_json=raw_manifest,
        manifest_url="",
        deadline=now + 86_400,
        challenge_window=3_600,
        metadata_url="",
    )
    vm.sender = seller
    contract.accept_agreement(agreement_id)
    contract.submit_delivery(
        agreement_id,
        ["https://api.example.com/delivery"],
        [""],
        "Test delivery",
    )
    return agreement_id


def mock_response(vm, url, status=200, body=b"", headers=None, method="GET"):
    vm.mock_web(
        re.escape(url),
        {
            "method": method,
            "response": {
                "status": status,
                "headers": headers or {},
                "body": body,
            }
        },
    )


@pytest.fixture
def setup_contract(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/Presense.py")
    return contract, direct_vm, direct_alice, direct_bob


def test_preview_runs_all_four_objective_checks(setup_contract):
    contract, vm, buyer, seller = setup_contract
    artifact = b"artifact-v1"
    criteria = [
        objective(
            "C1",
            "http_status",
            {
                "url": "https://api.example.com/health",
                "expected_status": [200, 204],
                "method": "HEAD",
            },
            25,
        ),
        objective(
            "C2",
            "json_has_keys",
            {
                "url": "https://api.example.com/openapi.json",
                "required_keys": ["info.title", "servers[0].url", "paths"],
                "types": {"info.title": "string", "servers[0].url": "string", "paths": "object"},
            },
            25,
        ),
        objective(
            "C3",
            "file_hash",
            {
                "url": "https://api.example.com/release.bin",
                "sha256": hashlib.sha256(artifact).hexdigest().upper(),
            },
            25,
        ),
        objective(
            "C4",
            "text_contains",
            {
                "url": "https://docs.example.com/requirements",
                "phrases": ["authentication and rate limit"],
            },
            25,
        ),
    ]
    agreement_id = create_submitted_agreement(
        contract, vm, buyer, seller, manifest_json(criteria)
    )
    mock_response(vm, "https://api.example.com/health", 204, method="HEAD")
    mock_response(
        vm,
        "https://api.example.com/openapi.json",
        body=b'{"info":{"title":"API"},"servers":[{"url":"https://api.example.com"}],"paths":{}}',
    )
    mock_response(vm, "https://api.example.com/release.bin", body=artifact)
    mock_response(
        vm,
        "https://docs.example.com/requirements",
        body=b"Authentication\n\nand   rate limit",
    )

    results = contract.preview_objective_checks(agreement_id)

    assert [result["status"] for result in results] == ["PASS"] * 4
    assert [result["criterion_id"] for result in results] == ["C1", "C2", "C3", "C4"]
    assert all(result["passed"] and result["score"] == 10 for result in results)
    assert all(result["evidence_url"] for result in results)
    assert contract.get_status(agreement_id) == "SUBMITTED"


def test_check_failure_is_distinct_from_missing_evidence(setup_contract):
    contract, vm, buyer, seller = setup_contract
    criteria = [
        objective(
            "C1",
            "http_status",
            {"url": "https://api.example.com/failing", "expected_status": 200},
            50,
        ),
        objective(
            "C2",
            "text_contains",
            {
                "url": "https://docs.example.com/unavailable",
                "phrases": ["available"],
            },
            50,
        ),
    ]
    agreement_id = create_submitted_agreement(
        contract, vm, buyer, seller, manifest_json(criteria)
    )
    mock_response(vm, "https://api.example.com/failing", 503, b"service unavailable")

    results = contract.preview_objective_checks(agreement_id)

    assert results[0]["status"] == "FAIL"
    assert results[0]["passed"] is False
    assert results[1]["status"] == "MISSING"
    assert results[1]["passed"] is False


def test_evaluate_fails_closed_when_evidence_is_missing(setup_contract):
    contract, vm, buyer, seller = setup_contract
    criteria = [
        objective(
            "C1",
            "http_status",
            {"url": "https://api.example.com/unavailable", "expected_status": 200},
            100,
        )
    ]
    agreement_id = create_submitted_agreement(
        contract, vm, buyer, seller, manifest_json(criteria)
    )

    with pytest.raises(Exception) as exc:
        contract.evaluate(agreement_id)

    assert "E_UNDETERMINED" in str(exc.value)
    assert contract.get_status(agreement_id) == "SUBMITTED"
    with pytest.raises(Exception) as no_verdict:
        contract.get_verdict(agreement_id)
    assert "E_NO_VERDICT" in str(no_verdict.value)


def test_content_length_cap_is_checked_before_parsing(setup_contract):
    contract, vm, buyer, seller = setup_contract
    criteria = [
        objective(
            "C1",
            "json_has_keys",
            {
                "url": "https://api.example.com/large.json",
                "required_keys": ["ok"],
            },
            100,
        )
    ]
    raw_manifest = manifest_json(criteria, max_bytes_per_source=1_000)
    agreement_id = create_submitted_agreement(
        contract, vm, buyer, seller, raw_manifest
    )
    mock_response(
        vm,
        "https://api.example.com/large.json",
        body=b"{}",
        headers={"Content-Length": b"1001"},
    )

    result = contract.preview_objective_checks(agreement_id)[0]

    assert result["status"] == "MISSING"
    assert "byte limit" in result["reason"]


def test_total_byte_budget_is_shared_across_criteria(setup_contract):
    contract, vm, buyer, seller = setup_contract
    body = b"x" * 600
    criteria = [
        objective(
            "C1",
            "http_status",
            {"url": "https://api.example.com/first", "expected_status": 200},
            50,
        ),
        objective(
            "C2",
            "http_status",
            {"url": "https://api.example.com/second", "expected_status": 200},
            50,
        ),
    ]
    agreement_id = create_submitted_agreement(
        contract,
        vm,
        buyer,
        seller,
        manifest_json(
            criteria,
            max_bytes_per_source=1_000,
            max_total_bytes=1_000,
        ),
    )
    mock_response(vm, "https://api.example.com/first", body=body)
    mock_response(
        vm,
        "https://api.example.com/second",
        body=body,
        headers={"Content-Length": b"600"},
    )

    results = contract.preview_objective_checks(agreement_id)

    assert results[0]["status"] == "PASS"
    assert results[1]["status"] == "MISSING"
    assert "total evidence" in results[1]["reason"]


def test_visible_redirect_is_followed_only_within_allowed_domain(setup_contract):
    contract, vm, buyer, seller = setup_contract
    start_url = "https://api.example.com/start/path"
    final_url = "https://docs.example.com/final"
    criteria = [
        objective(
            "C1",
            "http_status",
            {"url": start_url, "expected_status": 200},
            100,
        )
    ]
    agreement_id = create_submitted_agreement(
        contract, vm, buyer, seller, manifest_json(criteria)
    )
    mock_response(vm, start_url, 302, headers={"Location": b"https://docs.example.com/final"})
    mock_response(vm, final_url, 200, b"ok")

    result = contract.preview_objective_checks(agreement_id)[0]

    assert result["status"] == "PASS"
    assert result["evidence_url"] == start_url


def test_redirect_outside_allowlist_is_missing(setup_contract):
    contract, vm, buyer, seller = setup_contract
    start_url = "https://api.example.com/redirect"
    criteria = [
        objective(
            "C1",
            "http_status",
            {"url": start_url, "expected_status": 200},
            100,
        )
    ]
    agreement_id = create_submitted_agreement(
        contract, vm, buyer, seller, manifest_json(criteria)
    )
    mock_response(vm, start_url, 302, headers={"Location": b"https://evil.example/"})

    result = contract.preview_objective_checks(agreement_id)[0]

    assert result["status"] == "MISSING"
    assert result["passed"] is False


@pytest.mark.parametrize(
    ("body", "required_keys", "types"),
    [
        (b"not json", ["ok"], {}),
        (b'{"ok":[]}', ["missing"], {}),
        (b'{"ok":[]}', ["ok"], {"ok": "object"}),
    ],
)
def test_invalid_json_missing_path_and_type_mismatch_fail(
    setup_contract, body, required_keys, types
):
    contract, vm, buyer, seller = setup_contract
    url = "https://api.example.com/data.json"
    criteria = [
        objective(
            "C1",
            "json_has_keys",
            {"url": url, "required_keys": required_keys, "types": types},
            100,
        )
    ]
    agreement_id = create_submitted_agreement(
        contract, vm, buyer, seller, manifest_json(criteria)
    )
    mock_response(vm, url, body=body)

    result = contract.preview_objective_checks(agreement_id)[0]

    assert result["status"] == "FAIL"
    assert result["passed"] is False


def test_redirect_limit_is_enforced(setup_contract):
    contract, vm, buyer, seller = setup_contract
    url = "https://api.example.com/redirect"
    criteria = [
        objective(
            "C1",
            "http_status",
            {"url": url, "expected_status": 200},
            100,
        )
    ]
    agreement_id = create_submitted_agreement(
        contract,
        vm,
        buyer,
        seller,
        manifest_json(criteria, max_redirects=0),
    )
    mock_response(vm, url, 302, headers={"Location": b"/next"})

    result = contract.preview_objective_checks(agreement_id)[0]

    assert result["status"] == "MISSING"
    assert "redirect limit" in result["reason"]