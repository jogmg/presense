"""Phase 2: agreement lifecycle, escrow claims, and accounting invariants."""

from datetime import datetime, timezone
import json
import re

import pytest


ESCROW = 1_000
CHALLENGE_WINDOW = 3_600


def make_manifest() -> str:
    return json.dumps(
        {
            "schema": "presense.manifest.v1",
            "version": 1,
            "title": "Test delivery",
            "description": "A test acceptance manifest.",
            "criteria": [
                {
                    "id": "C1",
                    "title": "Health endpoint",
                    "kind": "objective",
                    "check": "http_status",
                    "weight": 100,
                    "mandatory": True,
                    "params": {
                        "url": "https://api.example.com/health",
                        "expected_status": 200,
                    },
                }
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


def transaction_now(vm) -> int:
    return int(datetime.fromisoformat(vm._datetime.replace("Z", "+00:00")).timestamp())


def set_transaction_time(vm, timestamp: int) -> None:
    vm._datetime = datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def create_agreement(contract, vm, buyer, seller, agreement_id="agreement_1", **overrides):
    now = transaction_now(vm)
    value = overrides.pop("value", ESCROW)
    params = {
        "agreement_id": agreement_id,
        "seller": seller,
        "manifest_json": make_manifest(),
        "manifest_url": "",
        "deadline": now + 86_400,
        "challenge_window": CHALLENGE_WINDOW,
        "metadata_url": "",
    }
    params.update(overrides)
    vm.sender = buyer
    vm.value = value
    return contract.create_agreement(**params)


@pytest.fixture
def setup_contract(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/Presense.py")
    return contract, direct_vm, direct_alice, direct_bob


def assert_error(call, code):
    with pytest.raises(Exception) as exc:
        call()
    assert code in str(exc.value)


def test_create_stores_canonical_agreement_and_escrow(setup_contract):
    contract, vm, buyer, seller = setup_contract
    raw_manifest = make_manifest()

    result = create_agreement(
        contract,
        vm,
        buyer,
        seller,
        manifest_json=raw_manifest,
        manifest_url="https://files.example.org/manifest.json",
        metadata_url="https://files.example.org/task/1",
    )

    agreement = contract.get_agreement(result)
    assert result == "agreement_1"
    assert re.fullmatch(r"0x[0-9a-fA-F]{40}", agreement["buyer"])
    assert re.fullmatch(r"0x[0-9a-fA-F]{40}", agreement["seller"])
    assert agreement["status"] == "CREATED"
    assert agreement["manifest_json"] == contract.check_manifest(raw_manifest)["canonical"]
    assert agreement["manifest_hash"] == contract.check_manifest(raw_manifest)["hash"]
    assert contract.get_status(result) == "CREATED"
    assert json.loads(contract.get_agreement_json(result))["escrow"] == ESCROW
    assert int(contract.get_totals()["total_locked"]) == ESCROW


def test_create_rejects_bad_id_zero_escrow_self_and_duplicate(setup_contract):
    contract, vm, buyer, seller = setup_contract
    now = transaction_now(vm)

    assert_error(
        lambda: create_agreement(contract, vm, buyer, seller, agreement_id="bad id"),
        "E_BAD_ID",
    )
    assert_error(
        lambda: create_agreement(
            contract,
            vm,
            buyer,
            seller,
            agreement_id="zero",
            deadline=now + 7200,
            value=0,
        ),
        "E_ESCROW_ZERO",
    )

    vm.value = ESCROW
    assert_error(
        lambda: create_agreement(contract, vm, buyer, buyer, agreement_id="self"),
        "E_SELF_AGREEMENT",
    )
    assert_error(
        lambda: create_agreement(
            contract,
            vm,
            buyer,
            bytes(20),
            agreement_id="zero_seller",
        ),
        "E_ZERO_ADDRESS",
    )
    create_agreement(contract, vm, buyer, seller)
    assert_error(lambda: create_agreement(contract, vm, buyer, seller), "E_AGREEMENT_EXISTS")


def test_create_rejects_invalid_deadline_window_manifest_and_info_url(setup_contract):
    contract, vm, buyer, seller = setup_contract
    now = transaction_now(vm)

    assert_error(
        lambda: create_agreement(
            contract, vm, buyer, seller, agreement_id="short", deadline=now + 3599
        ),
        "E_DEADLINE_INVALID",
    )
    assert_error(
        lambda: create_agreement(
            contract,
            vm,
            buyer,
            seller,
            agreement_id="window",
            challenge_window=3599,
        ),
        "E_WINDOW_INVALID",
    )
    assert_error(
        lambda: create_agreement(
            contract,
            vm,
            buyer,
            seller,
            agreement_id="manifest",
            manifest_json="{}",
        ),
        "E_MANIFEST_INVALID",
    )
    assert_error(
        lambda: create_agreement(
            contract,
            vm,
            buyer,
            seller,
            agreement_id="url",
            manifest_url="http://files.example.org/manifest.json",
        ),
        "E_URL_INVALID",
    )


def test_seller_acceptance_and_role_and_state_guards(setup_contract):
    contract, vm, buyer, seller = setup_contract
    create_agreement(contract, vm, buyer, seller)

    vm.sender = buyer
    assert_error(lambda: contract.accept_agreement("agreement_1"), "E_UNAUTHORIZED")
    vm.sender = seller
    contract.accept_agreement("agreement_1")
    assert contract.get_status("agreement_1") == "ACTIVE"
    assert_error(lambda: contract.accept_agreement("agreement_1"), "E_INVALID_STATE")


def test_buyer_cancels_and_gets_refund_without_changing_locked_total(setup_contract):
    contract, vm, buyer, seller = setup_contract
    create_agreement(contract, vm, buyer, seller)

    vm.sender = seller
    assert_error(lambda: contract.cancel_agreement("agreement_1"), "E_UNAUTHORIZED")
    vm.sender = buyer
    contract.cancel_agreement("agreement_1")

    assert contract.get_status("agreement_1") == "CANCELLED"
    assert int(contract.get_claim(buyer)) == ESCROW
    assert int(contract.get_totals()["total_locked"]) == ESCROW
    assert_error(lambda: contract.cancel_agreement("agreement_1"), "E_INVALID_STATE")


def test_seller_submits_artifacts_and_moves_to_submitted(setup_contract):
    contract, vm, buyer, seller = setup_contract
    create_agreement(contract, vm, buyer, seller)
    vm.sender = seller
    contract.accept_agreement("agreement_1")

    submission_id = contract.submit_delivery(
        "agreement_1",
        ["https://api.example.com/release.zip"],
        ["a" * 64],
        "Release artifact.",
    )

    submission = contract.submissions[submission_id]
    agreement = contract.get_agreement("agreement_1")
    assert submission_id == "agreement_1:submission"
    assert list(submission.artifact_urls) == ["https://api.example.com/release.zip"]
    assert list(submission.artifact_hashes) == ["a" * 64]
    assert str(submission.submitter) == str(contract.get_agreement("agreement_1")["seller"])
    assert agreement["submission_id"] == submission_id
    assert agreement["status"] == "SUBMITTED"


def test_submit_rejects_wrong_role_state_artifacts_hash_and_domain(setup_contract):
    contract, vm, buyer, seller = setup_contract
    create_agreement(contract, vm, buyer, seller)
    vm.sender = buyer
    assert_error(
        lambda: contract.submit_delivery("agreement_1", ["https://api.example.com/a"], [""], ""),
        "E_UNAUTHORIZED",
    )
    vm.sender = seller
    assert_error(
        lambda: contract.submit_delivery("agreement_1", ["https://api.example.com/a"], [""], ""),
        "E_INVALID_STATE",
    )
    contract.accept_agreement("agreement_1")
    assert_error(
        lambda: contract.submit_delivery("agreement_1", [], [], ""),
        "E_ARTIFACT_COUNT",
    )
    assert_error(
        lambda: contract.submit_delivery(
            "agreement_1", ["https://api.example.com/a"], [], ""
        ),
        "E_ARTIFACT_MISMATCH",
    )
    assert_error(
        lambda: contract.submit_delivery(
            "agreement_1", ["https://api.example.com/a"], ["bad"], ""
        ),
        "E_BAD_HASH",
    )
    assert_error(
        lambda: contract.submit_delivery(
            "agreement_1", ["https://evil.example/a"], [""], ""
        ),
        "E_EVIDENCE_DOMAIN",
    )
    assert_error(
        lambda: contract.submit_delivery(
            "agreement_1", ["https://api.example.com/a"], [""], "n" * 2_001
        ),
        "E_MANIFEST_INVALID",
    )


def test_expire_refunds_buyer_after_deadline(setup_contract):
    contract, vm, buyer, seller = setup_contract
    now = transaction_now(vm)
    create_agreement(
        contract,
        vm,
        buyer,
        seller,
        deadline=now + 7_200,
    )
    vm.sender = seller
    contract.accept_agreement("agreement_1")

    set_transaction_time(vm, now + 7_201)
    contract.claim_expired("agreement_1")

    assert contract.get_status("agreement_1") == "EXPIRED"
    assert int(contract.get_claim(buyer)) == ESCROW
    assert int(contract.get_totals()["total_locked"]) == ESCROW
    assert_error(lambda: contract.claim_expired("agreement_1"), "E_INVALID_STATE")


def test_expiry_requires_active_agreement_and_elapsed_deadline(setup_contract):
    contract, vm, buyer, seller = setup_contract
    now = transaction_now(vm)
    create_agreement(contract, vm, buyer, seller, deadline=now + 7_200)
    assert_error(lambda: contract.claim_expired("agreement_1"), "E_INVALID_STATE")

    vm.sender = seller
    contract.accept_agreement("agreement_1")
    assert_error(lambda: contract.claim_expired("agreement_1"), "E_DEADLINE_NOT_PASSED")


def test_seller_cannot_accept_after_deadline(setup_contract):
    contract, vm, buyer, seller = setup_contract
    now = transaction_now(vm)
    create_agreement(contract, vm, buyer, seller, deadline=now + 7_200)

    set_transaction_time(vm, now + 7_201)
    vm.sender = seller
    assert_error(lambda: contract.accept_agreement("agreement_1"), "E_DEADLINE_PASSED")
    assert contract.get_status("agreement_1") == "CREATED"


def test_seller_cannot_submit_after_deadline(setup_contract):
    contract, vm, buyer, seller = setup_contract
    now = transaction_now(vm)
    create_agreement(contract, vm, buyer, seller, deadline=now + 7_200)
    vm.sender = seller
    contract.accept_agreement("agreement_1")

    set_transaction_time(vm, now + 7_201)
    assert_error(
        lambda: contract.submit_delivery(
            "agreement_1", ["https://api.example.com/a"], [""], ""
        ),
        "E_DEADLINE_PASSED",
    )
    assert contract.get_status("agreement_1") == "ACTIVE"


def test_withdraw_validates_kind_and_zero_claim(setup_contract):
    contract, vm, buyer, seller = setup_contract
    vm.sender = buyer
    assert_error(lambda: contract.withdraw("evm"), "E_CLAIM_ZERO")
    assert_error(lambda: contract.withdraw("bank"), "E_BAD_RECIPIENT_KIND")


@pytest.mark.parametrize("kind", ["evm", "ic"])
def test_withdraw_clears_claim_and_reduces_locked_total(setup_contract, kind):
    contract, vm, buyer, seller = setup_contract
    create_agreement(contract, vm, buyer, seller)
    vm.sender = buyer
    contract.cancel_agreement("agreement_1")

    contract.withdraw(kind)

    assert int(contract.get_claim(buyer)) == 0
    assert int(contract.get_totals()["total_locked"]) == 0
    assert_error(lambda: contract.withdraw(kind), "E_CLAIM_ZERO")


def test_unknown_agreement_views_return_not_found(setup_contract):
    contract, _vm, _buyer, _seller = setup_contract
    assert_error(lambda: contract.get_agreement("missing"), "E_NOT_FOUND")
    assert_error(lambda: contract.get_agreement_json("missing"), "E_NOT_FOUND")
    assert_error(lambda: contract.get_status("missing"), "E_NOT_FOUND")
