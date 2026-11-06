"""Localnet smoke test for the complete Presense lifecycle.

Run against glsim (fast, Python runner):

    glsim --no-browser

or against a full GenVM localnet (`genlayer up`). Then:

    gltest tests/integration -v -s --network localnet

The manifest is objective-only so the test does not need an LLM provider.
It does make a real HTTPS request to example.com.
"""

from datetime import datetime, timezone
import json
import time
import urllib.request

import pytest
from gltest import get_contract_factory
from gltest_cli.config.general import get_general_config

from genlayer_py.types import TransactionStatus


pytestmark = pytest.mark.integration

ESCROW = 10**15  # 0.001 GEN
CHALLENGE_WINDOW = 3_600
FUNDING = 10 * 10**18  # 10 GEN


def rpc(method: str, params=None):
    """Call a simulator RPC directly (funding, time travel)."""
    url = get_general_config().get_rpc_url()
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
    ).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if "error" in payload:
        raise RuntimeError(f"{method} failed: {payload['error']}")
    return payload.get("result")


def effective_now() -> int:
    result = rpc("sim_getTime")
    return int(datetime.fromisoformat(result["effective_datetime"]).timestamp())


def increase_time(seconds: int) -> None:
    rpc("sim_increaseTime", [seconds])


def fund(address: str) -> None:
    rpc("sim_fundAccount", [address, FUNDING])


def make_manifest() -> str:
    return json.dumps(
        {
            "schema": "presense.manifest.v1",
            "version": 1,
            "title": "Localnet objective smoke test",
            "description": "Objective-only manifest for the localnet lifecycle flow.",
            "criteria": [
                {
                    "id": "C1",
                    "title": "Example Domain is reachable",
                    "kind": "objective",
                    "check": "http_status",
                    "weight": 100,
                    "mandatory": True,
                    "params": {
                        "url": "https://example.com/",
                        "expected_status": 200,
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
                "allowed_domains": ["example.com"],
                "require_https": True,
                "max_bytes_per_source": 1_000_000,
                "max_total_bytes": 5_000_000,
                "max_sources_per_criterion": 3,
                "allow_redirects": True,
                "max_redirects": 3,
            },
        }
    )


@pytest.fixture(scope="module")
def parties(accounts):
    if len(accounts) < 2:
        pytest.skip("integration tests need at least two configured accounts")
    buyer, seller = accounts[0], accounts[1]
    fund(buyer.address)
    fund(seller.address)
    return buyer, seller


@pytest.fixture(scope="module")
def presense(parties):
    buyer, _seller = parties
    factory = get_contract_factory(contract_name="Presense")
    contract = factory.deploy(
        account=buyer,
        wait_transaction_status=TransactionStatus.ACCEPTED,
        wait_retries=200,
    )
    return contract


def transact(call, **kwargs):
    """Execute a write and fail if the leader execution reverted.

    glsim marks a reverted deterministic execution as a FINALIZED transaction
    with ``execution_result: ERROR``, so the receipt status alone is not
    enough to prove the call succeeded.
    """
    receipt = call.transact(**kwargs)
    leader = receipt["consensus_data"]["leader_receipt"][0]
    assert leader["execution_result"] == "SUCCESS", leader.get("genvm_result")
    return receipt


def create(contract, buyer, seller, agreement_id: str, deadline: int):
    return transact(
        contract.connect(buyer).create_agreement(
            args=[
                agreement_id,
                seller.address,
                make_manifest(),
                "",
                deadline,
                CHALLENGE_WINDOW,
                "",
            ]
        ),
        value=ESCROW,
        wait_retries=200,
    )


def test_accept_submit_evaluate_settle_withdraw(presense, parties):
    buyer, seller = parties
    agreement_id = f"localnet-{int(time.time())}-happy"
    now = effective_now()
    create(presense, buyer, seller, agreement_id, now + 86_400)

    seller_contract = presense.connect(seller)
    transact(seller_contract.accept_agreement(args=[agreement_id]), wait_retries=200)
    assert presense.get_status(args=[agreement_id]).call() == "ACTIVE"

    transact(
        seller_contract.submit_delivery(
            args=[
                agreement_id,
                ["https://example.com/"],
                [""],
                "Localnet smoke delivery.",
            ]
        ),
        wait_retries=200,
    )
    assert presense.get_status(args=[agreement_id]).call() == "SUBMITTED"

    transact(presense.evaluate(args=[agreement_id]), wait_retries=400)

    verdict = presense.get_verdict(args=[agreement_id]).call()
    assert verdict["decision"] == "ACCEPT"
    assert verdict["score"] == 100
    assert verdict["payout_seller"] == ESCROW
    assert verdict["payout_buyer"] == 0
    assert presense.get_status(args=[agreement_id]).call() == "EVALUATED"

    increase_time(CHALLENGE_WINDOW + 1)
    transact(presense.settle(args=[agreement_id]), wait_retries=200)
    assert presense.get_status(args=[agreement_id]).call() == "SETTLED"
    assert presense.get_claim(args=[seller.address]).call() == ESCROW

    transact(seller_contract.withdraw(args=["evm"]), wait_retries=200)
    assert presense.get_claim(args=[seller.address]).call() == 0


def test_expiry_refunds_buyer(presense, parties):
    buyer, seller = parties
    agreement_id = f"localnet-{int(time.time())}-expire"
    now = effective_now()
    create(presense, buyer, seller, agreement_id, now + 3_601)

    seller_contract = presense.connect(seller)
    transact(seller_contract.accept_agreement(args=[agreement_id]), wait_retries=200)

    increase_time(3_700)
    transact(presense.claim_expired(args=[agreement_id]), wait_retries=200)

    assert presense.get_status(args=[agreement_id]).call() == "EXPIRED"
    assert presense.get_claim(args=[buyer.address]).call() == ESCROW

    transact(presense.connect(buyer).withdraw(args=["evm"]), wait_retries=200)
    assert presense.get_claim(args=[buyer.address]).call() == 0
