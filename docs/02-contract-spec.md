# 02 — Contract Specification

**Project:** Presense
**Version:** 0.1
**Contract:** `contracts/Presense.py`
**Runtime:** `py-genlayer` (magic comment below)
**Status:** Phases 0–6 implemented (manifest core, lifecycle/escrow, objective checks, subjective evaluation, hardened leader/validator consensus, challenge, payout, settlement, and security tests). Phase 6 adds no public API methods.

---

## 1. Contract header

```python
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
import typing

@gl.evm.contract_interface
class _Recipient:
    """External-message interface for EOAs and EVM contracts."""
    class View:
        pass
    class Write:
        pass
```

### 1.1 Import rules

- `genlayer import *` provides `gl`, `u256`, `Address`, `TreeMap`, `DynArray`, `allow_storage`, `dataclass`, etc.
- `json`, `hashlib`, `re`, `datetime`, `typing` are used for parsing, hashing, URL validation, and types.
- No `os`, `sys`, `subprocess`, or filesystem access.
- No external network libraries; use `gl.nondet.web`.

---

## 2. Data types

### 2.1 Agreement

```python
@allow_storage
@dataclass
class Agreement:
    id: str
    buyer: Address
    seller: Address
    manifest_json: str
    manifest_hash: str
    manifest_url: str
    metadata_url: str
    escrow: u256
    deadline: u256
    challenge_window: u256
    created_at: u256
    status: str
    submission_id: str
    verdict_id: str
    challenge_id: str
    challenge_count: u8
    evaluated_at: u256
```

### 2.2 Submission

```python
@allow_storage
@dataclass
class Submission:
    id: str
    agreement_id: str
    artifact_urls: DynArray[str]
    artifact_hashes: DynArray[str]
    notes: str
    submitted_at: u256
    submitter: Address
```

### 2.3 CriterionResult

```python
@allow_storage
@dataclass
class CriterionResult:
    criterion_id: str
    kind: str          # "objective" | "subjective"
    check: str         # check type
    passed: bool
    score: u8          # 0..10
    weight: u8         # 1..100
    reason: str
    evidence_url: str
    evidence_quote: str
```

### 2.4 Verdict

```python
@allow_storage
@dataclass
class Verdict:
    id: str
    agreement_id: str
    manifest_hash: str
    decision: str      # "ACCEPT" | "PARTIAL" | "REJECT" | "UNDETERMINED"
    score: u8          # 0..100
    payout_buyer: u256
    payout_seller: u256
    summary: str
    results: DynArray[CriterionResult]
    evaluated_at: u256
    evaluator: Address
    challenge_deadline: u256
```

### 2.5 Challenge

```python
@allow_storage
@dataclass
class Challenge:
    id: str
    agreement_id: str
    challenger: Address
    reason: str
    evidence_urls: DynArray[str]
    evidence_hashes: DynArray[str]
    created_at: u256
```

---

## 3. State variables

```python
class Presense(gl.Contract):
    agreements: TreeMap[str, Agreement]
    submissions: TreeMap[str, Submission]
    verdicts: TreeMap[str, Verdict]
    challenges: TreeMap[str, Challenge]
    claims: TreeMap[Address, u256]
    total_locked: u256

    def __init__(self):
        pass
```

### 3.1 Time

GenVM’s clock is pinned to the transaction timestamp, so every validator sees the same value. Use:

```python
def _now(self) -> u256:
    return u256(int(datetime.now(timezone.utc).timestamp()))
```

Do not use host wall-clock time. All `deadline`, `created_at`, `evaluated_at`, and `challenge_deadline` values are Unix seconds from this helper.

### 3.2 Accounting model

- `total_locked` is the total GEN held by the contract for escrow plus unwithdrawn claims.
- On `create_agreement`, `total_locked += gl.message.value`.
- On `settle`, `cancel`, or `expire`, escrow becomes claims; `total_locked` does not change.
- On `withdraw`, `claims[sender] -= amount` and `total_locked -= amount`.
- Invariant: `total_locked == sum(unsettled escrow) + sum(claims)` at all times.

There is no admin, no pause, no upgrade proxy, and no treasury in v1.

---

## 4. Public API

### 4.1 `create_agreement`

```python
@gl.public.write.payable
def create_agreement(
    self,
    agreement_id: str,
    seller: Address,
    manifest_json: str,
    manifest_url: str,
    deadline: u256,
    challenge_window: u256,
    metadata_url: str,
) -> str:
```

**Auth:** any caller becomes the buyer.

**Preconditions:**

