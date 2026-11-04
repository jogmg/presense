# 06 — Implementation Plan

**Project:** Presense
**Version:** 0.1
**Purpose:** Turn the specification into a build sequence with clear deliverables and definition-of-done gates.

---

## 1. Build philosophy

1. **Spec first, then code.** The manifest schema and equivalence rules are the hard parts; write them before Solidity-style contract code.
2. **Small vertical slices.** Each phase ends with something testable.
3. **Deterministic before probabilistic.** Get the lifecycle and accounting right before adding LLM judgment.
4. **Test the lie early.** Build the malicious-leader test in Phase 4, not at the end.
5. **Deploy only after localnet.** Bradbury is for validation, not first-run debugging.

---

## 2. Phase overview

| Phase | Name                   | Output                                         | Estimate |
| ----- | ---------------------- | ---------------------------------------------- | -------- |
| 0     | Setup                  | Repo, tooling, skeleton                        | 0.5 day  |
| 1     | Manifest core          | Parser, validator, canonicalization, tests     | 1.5 days |
| 2     | Lifecycle and escrow   | Create, accept, cancel, submit, expire, claims | 2 days   |
| 3     | Objective checks       | Fetch, 4 checks, evidence policy               | 1.5 days |
| 4     | Subjective + consensus | LLM rubric, validator, adversarial tests       | 2.5 days |
| 5     | Verdict and settlement | Verdict, payout, challenge, settle, withdraw   | 1.5 days |
| 6     | Hardening              | Security tests, lint, review, docs sync        | 1 day    |
| 7     | Deploy and submit      | Bradbury, evidence, portal                     | 1 day    |

**Total:** ~11.5 working days. A solo builder can compress this to 10 days by running docs and tests in parallel.

---

## 3. Phase 0 — Setup

**Status: complete.**

### Tasks

- [x] Create `contracts/`, `tests/direct/`, `tests/integration/`, `deploy/`, `examples/`.
- [x] Add `requirements.txt`:
  ```text
  genlayer-test==0.29.2
  genvm-linter==0.11.0
  pytest>=9,<10
  pytest-cov>=7,<8
  ```
- [x] Add `.gitignore` for `.venv/`, `__pycache__/`, `.pytest_cache/`, `*.pyc`, `.env`, artifacts, and local config.
- [x] Add `pyproject.toml` with test paths and coverage settings.
- [x] Add the contract magic comment.
- [x] Add a minimal `Presense.py` with `__init__` and `get_version` view.
- [x] Verify `genvm-lint check` runs.
- [x] Verify `pytest` discovers and passes the smoke test.
- [x] Add `tests/conftest.py` shims for the pinned toolchain.

### Deliverable

A repository that lints, validates, and runs a one-test direct suite.

### Definition of done

- [x] `genvm-lint check contracts/Presense.py` exits 0.
- [x] `pytest tests/direct/ -v` exits 0 (one trivial test).
- [x] The magic comment is present and exact.

### Verified locally

```text
✓ Lint passed (3 checks)
✓ Validation passed
  Contract: Presense
  Methods: 1 (1 view, 0 write)

tests/direct/test_smoke.py::test_contract_deploys_and_reports_version PASSED
1 passed
```

Environment: Python 3.13.7, Windows, `genlayer-test 0.29.2`,
`genvm-linter 0.11.0`, `pytest 9.2.0`.

---

## 4. Phase 1 — Manifest core

**Status: complete.**

### Goal

Make the acceptance manifest the most rigorously validated object in the system.

### Tasks

- [x] Define constants.
- [x] Implement strict JSON parsing:
  - reject duplicate keys,
  - reject `NaN`/`Infinity`,
  - reject non-object top level,
  - reject trailing content.
- [x] Implement canonicalization:
  - `sort_keys=True`,
  - `separators=(",", ":")`,
  - `ensure_ascii=False`.
- [x] Compute SHA-256.
- [x] Enforce 16 KiB cap on raw and canonical bytes.
- [x] Validate top-level fields.
- [x] Validate criteria:
  - count 1–20,
  - unique IDs,
  - kinds,
  - checks,
  - weights sum 100,
  - mandatory flag.
