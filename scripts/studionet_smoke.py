"""Run the Presense lifecycle smoke test against a live GenLayer network.

The script uses objective-only acceptance manifests, so it needs no LLM
provider. It drives six scenarios: accept, partial, reject, challenge, expiry,
and cancellation. Studionet enforces a minimum one-hour challenge window and a
minimum one-hour deadline, so the run is split into two phases:

    python scripts/studionet_smoke.py --phase init
    python scripts/studionet_smoke.py --phase finalize

`init` creates and evaluates the agreements. `finalize` waits for the challenge
windows and the expiry deadline, then settles, claims, and withdraws. The state
file makes the phases resumable and keeps every transaction hash.

Credentials are read from a JSON file outside version control:

    {
      "buyer":  {"name": "my-buyer",  "password": "..."},
      "seller": {"name": "my-seller", "password": "..."}
    }

Each entry may use `"private_key": "0x..."` instead of a keystore name and
password. Keystores are read from `~/.genlayer/keystores` by default.

Example:

    python scripts/studionet_smoke.py \
      --contract 0x1905d0Af801cc32D817Eed228b81902Dd1eB7DA9 \
      --credentials .presense-smoke/credentials.json \
      --state .presense-smoke/state.json \
      --phase init
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from eth_account import Account
from genlayer_py import create_client
from genlayer_py.chains import studionet
from genlayer_py.contracts.actions import read_contract, write_contract
from genlayer_py.transactions.actions import wait_for_transaction_receipt
from genlayer_py.types import CalldataAddress, TransactionStatus

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = ROOT / ".presense-smoke" / "state.json"
DEFAULT_CREDENTIALS = ROOT / ".presense-smoke" / "credentials.json"
DEFAULT_KEYSTORE_DIR = Path.home() / ".genlayer" / "keystores"
DEFAULT_EXPLORER = "https://explorer-studio.genlayer.com"
DEFAULT_CONTRACT = "0x1905d0Af801cc32D817Eed228b81902Dd1eB7DA9"

CHALLENGE_WINDOW = 3_600
DAY = 86_400
EXPIRY_MARGIN = 4_200
SETTLE_MARGIN = 90
FINALITY_RETRIES = 500
FINALITY_INTERVAL = 3_000
STATUS = TransactionStatus

SCENARIOS = ("accept", "partial", "reject", "challenge", "expiry", "cancel")


def utc_now() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Runner:
    def __init__(
        self,
        contract: str,
        explorer: str,
        state_path: Path,
        credentials_path: Path,
        keystore_dir: Path,
        escrow: int,
        log_path: Path,
    ) -> None:
        self.contract = contract
        self.explorer = explorer.rstrip("/")
        self.state_path = state_path
        self.credentials_path = credentials_path
        self.keystore_dir = keystore_dir
        self.escrow = escrow
        self.log_path = log_path
        self.state = self._load_state()
        self.buyer, self.seller = self._load_accounts()
        self.client = create_client(chain=studionet, account=self.buyer)

    # -- persistence -----------------------------------------------------

    def _load_state(self) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {"contract": self.contract, "scenarios": {}}

    def save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(self.state, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )

    def log(self, event: str, **fields) -> None:
        record = {"at": iso_now(), "event": event, **fields}
        print(json.dumps(record, sort_keys=True, default=str), flush=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")

    # -- accounts --------------------------------------------------------

    def _load_accounts(self):
        credentials = json.loads(
            self.credentials_path.read_text(encoding="utf-8-sig")
        )
        accounts = {}
        for role in ("buyer", "seller"):
            info = credentials[role]
            if "private_key" in info:
                accounts[role] = Account.from_key(info["private_key"])
                continue
            password = info.get("password") or os.environ.get(
                f"PRESENSE_SMOKE_{role.upper()}_PASSWORD"
            )
            if not password:
                raise SystemExit(
                    f"credentials for {role} need a password or private_key"
                )
            keystore_path = self.keystore_dir / f"{info['name']}.json"
            keystore = json.loads(keystore_path.read_text(encoding="utf-8-sig"))
            accounts[role] = Account.from_key(Account.decrypt(keystore, password))
        return accounts["buyer"], accounts["seller"]

    # -- contract helpers ------------------------------------------------

    def read(self, function: str, args=None):
        last_error = None
        for attempt in range(6):
            try:
                return read_contract(
                    self.client, self.contract, function, args=args or []
                )
            except Exception as error:  # transient network/indexing failures
                last_error = error
                time.sleep(2 + attempt * 2)
        raise last_error

    def send(self, account, function: str, args=None, value: int = 0) -> dict:
        last_error = None
        tx_hash = None
        for attempt in range(5):
            try:
                tx_hash = write_contract(
                    self.client,
                    self.contract,
                    function,
                    account=account,
                    value=value,
                    args=args or [],
                )
                break
            except Exception as error:
                last_error = error
                self.log("send_retry", function=function, error=str(error))
                time.sleep(5 + attempt * 5)
        if tx_hash is None:
            raise last_error

        receipt = None
        for _ in range(4):
            try:
                receipt = wait_for_transaction_receipt(
                    self.client,
                    tx_hash,
                    status=STATUS.FINALIZED,
                    retries=FINALITY_RETRIES,
                    interval=FINALITY_INTERVAL,
                    full_transaction=True,
                )
                break
            except Exception as error:  # the transaction may not be indexed yet
                last_error = error
                self.log("wait_retry", function=function, tx=tx_hash, error=str(error)[:500])
                time.sleep(10)
        if receipt is None:
            raise last_error

        leader = (receipt.get("consensus_data") or {}).get("leader_receipt") or []
        if isinstance(leader, list):
            leader = leader[0] if leader else {}
        execution = leader.get("execution_result")
        if execution != "SUCCESS":
            raise RuntimeError(
                f"{function} did not succeed: execution_result={execution!r} "
                f"genvm_result={json.dumps(leader.get('genvm_result'), default=str)[:2000]}"
            )
        record = {
            "function": function,
            "tx": tx_hash,
            "status": receipt.get("status_name") or str(receipt.get("status")),
            "execution_result": execution,
            "explorer": f"{self.explorer}/tx/{tx_hash}",
        }
        self.log("tx", **record)
        return record

    # -- manifests -------------------------------------------------------

    @staticmethod
    def status_criterion(expected: int, weight: int = 100, mandatory: bool = True) -> dict:
        return {
            "id": f"C{expected}",
            "title": f"example.com responds with {expected}",
            "kind": "objective",
            "check": "http_status",
            "weight": weight,
            "mandatory": mandatory,
            "params": {"url": "https://example.com/", "expected_status": expected},
        }

    def manifest(self, title: str, criteria: list[dict]) -> str:
        return json.dumps(
            {
                "schema": "presense.manifest.v1",
                "version": 1,
                "title": title,
                "description": f"Studionet smoke manifest: {title}.",
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

    def manifest_for(self, name: str) -> str:
        if name == "partial":
            return self.manifest(
                "Studionet partial path",
                [
                    self.status_criterion(200, 50, False),
                    self.status_criterion(404, 50, False),
                ],
            )
        if name == "reject":
            return self.manifest(
                "Studionet reject path", [self.status_criterion(404, 100, True)]
            )
        return self.manifest(
            f"Studionet {name} path", [self.status_criterion(200, 100, True)]
        )

    # -- scenario helpers ------------------------------------------------

    def entry(self, name: str) -> dict:
        return self.state["scenarios"][name]

    def create(self, name: str, deadline: int) -> str:
        agreement_id = f"smoke-{name}-{utc_now()}"
        record = self.send(
            self.buyer,
            "create_agreement",
            [
                agreement_id,
                CalldataAddress(self.seller.address),
                self.manifest_for(name),
                "",
                deadline,
                CHALLENGE_WINDOW,
                "",
            ],
            value=self.escrow,
        )
        self.state["scenarios"][name] = {
            "agreement_id": agreement_id,
            "escrow": self.escrow,
            "deadline": deadline,
            "challenge_window": CHALLENGE_WINDOW,
            "buyer": self.buyer.address,
            "seller": self.seller.address,
            "created_at": utc_now(),
            "transactions": {"create": record},
            "verdicts": [],
            "errors": [],
        }
        self.save()
        self.log("created", scenario=name, agreement_id=agreement_id, deadline=deadline)
        return agreement_id

    def snapshot(self, name: str) -> dict:
        agreement_id = self.entry(name)["agreement_id"]
        agreement = json.loads(self.read("get_agreement_json", [agreement_id]))
        payload = {
            "status": self.read("get_status", [agreement_id]),
            "agreement": agreement,
        }
        if agreement.get("verdict_id"):
            payload["verdict"] = json.loads(
                self.read("get_verdict_json", [agreement["verdict_id"]])
            )
        return payload

    def record_error(self, name: str, error: Exception) -> None:
        entry = self.state["scenarios"].setdefault(
            name,
            {
                "agreement_id": f"smoke-{name}-{utc_now()}",
                "created_at": utc_now(),
                "transactions": {},
                "verdicts": [],
                "errors": [],
            },
        )
        entry.setdefault("errors", []).append(str(error))
        self.save()
        self.log(
            "scenario_failed",
            scenario=name,
            error=str(error),
            trace=traceback.format_exc(),
        )

    def init(self) -> None:
        started = utc_now()
        plan = (
            ("accept", started + DAY),
            ("partial", started + DAY),
            ("reject", started + DAY),
            ("expiry", None),
            ("cancel", started + DAY),
        )
        for name, deadline in plan:
            entry = self.state["scenarios"].get(name)
            if entry and not entry.get("errors"):
                self.log("skip_existing", scenario=name, agreement_id=entry["agreement_id"])
                continue
            try:
                if deadline is None:
                    deadline = utc_now() + EXPIRY_MARGIN
                agreement_id = self.create(name, deadline)
                if name == "cancel":
                    self.state["scenarios"][name]["status_after_create"] = self.read(
                        "get_status", [agreement_id]
                    )
                    continue
                self.entry(name)["transactions"]["accept"] = self.send(
                    self.seller, "accept_agreement", [agreement_id]
                )
                self.save()
                self.entry(name)["status_after_accept"] = self.read(
                    "get_status", [agreement_id]
                )
                if name != "expiry":
                    self.entry(name)["transactions"]["submit"] = self.send(
                        self.seller,
                        "submit_delivery",
                        [
                            agreement_id,
                            ["https://example.com/"],
                            [""],
                            f"Studionet {name} delivery.",
                        ],
                    )
                    self.entry(name)["status_after_submit"] = self.read(
                        "get_status", [agreement_id]
                    )
                    self.entry(name)["transactions"]["evaluate"] = self.send(
                        self.buyer, "evaluate", [agreement_id]
                    )
                    self.entry(name)["status_after_evaluate"] = self.read(
                        "get_status", [agreement_id]
                    )
                    self.entry(name)["verdicts"].append(self.snapshot(name))
                    self.save()
            except Exception as error:
                self.record_error(name, error)

        if "cancel" in self.state["scenarios"]:
            entry = self.state["scenarios"]["cancel"]
            try:
                if not entry.get("cancelled"):
                    agreement_id = entry["agreement_id"]
                    entry["transactions"]["cancel"] = self.send(
                        self.buyer, "cancel_agreement", [agreement_id]
                    )
                    entry["status_after_cancel"] = self.read(
                        "get_status", [agreement_id]
                    )
                    entry["cancelled"] = True
                    self.save()
            except Exception as error:
                self.record_error("cancel", error)

        if (
            "challenge" not in self.state["scenarios"]
            or self.state["scenarios"]["challenge"].get("errors")
        ):
            try:
                agreement_id = self.create("challenge", started + DAY)
                entry = self.entry("challenge")
                entry["transactions"]["accept"] = self.send(
                    self.seller, "accept_agreement", [agreement_id]
                )
                entry["transactions"]["submit"] = self.send(
                    self.seller,
                    "submit_delivery",
                    [
                        agreement_id,
                        ["https://example.com/"],
                        [""],
                        "Studionet challenge delivery.",
                    ],
                )
                entry["transactions"]["evaluate"] = self.send(
                    self.buyer, "evaluate", [agreement_id]
                )
                entry["verdicts"].append(self.snapshot("challenge"))
                entry["transactions"]["challenge"] = self.send(
                    self.buyer,
                    "challenge",
                    [
                        agreement_id,
                        "Counter-evidence submitted for the smoke test.",
                        ["https://example.com/"],
                        [""],
                    ],
                )
                entry["status_after_challenge"] = self.read(
                    "get_status", [agreement_id]
                )
                entry["transactions"]["evaluate_after_challenge"] = self.send(
                    self.buyer, "evaluate", [agreement_id]
                )
                entry["status_after_reevaluate"] = self.read(
                    "get_status", [agreement_id]
                )
                entry["verdicts"].append(self.snapshot("challenge"))
                self.save()
            except Exception as error:
                self.record_error("challenge", error)

        self.state["init_finished_at"] = utc_now()
        self.save()

    def ready_at(self) -> int:
        candidates = []
        for name, entry in self.state["scenarios"].items():
            if name in ("accept", "partial", "reject", "challenge"):
                verdicts = entry.get("verdicts") or []
                evaluated = (
                    verdicts[-1]["agreement"].get("evaluated_at")
                    if verdicts
                    else entry.get("created_at", 0)
                )
                candidates.append(
                    int(evaluated) + CHALLENGE_WINDOW + SETTLE_MARGIN
                )
            elif name == "expiry":
                candidates.append(
                    int(entry.get("deadline", entry.get("created_at", 0)))
                    + SETTLE_MARGIN
                )
        return max(candidates) if candidates else utc_now()

    def finalize(self) -> None:
        target = self.ready_at()
        while utc_now() < target:
            remaining = target - utc_now()
            self.log("waiting", remaining_seconds=remaining, ready_at=target)
            time.sleep(min(300, max(30, remaining)))

        expectations = {
            "accept": ("ACCEPT", lambda escrow: (0, escrow)),
            "partial": ("PARTIAL", lambda escrow: (escrow // 2, escrow - escrow // 2)),
            "reject": ("REJECT", lambda escrow: (escrow, 0)),
            "challenge": ("ACCEPT", lambda escrow: (0, escrow)),
        }
        for name, (decision, payout_fn) in expectations.items():
            entry = self.state["scenarios"].get(name)
            if not entry or entry.get("errors") or not entry.get("verdicts"):
                self.log("finalize_skip", scenario=name, reason="missing or failed")
                continue
            try:
                agreement_id = entry["agreement_id"]
                verdict = json.loads(
                    self.read("get_verdict_json", [agreement_id])
                )
                expected_buyer, expected_seller = payout_fn(int(entry["escrow"]))
                if verdict["decision"] != decision:
                    raise RuntimeError(
                        f"expected {decision}, got {verdict['decision']}"
                    )
                if (
                    int(verdict["payout_buyer"]) != expected_buyer
                    or int(verdict["payout_seller"]) != expected_seller
                ):
                    raise RuntimeError(
                        "unexpected payouts "
                        f"{verdict['payout_buyer']}/{verdict['payout_seller']}"
                    )
                entry["transactions"]["settle"] = self.send(
                    self.buyer, "settle", [agreement_id]
                )
                entry["status_after_settle"] = self.read(
                    "get_status", [agreement_id]
                )
                entry["claims"] = self.claims()
                withdrawer = self.seller if expected_seller > 0 else self.buyer
                entry["transactions"]["withdraw"] = self.send(
                    withdrawer, "withdraw", ["evm"]
                )
                entry["claims_after_withdraw"] = self.claims()
                self.save()
                self.log(
                    "settled",
                    scenario=name,
                    decision=verdict["decision"],
                    score=verdict["score"],
                    paid_buyer=verdict["payout_buyer"],
                    paid_seller=verdict["payout_seller"],
                )
            except Exception as error:
                self.record_error(name, error)

        entry = self.state["scenarios"].get("expiry")
        if entry and not entry.get("errors"):
            try:
                agreement_id = entry["agreement_id"]
                entry["transactions"]["claim_expired"] = self.send(
                    self.buyer, "claim_expired", [agreement_id]
                )
                entry["status_after_claim"] = self.read(
                    "get_status", [agreement_id]
                )
                entry["claims"] = self.claims()
                entry["transactions"]["withdraw"] = self.send(
                    self.buyer, "withdraw", ["evm"]
                )
                entry["claims_after_withdraw"] = self.claims()
                self.save()
                self.log("expired", scenario="expiry", refunded=entry["escrow"])
            except Exception as error:
                self.record_error("expiry", error)

        entry = self.state["scenarios"].get("cancel")
        if entry and entry.get("cancelled"):
            try:
                # Claims are global per address. An earlier buyer withdrawal
                # may already have included this cancellation refund, in which
                # case there is nothing left to withdraw here.
                claims = self.claims()
                entry["claims"] = claims
                if claims["buyer"] > 0:
                    entry["transactions"]["withdraw"] = self.send(
                        self.buyer, "withdraw", ["evm"]
                    )
                    entry["claims_after_withdraw"] = self.claims()
                    self.log("cancelled_withdrawn", scenario="cancel")
                else:
                    entry["claims_after_withdraw"] = claims
                    self.log(
                        "cancel_claim_already_withdrawn",
                        scenario="cancel",
                        note="the refund was included in an earlier buyer withdrawal",
                    )
                entry["errors"] = []
                self.save()
            except Exception as error:
                self.record_error("cancel", error)

        self.state["finalized_at"] = utc_now()
        self.state["totals"] = self.read("get_totals")
        self.save()
        self.log("finalize_complete", totals=self.state["totals"])

    def claims(self) -> dict:
        return {
            "buyer": self.read(
                "get_claim", [CalldataAddress(self.buyer.address)]
            ),
            "seller": self.read(
                "get_claim", [CalldataAddress(self.seller.address)]
            ),
        }


def print_summary(state: dict) -> None:
    print(
        "| Scenario | Agreement | Decision | Score | Buyer payout | "
        "Seller payout | Final status |"
    )
    print("|---|---|---|---:|---:|---:|---|")
    for name in SCENARIOS:
        entry = state["scenarios"].get(name)
        if not entry:
            continue
        verdicts = entry.get("verdicts") or []
        verdict = verdicts[-1]["verdict"] if verdicts else {}
        status = (
            entry.get("status_after_claim")
            or entry.get("status_after_settle")
            or entry.get("status_after_reevaluate")
            or entry.get("status_after_cancel")
            or ""
        )
        errors = entry.get("errors") or []
        print(
            "| {name} | `{aid}` | {decision} | {score} | {buyer} | "
            "{seller} | {status}{errors} |".format(
                name=name,
                aid=entry.get("agreement_id", ""),
                decision=verdict.get("decision", ""),
                score=verdict.get("score", ""),
                buyer=verdict.get("payout_buyer", ""),
                seller=verdict.get("payout_seller", ""),
                status=status,
                errors=" **ERROR**" if errors else "",
            )
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase", choices=("init", "finalize", "summary"), required=True
    )
    parser.add_argument(
        "--contract",
        default=os.environ.get("PRESENSE_CONTRACT", DEFAULT_CONTRACT),
    )
    parser.add_argument(
        "--explorer",
        default=os.environ.get("PRESENSE_EXPLORER", DEFAULT_EXPLORER),
    )
    parser.add_argument("--credentials", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--keystore-dir", type=Path, default=DEFAULT_KEYSTORE_DIR)
    parser.add_argument("--escrow", type=int, default=10**15)
    parser.add_argument("--log", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.phase == "summary":
        state = json.loads(args.state.read_text(encoding="utf-8"))
        print_summary(state)
        return 0

    log_path = args.log or args.state.with_suffix(".log.jsonl")
    runner = Runner(
        contract=args.contract,
        explorer=args.explorer,
        state_path=args.state,
        credentials_path=args.credentials,
        keystore_dir=args.keystore_dir,
        escrow=args.escrow,
        log_path=log_path,
    )
    runner.log(
        "start",
        phase=args.phase,
        contract=args.contract,
        buyer=runner.buyer.address,
        seller=runner.seller.address,
        version=runner.read("get_version"),
    )
    if args.phase == "init":
        runner.init()
    else:
        runner.finalize()
    runner.log("state", state=runner.state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