- `agreement_id` is 1–64 chars, matching `[A-Za-z0-9_-]+`.
- `agreement_id` does not exist.
- `seller != gl.message.sender_address` (`E_SELF_AGREEMENT`).
- `seller != Address(0)` and `seller != gl.message.contract_address` (`E_ZERO_ADDRESS`).
- `gl.message.value > 0` (`E_ESCROW_ZERO`).
- `deadline > now` and `deadline >= now + MIN_DEADLINE_SECONDS`.
- `challenge_window` is between `MIN_CHALLENGE_WINDOW` and `MAX_CHALLENGE_WINDOW`.
- `manifest_json` is ≤ `MAX_MANIFEST_BYTES` before parsing, and its canonical form is also ≤ `MAX_MANIFEST_BYTES` after parsing.
- `manifest_url` and `metadata_url` are empty or valid HTTPS URLs. They are informational and do not need to match `allowed_domains`.
- All criterion URLs pass the manifest’s evidence policy.

**Effects:**

- Stores a canonical manifest string and its SHA-256 hash.
- Creates `Agreement` with `status = "CREATED"`.
- Adds `gl.message.value` to `total_locked`.
- Returns `agreement_id`.

**Errors:** `E_AGREEMENT_EXISTS`, `E_BAD_ID`, `E_SELF_AGREEMENT`, `E_ZERO_ADDRESS`, `E_ESCROW_ZERO`, `E_DEADLINE_INVALID`, `E_WINDOW_INVALID`, `E_MANIFEST_INVALID`, `E_MANIFEST_TOO_LARGE`, `E_URL_INVALID`.

---

### 4.2 `accept_agreement`

```python
@gl.public.write
def accept_agreement(self, agreement_id: str) -> None:
```

**Auth:** `gl.message.sender_address == agreement.seller`.

**Preconditions:**

- Agreement exists (`E_NOT_FOUND`).
- `status == "CREATED"` (`E_INVALID_STATE`).
- `now <= deadline` (`E_DEADLINE_PASSED`).

**Effects:** `status = "ACTIVE"`.

**Errors:** `E_NOT_FOUND`, `E_UNAUTHORIZED`, `E_INVALID_STATE`, `E_DEADLINE_PASSED`.

---

### 4.3 `cancel_agreement`

```python
@gl.public.write
def cancel_agreement(self, agreement_id: str) -> None:
```

**Auth:** `gl.message.sender_address == agreement.buyer`.

**Preconditions:**

- Agreement exists.
- `status == "CREATED"` (seller has not accepted).
- No submission exists.

**Effects:**

- `status = "CANCELLED"`.
- `claims[buyer] += escrow`.

**Errors:** `E_NOT_FOUND`, `E_UNAUTHORIZED`, `E_INVALID_STATE`.

---

### 4.4 `submit_delivery`

```python
@gl.public.write
def submit_delivery(
    self,
    agreement_id: str,
    artifact_urls: DynArray[str],
    artifact_hashes: DynArray[str],
    notes: str,
) -> str:
```

**Auth:** `gl.message.sender_address == agreement.seller`.

**Preconditions:**

- Agreement exists.
- `status == "ACTIVE"`.
- `now <= deadline` (`E_DEADLINE_PASSED`).
- `1 <= len(artifact_urls) <= MAX_ARTIFACTS`.
- `len(artifact_urls) == len(artifact_hashes)`.
- Every URL passes the manifest evidence policy.
- Every hash is empty or a 64-char hex SHA-256.
- `len(notes) <= MAX_NOTES_CHARS`.

**Effects:**

- Creates `Submission` with ID `f"{agreement_id}:submission"`.
- Sets `agreement.submission_id`.
- `status = "SUBMITTED"`.
- Returns the submission ID.

**Errors:** `E_NOT_FOUND`, `E_UNAUTHORIZED`, `E_INVALID_STATE`, `E_DEADLINE_PASSED`, `E_ARTIFACT_COUNT`, `E_ARTIFACT_MISMATCH`, `E_BAD_HASH`, `E_URL_INVALID`, `E_EVIDENCE_DOMAIN`.

---

### 4.5 `preview_objective_checks`

```python
@gl.public.write
def preview_objective_checks(self, agreement_id: str) -> typing.Any:
```

**Auth:** anyone. The agreement must be `SUBMITTED` or `DISPUTED` (`E_INVALID_STATE` otherwise).

**Execution:** Runs each objective criterion against independently fetched evidence inside `strict_eq`. Returns one structured result per objective criterion with `criterion_id`, `kind`, `check`, `passed`, `score`, `weight`, `reason`, `evidence_url`, `evidence_quote`, and `status` (`PASS`, `FAIL`, or `MISSING`). This method does not store a verdict or change agreement state. Missing-evidence decision policy is applied by the later verdict builder, not by this preview method.

The pinned `gl.nondet.web.Response` exposes only `status`, `headers`, and `body`; the request API exposes no timeout or redirect option and the response has no final URL. Presense follows and validates redirect responses that the SDK exposes, including each destination's HTTPS/domain policy and the configured cap. It cannot verify redirects transparently followed by the web backend. Until the runtime exposes a final URL or disables automatic redirects, manifests should use direct final-resource URLs; this limitation remains open for production hardening.

### 4.6 `evaluate`

```python
@gl.public.write
def evaluate(self, agreement_id: str) -> str:
```

**Auth:** anyone.