- [x] Validate decision policy.
- [x] Validate evidence policy.
- [x] Validate URLs and domains.
- [x] Write `parse_manifest(raw: str) -> ParsedManifest`.
- [x] Write unit tests for every rejection case.
- [x] Expose `check_manifest` as a read-only dry-run view.

### Deliverable

`parse_manifest` and `validate_manifest` are pure, tested functions with no network or state dependency.

### Definition of done

- [x] All §5.1 tests pass.
- [x] Canonicalization is stable across key order.
- [x] The hash matches the stored canonical string.
- [x] No `dict` or `list` is used for persistent storage.
- [x] Invalid manifests never reach state.

### Verified locally

```text
✓ Lint passed (3 checks)
✓ Validation passed
  Contract: Presense
  Methods: 3 (3 view, 0 write)

95 passed
contracts/Presense.py  96% coverage (branches included)
```

### Design note

Keep the parser as a pure helper. The contract method calls it, but the parser does not read contract state. `check_manifest` applies the exact same parser and validator that `create_agreement` will call in Phase 2.

---

## 5. Phase 2 — Lifecycle and escrow

**Status: complete.**

### Goal

A complete money lifecycle with no evaluation yet.

### Tasks

- [x] Define `Agreement` and `Submission` storage types and the `TreeMap[Address, u256]` claim ledger.
- [x] Implement `create_agreement` payable.
- [x] Implement `accept_agreement`.
- [x] Implement `cancel_agreement`.
- [x] Implement `submit_delivery`.
- [x] Implement `claim_expired`.
- [x] Implement `withdraw(kind)` with `evm`/`ic` routing.
- [x] Implement view methods: `get_agreement`, `get_agreement_json`, `get_status`, `get_claim`, `get_totals`, and `get_constants`.
- [x] Implement `_now()` using the transaction-pinned GenVM clock.
- [x] Implement agreement and claim helpers.
- [x] Write lifecycle tests.
- [x] Write accounting conservation tests.

### Deliverable

A contract that can hold escrow, accept work, submit delivery, cancel, expire, and withdraw — without evaluating quality.

### Definition of done

- [x] All lifecycle tests pass.
- [x] Buyer/seller roles are enforced.
- [x] Escrow is tracked from `gl.message.value`, not `self.balance`.
- [x] `total_locked` is correct after create, cancel, expire, withdraw.
- [x] `withdraw` cannot double-spend.
- [x] No evaluation code exists yet.

### Verified locally

```text
✓ Lint passed (3 checks)
✓ Validation passed
  Contract: Presense
  Methods: 14 (8 view, 6 write)

108 passed
contracts/Presense.py  96% coverage (branches included)
```

The contract intentionally has no `__receive__` handler: GenVM rejects value-only transfers by default, while the pinned linter rejects a custom public double-underscore method.

### Common mistakes to avoid

- Using `int` instead of `u256` for value fields.
- Using `dict`/`list` instead of `TreeMap`/`DynArray`.
- Forgetting to check `status` before every transition.
- Treating `self.balance` as the escrow ledger.
- Emitting a transfer before zeroing the claim.

---

## 6. Phase 3 — Objective checks

**Status: implemented with a documented runtime limitation.** The checks and mocked direct-mode coverage are in place. Final-domain verification for redirects transparently followed by the web backend and control of the backend timeout remain unresolved in the pinned SDK.

### Goal

Deterministic evidence checks with a strict fetch policy.

### Tasks

- [x] Implement `_fetch(url, policy)` with a shared evaluation byte budget.
- [x] Enforce HTTPS and allowed domains for source URLs and each visible redirect destination.
- [x] Enforce per-source and cumulative byte caps before parsing response bodies.
- [x] Enforce redirect hop cap for visible 3xx responses.
- [x] Treat web request exceptions, including runtime timeouts, as `MISSING`; custom timeout values are not supported by the pinned SDK.
- [x] Implement `http_status`, including `GET` and `HEAD`.
- [x] Implement `json_has_keys` with dot paths, array indexes, and optional types.
- [x] Implement `file_hash`.
- [x] Implement `text_contains` with whitespace and case normalization.
- [x] Implement `MISSING` vs `FAIL` classification.
- [x] Mock web responses in direct mode.
- [x] Write tests for pass, fail, missing, oversize, total cap, disallowed redirect, and redirect cap.
- [x] Wire checks into `_run_objective(criterion, evidence_policy)` and `preview_objective_checks`.
- [ ] Confirm the web backend does not transparently follow redirects, or update the runtime/API to expose a final URL or disable redirects.
- [ ] Apply `missing_evidence` policy when the Phase 4/5 verdict builder consumes objective results.