**Preconditions:**

- Agreement exists.
- `status in ("SUBMITTED", "DISPUTED")`.
- If `DISPUTED`, a challenge exists.
- Submission exists.

**Execution:**

1. Parse and validate the stored canonical manifest.
2. Build the evidence list from the submission plus challenge counter-evidence. Subjective criteria receive the manifest source plus bounded supplemental submission/challenge sources; declared hashes are checked. Objective criteria continue to run against their manifest-defined URL.
3. For each criterion, run the check.
4. Build a proposed verdict.
5. Run the leader/validator equivalence block.
6. If the accepted decision is `UNDETERMINED`, raise `E_UNDETERMINED` and store nothing.
7. Store the verdict; set `status = "EVALUATED"`, `evaluated_at = now`, `challenge_deadline = now + challenge_window`.

**Effects:**

- Creates `Verdict` with ID `f"{agreement_id}:verdict:{1 + challenge_count}"` (so the first verdict is `:verdict:1` and the post-challenge verdict is `:verdict:2`).
- Sets `agreement.verdict_id`.
- Returns the verdict ID.

**Errors:** `E_NOT_FOUND`, `E_INVALID_STATE`, `E_NO_SUBMISSION`, `E_UNDETERMINED`, `E_EVIDENCE_MISSING`, `E_CHECK_UNSUPPORTED`.

**Important:** The entire evaluation is a non-deterministic block. The deterministic code after it only stores the accepted result.

---

### 4.7 `challenge`

```python
@gl.public.write
def challenge(
    self,
    agreement_id: str,
    reason: str,
    evidence_urls: DynArray[str],
    evidence_hashes: DynArray[str],
) -> str:
```

**Auth:** buyer or seller.

**Preconditions:**

- Agreement exists.
- `status == "EVALUATED"`.
- `now <= agreement.evaluated_at + agreement.challenge_window`.
- `challenge_count == 0` (v1: one challenge per agreement).
- `1 <= len(reason) <= MAX_REASON_CHARS`.
- `1 <= len(evidence_urls) <= MAX_EVIDENCE_URLS`.
- URLs/hashes lengths match; URLs pass evidence policy; hashes empty or valid SHA-256.

**Effects:**

- Creates `Challenge` with ID `f"{agreement_id}:challenge"`.
- Sets `agreement.challenge_id`, `challenge_count = 1`.
- `status = "DISPUTED"`.
- Returns the challenge ID.

**Errors:** `E_NOT_FOUND`, `E_UNAUTHORIZED`, `E_INVALID_STATE`, `E_CHALLENGE_WINDOW_CLOSED`, `E_CHALLENGE_LIMIT`, `E_REASON_INVALID`, `E_ARTIFACT_COUNT`, `E_ARTIFACT_MISMATCH`, `E_BAD_HASH`, `E_URL_INVALID`, `E_EVIDENCE_DOMAIN`.

**No bond in v1.** The one-challenge limit and gas cost are the only anti-spam measures. v1.1 adds a challenge bond.

---

### 4.8 `settle`

```python
@gl.public.write
def settle(self, agreement_id: str) -> None:
```

**Auth:** anyone.

**Preconditions:**

- Agreement exists.
- `status == "EVALUATED"`.
- `now > agreement.evaluated_at + agreement.challenge_window`.
- Verdict exists and `decision != "UNDETERMINED"`.

**Effects:**

- `claims[buyer] += verdict.payout_buyer`.
- `claims[seller] += verdict.payout_seller`.
- `status = "SETTLED"`.

**Errors:** `E_NOT_FOUND`, `E_INVALID_STATE`, `E_CHALLENGE_WINDOW_OPEN`, `E_NO_VERDICT`.

**Invariant:** `payout_buyer + payout_seller == escrow`.

---

### 4.9 `claim_expired`

```python
@gl.public.write
def claim_expired(self, agreement_id: str) -> None:
```

**Auth:** anyone.

**Preconditions:**

- Agreement exists.
- `status == "ACTIVE"`.
- `now > deadline`.
- No submission exists.

**Effects:**

- `claims[buyer] += escrow`.
- `status = "EXPIRED"`.

**Errors:** `E_NOT_FOUND`, `E_INVALID_STATE`, `E_DEADLINE_NOT_PASSED`, `E_ALREADY_SUBMITTED`.

---

### 4.10 `withdraw`

```python
@gl.public.write
def withdraw(self, kind: str) -> None:
```

**Auth:** any address with a claim.

**Preconditions:**

- `claims[gl.message.sender_address] > 0` (`E_CLAIM_ZERO`).
- `kind in ("evm", "ic")` (`E_BAD_RECIPIENT_KIND`).

**Effects:**

- `amount = claims[sender]`.
- `claims[sender] = 0`.
- `total_locked -= amount`.
- Emit transfer:
  - `kind == "ic"`: `gl.get_contract_at(sender).emit_transfer(value=amount, on="finalized")`.
  - `kind == "evm"`: `_Recipient(sender).emit_transfer(value=amount)`.