### Deliverable

Four objective checks that return structured results and never crash the evaluation on a network error.

### Definition of done

- [x] All implemented §7 objective tests pass.
- [x] Fetch caps are enforced before parsing.
- [ ] Missing evidence follows the policy in the verdict builder.
- [x] No LLM is used for objective checks.
- [x] Each result includes `criterion_id`, `passed`, `score`, `reason`, `evidence_url`.

### Design note

Use `gl.nondet.web.request` inside the non-deterministic block. Do not fetch in a view method. Do not cache evidence across transactions. The pinned response exposes `status`, `headers`, and `body` only; no final URL or timeout/redirect controls are available. `preview_objective_checks` is a write operation because it performs network access and uses strict equivalence, but it does not persist results.

---

## 7. Phase 4 — Subjective checks and consensus

**Status: implementation complete.** Direct tests cover honest evaluation, a schema-valid lie, prompt injection, and score-tolerance boundaries. Dedicated wrong-decision and pass-mismatch tests remain open in the definition of done.

### Goal

The hard part: an LLM rubric with independent validator verification.

### Tasks

- [x] Implement the prompt builder with evidence delimiters and security rules.
- [x] Call `gl.nondet.exec_prompt` and parse LLM JSON defensively.
- [x] Implement evidence normalization.
- [x] Implement quote verification.
- [x] Implement `_run_subjective(criterion, evidence_policy)`.
- [x] Implement `_build_verdict_payload`.
- [x] Implement `_equivalent(leader, mine)`.
- [x] Implement `evaluate` with `run_nondet_unsafe`.
- [x] Implement deterministic post-processing:
  - validate leader shape,
  - validate decision consistency,
  - compute payout,
  - set timestamps.
- [x] Write validator tests with `direct_vm.run_validator`.
- [x] Write the schema-valid lie test.
- [x] Write the prompt-injection test.
- [x] Write score-tolerance tests.

### Deliverable

A working `evaluate` that stores a verdict only when the leader and validator agree.

### Definition of done

- [x] Honest leader passes.
- [x] Schema-valid lie fails.
- [ ] Wrong decision fails.
- [ ] Wrong objective pass fails.
- [ ] Subjective pass mismatch fails.
- [x] Invalid quote fails.
- [x] Score outside tolerance fails.
- [x] Score within tolerance passes.
- [x] Prompt-injection test does not produce a false ACCEPT.
- [x] `strict_eq` is not used for raw LLM output.

### Design note

Do not compare `reason` or `summary`. Do not let the leader set payout or timestamps. The validator must fetch evidence itself.

---

## 8. Phase 5 — Verdict, challenge, settlement

### Goal

Close the economic loop.

### Tasks

- [ ] Define `Verdict` and `CriterionResult`.
- [ ] Materialize verdict from the accepted leader payload.
- [ ] Compute score and payout.
- [ ] Implement `challenge`.
- [ ] Implement re-evaluation with counter-evidence.
- [ ] Implement `settle`.
- [ ] Implement `preview_payout`.
- [ ] Implement `get_verdict`, `get_verdict_json`.
- [ ] Write payout tests for ACCEPT/PARTIAL/REJECT.
- [ ] Write challenge tests.
- [ ] Write settlement-window tests.
- [ ] Write withdraw tests for both kinds.
- [ ] Write conservation tests.

### Deliverable

A complete agreement lifecycle from creation to withdrawal.

### Definition of done