`_Recipient` is defined as an EVM contract interface at the top of the contract:

```python
@gl.evm.contract_interface
class _Recipient:
    class View:
        pass
    class Write:
        pass
```

**Errors:** `E_CLAIM_ZERO`, `E_BAD_RECIPIENT_KIND`.

**Note:** State is updated before the message is emitted, preventing double-withdrawal. If the destination message fails, the value may not return automatically; see [04 — Security & Threat Model](04-security-threat-model.md). An IC recipient must implement a payable `__receive__` to accept a pure value transfer; otherwise the child transaction can fail. Integrators should use `"evm"` for EOAs and `"ic"` only for contracts that can receive GEN.

---

### 4.11 Direct value transfers

Presense does not define a `__receive__` handler. GenVM's default dispatcher rejects value-only calls when no receive handler is present, so funding must go through the payable `create_agreement` method. The pinned `genvm-linter 0.11.0` rejects public methods with double-underscore names, so this runtime rejection does not carry a custom `E_DIRECT_TRANSFER` error code.

---

## 5. View API

| Method                               | ID argument   | Returns      | Purpose                                                                         |
| ------------------------------------ | ------------- | ------------ | ------------------------------------------------------------------------------- |
| `check_manifest(manifest_json: str)` | — (raw JSON)  | `typing.Any` | Dry-run validation; returns canonical string, SHA-256, and criterion count.     |
| `get_agreement(id: str)`             | Agreement ID  | `typing.Any` | Structured agreement.                                                           |
| `get_agreement_json(id: str)`        | Agreement ID  | `str`        | Canonical JSON for debugging.                                                   |
| `get_manifest(id: str)`              | Agreement ID  | `str`        | Canonical manifest JSON.                                                        |
| `get_manifest_hash(id: str)`         | Agreement ID  | `str`        | SHA-256 of canonical manifest.                                                  |
| `get_submission(id: str)`            | Submission ID | `typing.Any` | Structured submission.                                                          |
| `get_verdict(id: str)`               | Verdict ID    | `typing.Any` | Structured verdict.                                                             |
| `get_verdict_json(id: str)`          | Verdict ID    | `str`        | Canonical JSON verdict.                                                         |
| `get_challenge(id: str)`             | Challenge ID  | `typing.Any` | Structured challenge.                                                           |
| `get_status(id: str)`                | Agreement ID  | `str`        | Current agreement status.                                                       |
| `get_claim(addr: Address)`           | Address       | `u256`       | Unwithdrawn claim.                                                              |
| `get_totals()`                       | —             | `typing.Any` | `total_locked` and `self.balance`. Use `get_claim(addr)` for individual claims. |
| `get_constants()`                    | —             | `typing.Any` | Limits and version.                                                             |
| `preview_payout(id: str)`            | Agreement ID  | `typing.Any` | Buyer/seller payout from the latest verdict.                                    |

Use `get_agreement(id).verdict_id` to find the verdict ID, `get_agreement(id).submission_id` for the submission ID, and `get_agreement(id).challenge_id` for the challenge ID. View methods must not mutate state and must not call `gl.nondet`.

`get_verdict` and `get_verdict_json` accept the verdict ID; they also accept an agreement ID for backwards-compatible convenience.

`check_manifest` runs the exact parser and validator used by `create_agreement` and returns:

```json
{
  "canonical": "{\"criteria\":[...],...}",
  "hash": "sha256...",
  "criteria": 5
}
```

It never stores state, so clients can validate a manifest before paying gas.

---

## 6. Acceptance Manifest schema

### 6.1 Top level

```json
{
  "schema": "presense.manifest.v1",
  "version": 1,
  "title": "Weather API delivery",
  "description": "Acceptance criteria for the delivered weather API.",
  "artifact": {
    "type": "http_api",
    "primary_url": "https://api.example.com",
    "docs_url": "https://docs.example.com",
    "notes": "Production endpoint and documentation."
  },
  "criteria": [],
  "decision_policy": {},
  "evidence_policy": {},
  "metadata": {}
}
```

### 6.2 Field rules

| Field             | Type    | Required | Rules                                        |
| ----------------- | ------- | -------- | -------------------------------------------- |
| `schema`          | string  | yes      | Exactly `"presense.manifest.v1"`.            |
| `version`         | integer | yes      | Exactly `1`.                                 |
| `title`           | string  | yes      | 1–200 chars.                                 |
| `description`     | string  | yes      | 1–2000 chars.                                |
| `artifact`        | object  | no       | Informational; not used for scoring.         |
| `criteria`        | array   | yes      | 1–20 items; unique `id`; weights sum to 100. |
| `decision_policy` | object  | yes      | See §6.4.                                    |
| `evidence_policy` | object  | yes      | See §6.5.                                    |
| `metadata`        | object  | no       | Arbitrary JSON; not used for scoring.        |

Unknown fields are rejected at every schema level. Put vendor extensions under `metadata`, never beside a defined field.

### 6.3 Criterion

```json
{
  "id": "C1",
  "title": "Health endpoint returns 200",
  "kind": "objective",
  "check": "http_status",
  "weight": 20,
  "mandatory": true,
  "params": {
    "url": "https://api.example.com/health",
    "expected_status": 200,
    "method": "GET"
  }
}
```

| Field       | Type    | Required | Rules                                 |
| ----------- | ------- | -------- | ------------------------------------- |
| `id`        | string  | yes      | 1–32 chars; unique; `[A-Za-z0-9_-]+`. |
| `title`     | string  | yes      | 1–200 chars.                          |
| `kind`      | string  | yes      | `"objective"` or `"subjective"`.      |
| `check`     | string  | yes      | One of the supported checks in §7.    |
| `weight`    | integer | yes      | 1–100; sum of all weights = 100.      |
| `mandatory` | boolean | yes      | If true, failure forces `REJECT`.     |
| `params`    | object  | yes      | Check-specific.                       |

`kind` must match the check classification in §7: the first four checks are `objective`; `llm_rubric` is `subjective`.

### 6.4 Decision policy

```json
{
  "accept_threshold": 80,
  "partial_threshold": 50,
  "mandatory_must_pass": true,
  "missing_evidence": "UNDETERMINED",
  "partial_payout": "pro_rata",
  "score_rounding": "floor"
}
```

| Field                 | Type    | Required | Rules                                           |
| --------------------- | ------- | -------- | ----------------------------------------------- |
| `accept_threshold`    | integer | yes      | 0–100.                                          |
| `partial_threshold`   | integer | yes      | 0–100; `partial_threshold <= accept_threshold`. |
| `mandatory_must_pass` | boolean | yes      | v1 requires `true`.                             |
| `missing_evidence`    | string  | yes      | `"UNDETERMINED"` or `"REJECT"`.                 |
| `partial_payout`      | string  | yes      | v1 requires `"pro_rata"`.                       |
| `score_rounding`      | string  | yes      | v1 requires `"floor"`.                          |

### 6.5 Evidence policy

```json
{
  "allowed_domains": ["api.example.com", "docs.example.com"],
  "require_https": true,
  "max_bytes_per_source": 2000000,
  "max_total_bytes": 10000000,
  "max_sources_per_criterion": 5,
  "allow_redirects": true,
  "max_redirects": 3
}
```

| Field                       | Type    | Required | Rules                                                    |
| --------------------------- | ------- | -------- | -------------------------------------------------------- |
| `allowed_domains`           | array   | yes      | 1–20 non-empty strings. Exact domain or `*.example.com`. |
| `require_https`             | boolean | yes      | v1 requires `true`.                                      |
| `max_bytes_per_source`      | integer | yes      | 1,000–5,000,000.                                         |
| `max_total_bytes`           | integer | yes      | 1,000–20,000,000.                                        |
| `max_sources_per_criterion` | integer | yes      | 1–5.                                                     |
| `allow_redirects`           | boolean | yes      | v1 requires `true`.                                      |
| `max_redirects`             | integer | yes      | 0–3.                                                     |

**Domain matching:**

- `"example.com"` matches `example.com` and any subdomain.
- `"*.example.com"` matches subdomains but not the bare domain.
- Matching is case-insensitive and ignores a trailing dot.

**URL rules:**

- Must be HTTPS.
- Max 2048 characters.
- No username or password.
- No `localhost`, `127.0.0.1`, `0.0.0.0`, `[::1]`, or private IPv4 ranges (`10.`, `172.16.`–`172.31.`, `192.168.`).
- Must match an allowed domain.

---

## 7. Check DSL

### 7.1 `http_status` (objective)

```json
{
  "url": "https://api.example.com/health",
  "expected_status": 200,
  "method": "GET"
}
```

| Param             | Type         | Required | Rules                                   |
| ----------------- | ------------ | -------- | --------------------------------------- |
| `url`             | string       | yes      | Must pass evidence policy.              |
| `expected_status` | int or array | yes      | 100–599; one or more accepted statuses. |
| `method`          | string       | no       | `GET` or `HEAD`; default `GET`.         |

**Pass:** the fetched response status is in the expected set.

**Failure:** non-matching status, network error, timeout, or oversized body.

---

### 7.2 `json_has_keys` (objective)

```json
{
  "url": "https://api.example.com/openapi.json",
  "required_keys": ["openapi", "paths", "info.title"],
  "types": {
    "openapi": "string",
    "paths": "object"
  }
}
```

| Param           | Type   | Required | Rules                                                                                   |
| --------------- | ------ | -------- | --------------------------------------------------------------------------------------- |
| `url`           | string | yes      | Must pass evidence policy.                                                              |
| `required_keys` | array  | yes      | 1–50 dot paths.                                                                         |
| `types`         | object | no       | Map of dot path → `"string"`, `"number"`, `"boolean"`, `"object"`, `"array"`, `"null"`. |