- [ ] ACCEPT pays seller.
- [ ] REJECT refunds buyer.
- [ ] PARTIAL splits pro rata with floor.
- [ ] `buyer + seller == escrow` on every path.
- [ ] Challenge window is enforced.
- [ ] One challenge limit is enforced.
- [ ] Settlement is permissionless.
- [ ] Double settlement reverts.
- [ ] Double withdrawal reverts.
- [ ] `total_locked` matches held funds.

---

## 9. Phase 6 — Hardening

### Goal

Make the contract defensible before deployment.

### Tasks

- [ ] Run `genvm-lint check`.
- [ ] Run the full direct suite with coverage.
- [ ] Run adversarial tests.
- [ ] Run property-based payout tests.
- [ ] Review every error code.
- [ ] Review every state transition.
- [ ] Review every external fetch.
- [ ] Review every value movement.
- [ ] Check storage types (`TreeMap`, `DynArray`, `u256`).
- [ ] Check for unbounded loops.
- [ ] Check for `dict`/`list` storage.
- [ ] Check for admin or upgrade hooks (should be none).
- [ ] Update docs if the interface changed.
- [ ] Ask a peer reviewer to read the contract against the spec.
- [ ] Fix findings.
- [ ] Re-run everything.

### Deliverable

A release candidate with no known critical issues.

### Definition of done

- [ ] Lint exits 0.
- [ ] Coverage ≥ 85%.
- [ ] All tests pass.
- [ ] No critical or high findings open.
- [ ] Docs match code.
- [ ] The portal narrative is drafted.

---

## 10. Phase 7 — Deploy and submit

### Goal

Prove the contract on Bradbury and submit it to the builder portal.

### Tasks

- [ ] Deploy to Localnet and run integration tests.
- [ ] Deploy to Bradbury.
- [ ] Verify the explorer shows the contract.
- [ ] Run the smoke test:
  - create,
  - accept,
  - submit,
  - evaluate,
  - settle,
  - withdraw.
- [ ] Run a challenge scenario.
- [ ] Run an expiry scenario.
- [ ] Save transaction hashes and verdict JSON.
- [ ] Write the portal description.
- [ ] Add the GitHub repo URL and deployed address.
- [ ] Submit to category 52.
- [ ] Respond to review feedback.

### Deliverable

A deployed contract, a public repo, and a submitted contribution.

### Definition of done

- [ ] Bradbury address is public.
- [ ] At least three lifecycle transactions are confirmed.
- [ ] At least one evaluation and one settlement are confirmed.
- [ ] At least one withdrawal is confirmed.
- [ ] The repo README explains the primitive and links the docs.
- [ ] The portal submission includes the required evidence.

---

## 11. Ten-day schedule

| Day | Focus                   | Output                                      |
| --- | ----------------------- | ------------------------------------------- |
| 1   | Phase 0 + Phase 1 start | Repo, skeleton, parser tests.               |
| 2   | Phase 1 finish          | Manifest validation complete.               |
| 3   | Phase 2 start           | Create/accept/cancel.                       |
| 4   | Phase 2 finish          | Submit/expire/withdraw.                     |
| 5   | Phase 3                 | Objective checks + mocks.                   |
| 6   | Phase 4 start           | LLM rubric + prompt.                        |
| 7   | Phase 4 finish          | Validator + adversarial tests.              |
| 8   | Phase 5                 | Verdict, challenge, settlement.             |
| 9   | Phase 6                 | Hardening, review, docs.                    |
| 10  | Phase 7                 | Bradbury deploy, smoke tests, portal draft. |

**Buffer:** Days 11–12 for review feedback and portal submission. Do not compress the consensus tests.

---

## 12. File-by-file plan

```text
contracts/
└── Presense.py

tests/direct/
├── conftest.py
├── test_manifest.py
├── test_lifecycle.py
├── test_checks_objective.py
├── test_checks_subjective.py
├── test_validator.py
├── test_settlement.py
└── test_security.py

tests/integration/
├── test_localnet_lifecycle.py
└── test_bradbury_lifecycle.py

deploy/
└── 001_deploy_presense.ts

examples/
├── manifest.weather-api.json
├── manifest.docs-delivery.json
└── manifest.bad-example.json

tools/
└── manifest_lint.py        # optional: off-chain manifest linter
```