**Pass:** every dot path exists and, when a type is declared, matches.

**Dot path rules:** keys separated by `.`; array indices use `[n]`, e.g., `paths./weather.get.responses.200`. Literal dots inside a key name are not supported in v1; rename the key or wait for the JSON Pointer mode in v1.1.

---

### 7.3 `file_hash` (objective)

```json
{
  "url": "https://api.example.com/openapi.json",
  "sha256": "9f2c...64-hex..."
}
```

| Param    | Type   | Required | Rules                           |
| -------- | ------ | -------- | ------------------------------- |
| `url`    | string | yes      | Must pass evidence policy.      |
| `sha256` | string | yes      | 64 hex chars, case-insensitive. |

**Pass:** SHA-256 of the fetched bytes equals `sha256`.

---

### 7.4 `text_contains` (objective)

```json
{
  "url": "https://docs.example.com",
  "phrases": ["authentication", "rate limit", "error codes"],
  "case_sensitive": false
}
```

| Param            | Type    | Required | Rules                                     |
| ---------------- | ------- | -------- | ----------------------------------------- |
| `url`            | string  | yes      | Must pass evidence policy.                |
| `phrases`        | array   | yes      | 1–20 non-empty strings; each ≤ 200 chars. |
| `case_sensitive` | boolean | no       | Default `false`.                          |

**Pass:** every phrase appears in the normalized text.

**Normalization:** decode UTF-8 with replacement, collapse whitespace to single spaces, trim.

---

### 7.5 `llm_rubric` (subjective)

```json
{
  "evidence_url": "https://docs.example.com",
  "rubric": "The documentation must explain authentication, rate limits, error codes, and include one end-to-end example. It must not invent endpoints that are absent from the evidence.",
  "threshold": 7,
  "max_chars": 20000
}
```

| Param          | Type    | Required | Rules                      |
| -------------- | ------- | -------- | -------------------------- |
| `evidence_url` | string  | yes      | Must pass evidence policy. |
| `rubric`       | string  | yes      | 20–4000 chars.             |
| `threshold`    | integer | yes      | 0–10.                      |
| `max_chars`    | integer | no       | 1000–50000; default 20000. |

**LLM output:**

```json
{
  "score": 8,
  "pass": true,
  "reason": "Covers auth, rate limits, errors, and one example.",
  "evidence_quote": "Authentication: send the API key in the X-API-Key header."
}
```

**Pass condition:**

- `score >= threshold`, and
- `pass == true`, and
- `evidence_quote` is an exact substring of the normalized, delimiter-sanitized evidence the model saw (whitespace-insensitive), and is at least 20 characters when `pass` is true.

If the quote is not found, the result is a failure, even if the score is high.

---

## 8. Verdict schema

```json
{
  "schema": "presense.verdict.v1",
  "agreement_id": "agr_001",
  "manifest_hash": "sha256...",
  "decision": "PARTIAL",
  "score": 72,
  "payout_buyer": "28000000000000000000",
  "payout_seller": "72000000000000000000",
  "summary": "Two objective checks passed; documentation scored 7/10.",
  "results": [
    {
      "criterion_id": "C1",
      "kind": "objective",
      "check": "http_status",
      "passed": true,
      "score": 10,
      "weight": 20,
      "reason": "HTTP 200",
      "evidence_url": "https://api.example.com/health",
      "evidence_quote": ""
    }
  ],
  "evaluated_at": 1760000000,
  "evaluator": "0x...",
  "challenge_deadline": 1760086400
}
```

### 8.1 Decision rules

1. If any mandatory criterion fails:
   - `missing_evidence == "UNDETERMINED"` and the failure is due to missing evidence → `UNDETERMINED`.
   - otherwise → `REJECT`.
2. Else if `score >= accept_threshold` → `ACCEPT`.
3. Else if `score >= partial_threshold` → `PARTIAL`.
4. Else → `REJECT`.

### 8.2 Score rules

- Objective: `score = 10` if passed, `0` otherwise.
- Subjective: `score = LLM score` (0–10).
- Weighted contribution: `score * weight / 10`.
- Total score: sum of contributions, floored to an integer (0–100).

### 8.3 Payout rules

| Decision       | Buyer payout                           | Seller payout                 |
| -------------- | -------------------------------------- | ----------------------------- |
| `ACCEPT`       | `0`                                    | `escrow`                      |
| `PARTIAL`      | `escrow - floor(escrow * score / 100)` | `floor(escrow * score / 100)` |
| `REJECT`       | `escrow`                               | `0`                           |
| `UNDETERMINED` | no payout                              | no payout                     |

**Invariant:** `payout_buyer + payout_seller == escrow`.

**Rounding:** floor; the buyer receives the remainder. This prevents the seller from receiving a wei more than the score allows.

---

## 9. Error codes