### `Presense.py` internal organization

```python
# 1. Header and imports
# 2. Constants
# 3. Storage dataclasses
# 4. Contract class
# 5. __init__
# 6. Public write methods
# 7. Public view methods
# 8. Internal lifecycle helpers
# 9. Internal validation helpers
# 10. Internal fetch/check helpers
# 11. Internal consensus helpers
# 12. Internal payout/accounting helpers
```

Keep helpers small and pure where possible. The contract file should remain readable in one sitting.

---

## 13. Coding standards

- Use `u256` for GEN amounts and timestamps.
- Use `u8` for scores and weights.
- Use `TreeMap` for keyed storage.
- Use `DynArray` for lists.
- Use `str` for statuses and decisions.
- Use `gl.vm.UserError("CODE: message")` for errors.
- Do not use `assert` for user input; use explicit checks and `UserError`.
- Do not use `print` for production logic; it is only for debugging.
- Keep method bodies under ~80 lines where practical.
- Name helpers with `_require_`, `_validate_`, `_fetch_`, `_run_`, `_build_`, `_compute_`.
- Document every public method with a docstring.
- Add a comment at every non-obvious consensus or money decision.

---

## 14. Review gates

### Gate 1 — After Phase 1

- Manifest validation is complete.
- Rejection tests exist.
- Canonicalization is stable.

### Gate 2 — After Phase 2

- Money lifecycle works without evaluation.
- Accounting conservation passes.
- No role bypass.

### Gate 3 — After Phase 4

- Validator rejects a schema-valid lie.
- Prompt injection does not produce a false ACCEPT.
- Score tolerance is bounded.

### Gate 4 — Before Bradbury

- Lint passes.
- Full suite passes.
- Peer review complete.
- No critical findings.

### Gate 5 — Before portal submission

- Bradbury smoke tests pass.
- Explorer evidence is saved.
- Repo and docs are public.
- Submission narrative matches the code.

---

## 15. Risk register

| Risk                 | Probability | Impact | Mitigation                                                        |
| -------------------- | ----------- | ------ | ----------------------------------------------------------------- |
| Manifest parser bugs | Medium      | High   | Pure helpers, duplicate-key tests, fuzz cases.                    |
| LLM output variance  | High        | Medium | Tolerance bands, quote checks, `UNDETERMINED`.                    |
| Evidence instability | Medium      | High   | Hashes, multiple sources, size caps.                              |
| Validator logic bug  | Medium      | High   | Adversarial tests, peer review, `run_validator` tests.            |
| Payout rounding bug  | Low         | High   | Conservation tests, floor + remainder.                            |
| Scope creep          | High        | High   | Freeze v1; move bonds/milestones/privacy to v2.                   |
| Bradbury flakiness   | Medium      | Medium | Retry, small escrow, save evidence, localnet first.               |
| Portal rejection     | Medium      | Medium | Follow category 52 evidence rules; emphasize consensus, not demo. |
| Time underestimation | Medium      | Medium | 2-day buffer; cut features, not tests.                            |

---

## 16. What to cut first if time is short

Cut in this order:

1. `text_contains` (keep 3 objective checks).
2. Challenge flow (keep evaluate + settle).
3. `metadata_url`.
4. `get_verdict_json`.
5. `preview_payout`.

Do **not** cut:

- manifest validation,
- independent validator,
- evidence quote verification,
- payout conservation,
- adversarial tests,
- Bradbury smoke test.

---

## 17. Definition of done for v1

Presense v1 is done when:

- [ ] The contract is implemented and lint-clean.
- [ ] The direct suite passes with coverage ≥ 85%.
- [ ] The schema-valid lie test fails the validator.
- [ ] The prompt-injection test fails the validator.
- [ ] The full lifecycle passes on Localnet.
- [ ] At least five scenarios pass on Bradbury.
- [ ] The repo is public with this documentation.
- [ ] The portal submission is submitted with the required evidence.
- [ ] A reviewer can understand the consensus design without reading the code first.

---

## 18. Next document

Read [07 — Deployment Runbook](07-deployment-runbook.md) for the exact commands and environments.