| Code                        | Raised when                                                                                                             |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `E_BAD_ID`                  | Agreement ID is malformed.                                                                                              |
| `E_AGREEMENT_EXISTS`        | Agreement ID already exists.                                                                                            |
| `E_SELF_AGREEMENT`          | Buyer and seller are the same address.                                                                                  |
| `E_ZERO_ADDRESS`            | Seller is the zero address or the contract itself.                                                                      |
| `E_NOT_FOUND`               | Agreement, submission, verdict, or challenge not found.                                                                 |
| `E_UNAUTHORIZED`            | Caller is not the required party.                                                                                       |
| `E_INVALID_STATE`           | Action is not allowed in the current state.                                                                             |
| `E_ESCROW_ZERO`             | `gl.message.value == 0` on create.                                                                                      |
| `E_DEADLINE_INVALID`        | Deadline is in the past or too soon.                                                                                    |
| `E_DEADLINE_PASSED`         | Action requires a deadline that has not passed.                                                                         |
| `E_DEADLINE_NOT_PASSED`     | Expiry requires the deadline to have passed.                                                                            |
| `E_WINDOW_INVALID`          | Challenge window is outside allowed bounds.                                                                             |
| `E_MANIFEST_INVALID`        | Manifest fails schema or semantic validation.                                                                           |
| `E_MANIFEST_TOO_LARGE`      | Canonical manifest exceeds 16 KiB.                                                                                      |
| `E_URL_INVALID`             | URL is malformed, non-HTTPS, or private.                                                                                |
| `E_EVIDENCE_DOMAIN`         | URL is not in `allowed_domains`.                                                                                        |
| `E_ARTIFACT_COUNT`          | Artifact/evidence URL count is outside bounds.                                                                          |
| `E_ARTIFACT_MISMATCH`       | URL and hash arrays have different lengths.                                                                             |
| `E_BAD_HASH`                | Hash is not empty and not 64 hex chars.                                                                                 |
| `E_REASON_INVALID`          | Challenge reason length is invalid.                                                                                     |
| `E_CHALLENGE_WINDOW_CLOSED` | Challenge submitted after the window.                                                                                   |
| `E_CHALLENGE_LIMIT`         | Agreement already has a challenge.                                                                                      |
| `E_NO_SUBMISSION`           | Evaluation requires a submission.                                                                                       |
| `E_NO_VERDICT`              | Settlement requires a verdict.                                                                                          |
| `E_PAYOUT_INVALID`          | Stored buyer and seller payouts do not sum to the agreement escrow.                                                     |
| `E_CHALLENGE_WINDOW_OPEN`   | Settlement attempted before the window closes.                                                                          |
| `E_ALREADY_SUBMITTED`       | Expiry attempted after submission.                                                                                      |
| `E_EVIDENCE_MISSING`        | Required evidence could not be fetched.                                                                                 |
| `E_CHECK_UNSUPPORTED`       | Evaluation encounters a check type it cannot execute. Manifest creation rejects unknown checks as `E_MANIFEST_INVALID`. |
| `E_UNDETERMINED`            | Consensus could not produce a reliable verdict.                                                                         |
| `E_CLAIM_ZERO`              | Withdraw called with no claim.                                                                                          |
| `E_BAD_RECIPIENT_KIND`      | Withdraw kind is not `"evm"` or `"ic"`.                                                                                 |

All listed contract-level errors use `gl.vm.UserError("CODE: human-readable message")`. Value-only calls are rejected by GenVM's dispatcher before contract code runs.

---

## 10. Constants

```python
MAX_MANIFEST_BYTES = 16_384
MAX_CRITERIA = 20
MAX_ARTIFACTS = 10
MAX_EVIDENCE_URLS = 5
MAX_NOTES_CHARS = 2_000
MAX_REASON_CHARS = 1_000
MIN_DEADLINE_SECONDS = 3_600
MIN_CHALLENGE_WINDOW = 3_600          # 1 hour
MAX_CHALLENGE_WINDOW = 604_800        # 7 days
MAX_SOURCE_BYTES = 2_000_000
MAX_TOTAL_BYTES = 10_000_000
MAX_LLM_CHARS = 20_000
MAX_URL_CHARS = 2_048
```

These are exposed through `get_constants()` for clients.

---

## 11. Canonicalization

The manifest is canonicalized before storage:

```python
obj = json.loads(manifest_json)
canonical = json.dumps(
    obj,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
)
manifest_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

Rules:

- Reject raw input larger than `MAX_MANIFEST_BYTES` before calling `json.loads`.
- Reject duplicate keys. Python’s `json.loads` silently keeps the last duplicate; v1 uses a custom `object_pairs_hook` to reject duplicates.
- Reject `NaN` and `Infinity`.
- Reject non-object top level.
- Reject trailing content after the JSON value.
- Reject a canonical form larger than `MAX_MANIFEST_BYTES`.
- Reject unknown fields at the top level, criterion level, policy level, and check-param level.
- Store `canonical` as `manifest_json`.

This guarantees `manifest_hash == sha256(manifest_json)` forever.

---

## 12. Example manifest

```json
{
  "schema": "presense.manifest.v1",
  "version": 1,
  "title": "Weather API delivery",
  "description": "Acceptance criteria for a delivered weather API and its documentation.",
  "artifact": {
    "type": "http_api",
    "primary_url": "https://api.example.com",
    "docs_url": "https://docs.example.com",
    "notes": "Production endpoint and public documentation."
  },
  "criteria": [
    {
      "id": "C1",
      "title": "Health endpoint returns 200",
      "kind": "objective",
      "check": "http_status",
      "weight": 20,
      "mandatory": true,
      "params": {
        "url": "https://api.example.com/health",
        "expected_status": 200,
        "method": "GET"
      }
    },
    {
      "id": "C2",
      "title": "OpenAPI document exposes required keys",
      "kind": "objective",
      "check": "json_has_keys",
      "weight": 20,
      "mandatory": true,
      "params": {
        "url": "https://api.example.com/openapi.json",
        "required_keys": ["openapi", "info.title", "paths"],
        "types": {
          "openapi": "string",
          "paths": "object"
        }
      }
    },
    {
      "id": "C3",
      "title": "OpenAPI document is pinned",
      "kind": "objective",
      "check": "file_hash",
      "weight": 10,
      "mandatory": false,
      "params": {
        "url": "https://api.example.com/openapi.json",
        "sha256": "9f2c000000000000000000000000000000000000000000000000000000000000"
      }
    },
    {
      "id": "C4",
      "title": "Documentation covers auth and errors",
      "kind": "objective",
      "check": "text_contains",
      "weight": 10,
      "mandatory": true,
      "params": {
        "url": "https://docs.example.com",
        "phrases": ["authentication", "rate limit", "error codes"],
        "case_sensitive": false
      }
    },
    {
      "id": "C5",
      "title": "Documentation quality",
      "kind": "subjective",
      "check": "llm_rubric",
      "weight": 40,
      "mandatory": true,
      "params": {
        "evidence_url": "https://docs.example.com",
        "rubric": "The documentation must explain authentication, rate limits, error codes, and include one end-to-end example. It must not invent endpoints that are absent from the evidence.",
        "threshold": 7,
        "max_chars": 20000
      }
    }
  ],
  "decision_policy": {
    "accept_threshold": 80,
    "partial_threshold": 50,
    "mandatory_must_pass": true,
    "missing_evidence": "UNDETERMINED",
    "partial_payout": "pro_rata",
    "score_rounding": "floor"
  },
  "evidence_policy": {
    "allowed_domains": ["api.example.com", "docs.example.com"],
    "require_https": true,
    "max_bytes_per_source": 2000000,
    "max_total_bytes": 10000000,
    "max_sources_per_criterion": 5,
    "allow_redirects": true,
    "max_redirects": 3
  },
  "metadata": {
    "buyer": "example-buyer",
    "seller": "example-agent",
    "created_for": "GenLayer builder demo"
  }
}
```

---

## 13. Example calls

### 13.1 Deploy (CLI)

```bash
genlayer network set studionet
genlayer deploy --contract contracts/Presense.py
```

The CLI prints the contract address. Presense has no constructor arguments.

### 13.2 Write and read methods

Current CLI `write` and `call` commands take `<contractAddress> <method>` and may prompt for arguments interactively. For complex arguments (arrays, JSON strings, attached value), use the TypeScript deploy script or GenLayerJS. The examples below use GenLayerJS because the argument shape is unambiguous.

### 13.3 Create (GenLayerJS)

```ts
const tx = await client.writeContract({
  address: presenseAddress,
  functionName: "create_agreement",
  args: [
    "agr_001",
    sellerAddress,
    manifestJson,
    "",
    BigInt(Math.floor(Date.now() / 1000) + 7 * 86400),
    BigInt(86400),
    "",
  ],
  value: 100n * 10n ** 18n,
});
```

### 13.4 Submit

```ts
await client.writeContract({
  address: presenseAddress,
  functionName: "submit_delivery",
  args: [
    "agr_001",
    ["https://api.example.com/health", "https://docs.example.com"],
    ["", ""],
    "Delivered API and docs.",
  ],
});
```

### 13.5 Evaluate

```ts
await client.writeContract({
  address: presenseAddress,
  functionName: "evaluate",
  args: ["agr_001"],
});
```

### 13.6 Read verdict

```ts
const verdict = await client.readContract({
  address: presenseAddress,
  functionName: "get_verdict",
  args: ["agr_001:verdict:1"],
});
```

---

## 14. Upgrade and migration

v1 is immutable. There is no proxy and no admin.

To ship v2:

1. Deploy a new `PresenseV2` contract.
2. Publish the new address and a migration note.
3. Keep v1 online until all agreements are settled or expired.
4. Do not route existing escrow through an admin key.

The frontend should read the contract address from configuration, not hardcode it.

---

## 15. Next document

Read [03 — Consensus Design](03-consensus-design.md) for the leader/validator logic, equivalence rules, and prompt design.
