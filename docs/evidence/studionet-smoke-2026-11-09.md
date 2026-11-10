# Studionet smoke-test evidence — 2026-11-09

**Project:** Presense  
**Network:** Studionet (chain ID `61999`)  
**RPC:** `https://studio.genlayer.com/api`  
**Contract:** `0x1905d0Af801cc32D817Eed228b81902Dd1eB7DA9`  
**Explorer:** https://explorer-studio.genlayer.com/address/0x1905d0Af801cc32D817Eed228b81902Dd1eB7DA9  
**Deploy transaction:** [`0xdad3d744f8ae7c3cbd5314e58104aa22bcc00d36ef9b34f64fc9f5a8e81cc4c9`](https://explorer-studio.genlayer.com/tx/0xdad3d744f8ae7c3cbd5314e58104aa22bcc00d36ef9b34f64fc9f5a8e81cc4c9)  
**Deployer:** `0xF8645Cf1b5Df6ca64f4F3c632B9f779595A2cdA0`  
**Deployed:** 2026-11-09T02:37:04Z (finalized, GenVM result `SUCCESS`)  
**Buyer:** `0xa99A818C266De66225F33e6c8633DF524AC618C4`  
**Seller:** `0x4801Af1E73f86F76a893f6d6dc634bD693f93e3b`  
**Escrow:** `0.001 GEN` per agreement  
**Challenge window:** `3600` seconds  
**Manifests:** objective-only (`http_status` against `https://example.com/`)

Six agreements were driven end to end against the live Studionet deployment
with `genlayer-py 0.16.3`. Every transaction receipt reached `FINALIZED` with
leader `execution_result=SUCCESS`. No LLM provider was needed because every
criterion used the objective `http_status` check.

---

## 1. Result

| # | Scenario | Agreement | Decision | Score | Buyer payout (wei) | Seller payout (wei) | Final status |
|---|---|---|---:|---:|---:|---:|---|
| 1 | Accept | `smoke-accept-1794250643` | ACCEPT | 100 | `0` | `1000000000000000` | `SETTLED` |
| 2 | Partial | `smoke-partial-1794250825` | PARTIAL | 50 | `500000000000000` | `500000000000000` | `SETTLED` |
| 3 | Reject | `smoke-reject-1794251012` | REJECT | 0 | `1000000000000000` | `0` | `SETTLED` |
| 4 | Challenge | `smoke-challenge-1794251342` | ACCEPT | 100 | `0` | `1000000000000000` | `SETTLED` |
| 5 | Expiry | `smoke-expiry-1794251667` | refund | — | `1000000000000000` | `0` | `EXPIRED` |
| 6 | Cancellation | `smoke-cancel-clean-1794256622` | refund | — | `1000000000000000` | `0` | `CANCELLED` |

The accept, partial, reject, and challenge paths settled and paid through the
pull-payment claim ledger. The expiry and cancellation paths refunded the buyer
directly into the same claim ledger.

---

## 2. Accounting

### 2.1 Final balances

| Account | Final balance (wei) | Final balance (GEN) |
|---|---:|---:|
| Buyer | `96500000000000000` | `0.096500` |
| Seller | `2500000000000000` | `0.002500` |
| Contract | `1000000000000000` | `0.001000` |
| **Total** | **`100000000000000000`** | **`0.100000`** |

The buyer was funded with `0.1 GEN` before the run. Buyer, seller, and contract
balances sum exactly to the funded amount, so no value was created or destroyed.
The contract's `0.001 GEN` is explained in §5.1.

### 2.2 Contract escrow view

```json
{
  "balance": 1000000000000000,
  "total_locked": 0
}
```

`get_totals` reports the contract's native balance and the tracked locked
escrow. `total_locked` returned to `0` after the last settlement and refund,
which is the expected terminal accounting state.

### 2.3 Global claim ledger

`get_claim` is keyed by address, not by agreement. Claims therefore accumulate
across agreements until withdrawn. The snapshots below are the global claim
balances immediately before and after each withdrawal transaction.

| Withdrawal | Withdrawer | Buyer claim before | Seller claim before | Buyer claim after | Seller claim after |
|---|---|---:|---:|---:|---:|
| Accept `0x704566ae…43bb5` | seller | `1000000000000000` | `1000000000000000` | `1000000000000000` | `0` |
| Partial `0xbd20ae72…1959c6` | seller | `1500000000000000` | `500000000000000` | `1500000000000000` | `0` |
| Reject `0xfe7aa216…40496e9` | buyer | `2500000000000000` | `0` | `0` | `0` |
| Challenge `0x9c862f6c…5c5c12e` | seller | `0` | `1000000000000000` | `0` | `0` |
| Expiry `0x2f7c4b85…0d3bde0f` | buyer | `1000000000000000` | `0` | `0` | `0` |
| Cancellation `0x844231ad…5ef20057` | buyer | `1000000000000000` | `0` | `0` | `0` |

The buyer claim of `0.001 GEN` visible before the accept withdrawal is the
refund credited by the first cancellation during the init phase. It was
withdrawn together with the reject refund, which is why the reject withdrawal
cleared `0.0025 GEN`.

Per-agreement payouts are authoritative in each verdict's `payout_buyer` and
`payout_seller` fields, not in these cumulative snapshots.

---

## 3. Scenario detail

### 3.1 Accept

- Agreement: `smoke-accept-1794250643`
- Status path: `CREATED → ACTIVE → SUBMITTED → EVALUATED → SETTLED`
- Deadline: `1794337043` (`2026-11-10T18:57:23Z`)

| Step | Transaction | Result |
|---|---|---|
| create | [`0x8bec81e917db8c2696657bfd834aab0dfc073afcd6b3a99b3c0162d20f6345a9`](https://explorer-studio.genlayer.com/tx/0x8bec81e917db8c2696657bfd834aab0dfc073afcd6b3a99b3c0162d20f6345a9) | FINALIZED / SUCCESS |
| accept | [`0xc31364def111c2b7021d8a445f967b7705b988814df3e174954602ecef188272`](https://explorer-studio.genlayer.com/tx/0xc31364def111c2b7021d8a445f967b7705b988814df3e174954602ecef188272) | FINALIZED / SUCCESS |
| submit | [`0x5562e4b7a073f8ccc2b3eb886cd1e0d73113bec02cf73e649007cc8258f29519`](https://explorer-studio.genlayer.com/tx/0x5562e4b7a073f8ccc2b3eb886cd1e0d73113bec02cf73e649007cc8258f29519) | FINALIZED / SUCCESS |
| evaluate | [`0x82cfea12a504900269a02281b6e695f59280fb090d6c1a478891f84df6368405`](https://explorer-studio.genlayer.com/tx/0x82cfea12a504900269a02281b6e695f59280fb090d6c1a478891f84df6368405) | FINALIZED / SUCCESS |
| settle | [`0x4367407fea3b76f76ade46c4b6db42426973539a419ed5f1f11329fe46d76eb5`](https://explorer-studio.genlayer.com/tx/0x4367407fea3b76f76ade46c4b6db42426973539a419ed5f1f11329fe46d76eb5) | FINALIZED / SUCCESS |
| withdraw | [`0x704566ae578f39715e5cd5d4fd8de370bf5fb301d729209e21d1cee5a0c43bb5`](https://explorer-studio.genlayer.com/tx/0x704566ae578f39715e5cd5d4fd8de370bf5fb301d729209e21d1cee5a0c43bb5) | FINALIZED / SUCCESS |

```json
{
  "agreement_id": "smoke-accept-1794250643",
  "challenge_deadline": 1794254376,
  "decision": "ACCEPT",
  "evaluated_at": 1794250776,
  "evaluator": "0xa99A818C266De66225F33e6c8633DF524AC618C4",
  "id": "smoke-accept-1794250643:verdict:1",
  "manifest_hash": "f1ddf165bb52385281e22761b2d191dd54f2e0b145b93a67dbcb3fcb4ec04e9b",
  "payout_buyer": 0,
  "payout_seller": 1000000000000000,
  "results": [
    {
      "check": "http_status",
      "criterion_id": "C200",
      "evidence_quote": "",
      "evidence_url": "https://example.com/",
      "kind": "objective",
      "passed": true,
      "reason": "HTTP 200",
      "score": 10,
      "weight": 100
    }
  ],
  "schema": "presense.verdict.v1",
  "score": 100,
  "summary": "Decision=ACCEPT; score=100; 1 passed, 0 failed."
}
```

### 3.2 Partial

- Agreement: `smoke-partial-1794250825`
- Status path: `CREATED → ACTIVE → SUBMITTED → EVALUATED → SETTLED`
- Criteria: `C200` weight 50, `C404` weight 50; one passed, one failed.

| Step | Transaction | Result |
|---|---|---|
| create | [`0xdca5c2a6e27f7ff4c6ad95953d4c2324400ec336b0cd798296e4016450937e54`](https://explorer-studio.genlayer.com/tx/0xdca5c2a6e27f7ff4c6ad95953d4c2324400ec336b0cd798296e4016450937e54) | FINALIZED / SUCCESS |
| accept | [`0x1220bf5d360830d6d1c1693f151af1afb35f8be22ffcbfa4dae16a3788e53f5d`](https://explorer-studio.genlayer.com/tx/0x1220bf5d360830d6d1c1693f151af1afb35f8be22ffcbfa4dae16a3788e53f5d) | FINALIZED / SUCCESS |
| submit | [`0xb3e96f83a309c94e33191b6c01324c055c83d3dbd9e98eb085d7ecb461862541`](https://explorer-studio.genlayer.com/tx/0xb3e96f83a309c94e33191b6c01324c055c83d3dbd9e98eb085d7ecb461862541) | FINALIZED / SUCCESS |
| evaluate | [`0x71f0159766b3027960ffaf1600f8ffe0966acb8f9bfa1132e7d4f6702f52c380`](https://explorer-studio.genlayer.com/tx/0x71f0159766b3027960ffaf1600f8ffe0966acb8f9bfa1132e7d4f6702f52c380) | FINALIZED / SUCCESS |
| settle | [`0xd961affd5f6c750baaf26ad8ea15e5bb43d3858e51ef33234ef1aae2e9684623`](https://explorer-studio.genlayer.com/tx/0xd961affd5f6c750baaf26ad8ea15e5bb43d3858e51ef33234ef1aae2e9684623) | FINALIZED / SUCCESS |
| withdraw | [`0xbd20ae7210ab691f9b1be16ff456b66af7a8373cb00d7fc26e2224d1671959c6`](https://explorer-studio.genlayer.com/tx/0xbd20ae7210ab691f9b1be16ff456b66af7a8373cb00d7fc26e2224d1671959c6) | FINALIZED / SUCCESS |

```json
{
  "agreement_id": "smoke-partial-1794250825",
  "challenge_deadline": 1794254564,
  "decision": "PARTIAL",
  "evaluated_at": 1794250964,
  "evaluator": "0xa99A818C266De66225F33e6c8633DF524AC618C4",
  "id": "smoke-partial-1794250825:verdict:1",
  "manifest_hash": "ed44581bc7ad2966d53738b3bc391d5c12310014ad970b54e95b9dbbcc6f50d9",
  "payout_buyer": 500000000000000,
  "payout_seller": 500000000000000,
  "results": [
    {
      "check": "http_status",
      "criterion_id": "C200",
      "evidence_quote": "",
      "evidence_url": "https://example.com/",
      "kind": "objective",
      "passed": true,
      "reason": "HTTP 200",
      "score": 10,
      "weight": 50
    },
    {
      "check": "http_status",
      "criterion_id": "C404",
      "evidence_quote": "",
      "evidence_url": "https://example.com/",
      "kind": "objective",
      "passed": false,
      "reason": "HTTP 200",
      "score": 0,
      "weight": 50
    }
  ],
  "schema": "presense.verdict.v1",
  "score": 50,
  "summary": "Decision=PARTIAL; score=50; 1 passed, 1 failed."
}
```

### 3.3 Reject

- Agreement: `smoke-reject-1794251012`
- Status path: `CREATED → ACTIVE → SUBMITTED → EVALUATED → SETTLED`
- The mandatory `C404` criterion failed because `example.com` returned HTTP 200.

| Step | Transaction | Result |
|---|---|---|
| create | [`0xac04ff92e12e429820d65f52e6f287310ee4ff698da0d090073a891dfe7f473d`](https://explorer-studio.genlayer.com/tx/0xac04ff92e12e429820d65f52e6f287310ee4ff698da0d090073a891dfe7f473d) | FINALIZED / SUCCESS |
| accept | [`0x9eb7f26ff6f4eb5c0c6686ebd39cd88e0e38dde2ba58707efcd7344e7b6b5db0`](https://explorer-studio.genlayer.com/tx/0x9eb7f26ff6f4eb5c0c6686ebd39cd88e0e38dde2ba58707efcd7344e7b6b5db0) | FINALIZED / SUCCESS |
| submit | [`0xc7d1775eca9b8d86a5b3b598673bad7a04f04dcfa80e567bb87601d29f4d089c`](https://explorer-studio.genlayer.com/tx/0xc7d1775eca9b8d86a5b3b598673bad7a04f04dcfa80e567bb87601d29f4d089c) | FINALIZED / SUCCESS |
| evaluate | [`0xcddf8b7cd805533cab99fe304c378501f5a04259f7fbfbae4de47e2c0e4ddafb`](https://explorer-studio.genlayer.com/tx/0xcddf8b7cd805533cab99fe304c378501f5a04259f7fbfbae4de47e2c0e4ddafb) | FINALIZED / SUCCESS |
| settle | [`0x9857f6c8b2c85128280290491029a8cd6f9e29c389829be7de7b48651da5d1a2`](https://explorer-studio.genlayer.com/tx/0x9857f6c8b2c85128280290491029a8cd6f9e29c389829be7de7b48651da5d1a2) | FINALIZED / SUCCESS |
| withdraw | [`0xfe7aa216466fd9309b2e991569028c0aca7d9caacf47ce9be701a199d40496e9`](https://explorer-studio.genlayer.com/tx/0xfe7aa216466fd9309b2e991569028c0aca7d9caacf47ce9be701a199d40496e9) | FINALIZED / SUCCESS |

```json
{
  "agreement_id": "smoke-reject-1794251012",
  "challenge_deadline": 1794254755,
  "decision": "REJECT",
  "evaluated_at": 1794251155,
  "evaluator": "0xa99A818C266De66225F33e6c8633DF524AC618C4",
  "id": "smoke-reject-1794251012:verdict:1",
  "manifest_hash": "7a0c4fa8f1c39025667183eedcbafbd16a70aaa035d4debbe9f716c8cb899a33",
  "payout_buyer": 1000000000000000,
  "payout_seller": 0,
  "results": [
    {
      "check": "http_status",
      "criterion_id": "C404",
      "evidence_quote": "",
      "evidence_url": "https://example.com/",
      "kind": "objective",
      "passed": false,
      "reason": "HTTP 200",
      "score": 0,
      "weight": 100
    }
  ],
  "schema": "presense.verdict.v1",
  "score": 0,
  "summary": "Decision=REJECT; score=0; 0 passed, 1 failed."
}
```

### 3.4 Challenge

- Agreement: `smoke-challenge-1794251342`
- Status path: `CREATED → ACTIVE → SUBMITTED → EVALUATED → DISPUTED → EVALUATED → SETTLED`
- Verdict 1 and verdict 2 both decided `ACCEPT` with score 100; the re-evaluation
  ran with the challenge's counter-evidence attached.

| Step | Transaction | Result |
|---|---|---|
| create | [`0x62cf0a6fdd75ee7c7d6716539bdc7df1d43885e6380eae942af08c6c48d70050`](https://explorer-studio.genlayer.com/tx/0x62cf0a6fdd75ee7c7d6716539bdc7df1d43885e6380eae942af08c6c48d70050) | FINALIZED / SUCCESS |
| accept | [`0xea121e76b95fbbf836d997283cc1ee0ff7b8db7129b9a22320a9d29906d5e6f0`](https://explorer-studio.genlayer.com/tx/0xea121e76b95fbbf836d997283cc1ee0ff7b8db7129b9a22320a9d29906d5e6f0) | FINALIZED / SUCCESS |
| submit | [`0x9ec93f030af1bcf3a0b6794fd2fabeb31d5b77f9455cb714e9c4ae3a51aaaff4`](https://explorer-studio.genlayer.com/tx/0x9ec93f030af1bcf3a0b6794fd2fabeb31d5b77f9455cb714e9c4ae3a51aaaff4) | FINALIZED / SUCCESS |
| evaluate (verdict 1) | [`0x0cec85992b031bc937bd3941dc2b6830451c0121b0a7663b64930c157ea41e16`](https://explorer-studio.genlayer.com/tx/0x0cec85992b031bc937bd3941dc2b6830451c0121b0a7663b64930c157ea41e16) | FINALIZED / SUCCESS |
| challenge | [`0x39cf8b020bc72c1b7a6490d6b6607911f9c3e81b763b828860f951607143f058`](https://explorer-studio.genlayer.com/tx/0x39cf8b020bc72c1b7a6490d6b6607911f9c3e81b763b828860f951607143f058) | FINALIZED / SUCCESS |
| evaluate (verdict 2) | [`0x3d5cea7ba22c2ce8a421b6937d225edf78b44962cc1b7d26bccf3e57a28a227a`](https://explorer-studio.genlayer.com/tx/0x3d5cea7ba22c2ce8a421b6937d225edf78b44962cc1b7d26bccf3e57a28a227a) | FINALIZED / SUCCESS |
| settle | [`0x4fdd7e0165f764331336cd984972ed2a940b79d34979cd8e10d24303c1ecefef`](https://explorer-studio.genlayer.com/tx/0x4fdd7e0165f764331336cd984972ed2a940b79d34979cd8e10d24303c1ecefef) | FINALIZED / SUCCESS |
| withdraw | [`0x9c862f6c606d19e6d9acc53cbd03821d38dc4699bf3729d50c90482b82c5c12e`](https://explorer-studio.genlayer.com/tx/0x9c862f6c606d19e6d9acc53cbd03821d38dc4699bf3729d50c90482b82c5c12e) | FINALIZED / SUCCESS |

```json
{
  "agreement_id": "smoke-challenge-1794251342",
  "challenge_deadline": 1794255176,
  "decision": "ACCEPT",
  "evaluated_at": 1794251576,
  "evaluator": "0xa99A818C266De66225F33e6c8633DF524AC618C4",
  "id": "smoke-challenge-1794251342:verdict:2",
  "manifest_hash": "7d854a2f5eb10e2f73c7330a5ca247f200fd8d66ed0e24c57f9a9700b9750708",
  "payout_buyer": 0,
  "payout_seller": 1000000000000000,
  "results": [
    {
      "check": "http_status",
      "criterion_id": "C200",
      "evidence_quote": "",
      "evidence_url": "https://example.com/",
      "kind": "objective",
      "passed": true,
      "reason": "HTTP 200",
      "score": 10,
      "weight": 100
    }
  ],
  "schema": "presense.verdict.v1",
  "score": 100,
  "summary": "Decision=ACCEPT; score=100; 1 passed, 0 failed."
}
```

### 3.5 Expiry

- Agreement: `smoke-expiry-1794251667`
- Status path: `CREATED → ACTIVE → EXPIRED`
- Deadline: `1794255867`; the buyer called `claim_expired` after it passed.

| Step | Transaction | Result |
|---|---|---|
| create | [`0x5d3d736cfe2fe9a0c9f89884ce0baeb3226ce11e55dbda837102d5836d38b8cf`](https://explorer-studio.genlayer.com/tx/0x5d3d736cfe2fe9a0c9f89884ce0baeb3226ce11e55dbda837102d5836d38b8cf) | FINALIZED / SUCCESS |
| accept | [`0x463fb099de3a69cd8c4818d34b36776e3ebddddef114106bd3054165fbd026bf`](https://explorer-studio.genlayer.com/tx/0x463fb099de3a69cd8c4818d34b36776e3ebddddef114106bd3054165fbd026bf) | FINALIZED / SUCCESS |
| claim_expired | [`0xecdbf2fc8bf68f51d09b0da816e7d42401e019425a06808b464241e98bc313b8`](https://explorer-studio.genlayer.com/tx/0xecdbf2fc8bf68f51d09b0da816e7d42401e019425a06808b464241e98bc313b8) | FINALIZED / SUCCESS |
| withdraw | [`0x2f7c4b85c1bd53f82c6be0061821b778ea17fa158454f123d26dc51a0d3bde0f`](https://explorer-studio.genlayer.com/tx/0x2f7c4b85c1bd53f82c6be0061821b778ea17fa158454f123d26dc51a0d3bde0f) | FINALIZED / SUCCESS |

`claim_expired` credited the full `0.001 GEN` escrow to the buyer claim; the
withdraw transaction triggered a finalized native transfer of
`1000000000000000` wei from the contract to the buyer.

### 3.6 Cancellation

- Agreement: `smoke-cancel-clean-1794256622`
- Status path: `CREATED → CANCELLED`
- The seller never accepted, so the buyer could cancel and recover the escrow.

| Step | Transaction | Result |
|---|---|---|
| create | [`0x5a748a068e68da2a05f7d8e7dd8b3662134d697d00fcdd7a7bfb00d23036bea9`](https://explorer-studio.genlayer.com/tx/0x5a748a068e68da2a05f7d8e7dd8b3662134d697d00fcdd7a7bfb00d23036bea9) | FINALIZED / SUCCESS |
| cancel_agreement | [`0x0616a1a82d77057761c734125755a9ea712a4ce5b592902f3df3c2c4219abc39`](https://explorer-studio.genlayer.com/tx/0x0616a1a82d77057761c734125755a9ea712a4ce5b592902f3df3c2c4219abc39) | FINALIZED / SUCCESS |
| withdraw | [`0x844231addfd3c410d0c7fc83a7c10e480f655f8c3fb60ca196be35745ef20057`](https://explorer-studio.genlayer.com/tx/0x844231addfd3c410d0c7fc83a7c10e480f655f8c3fb60ca196be35745ef20057) | FINALIZED / SUCCESS |

The cancel credited `0.001 GEN` to the buyer claim and the withdraw transferred
it. The child send transaction
`0x85fdf22ffd26ba4201802e2c24f6f25615b5f332ad3b74c812d52f7ef566b133` is
`FINALIZED` with `value_credited: true`, sender `0x1905…7DA9`, recipient
`0xa99A…18C4`, value `1000000000000000` wei.

---

## 4. Transaction inventory

Every call below is a contract call unless marked as a send.

| Scenario | Call | Hash |
|---|---|---|
| Deploy | constructor | `0xdad3d744f8ae7c3cbd5314e58104aa22bcc00d36ef9b34f64fc9f5a8e81cc4c9` |
| Accept | create | `0x8bec81e917db8c2696657bfd834aab0dfc073afcd6b3a99b3c0162d20f6345a9` |
| Accept | accept | `0xc31364def111c2b7021d8a445f967b7705b988814df3e174954602ecef188272` |
| Accept | submit | `0x5562e4b7a073f8ccc2b3eb886cd1e0d73113bec02cf73e649007cc8258f29519` |
| Accept | evaluate | `0x82cfea12a504900269a02281b6e695f59280fb090d6c1a478891f84df6368405` |
| Accept | settle | `0x4367407fea3b76f76ade46c4b6db42426973539a419ed5f1f11329fe46d76eb5` |
| Accept | withdraw | `0x704566ae578f39715e5cd5d4fd8de370bf5fb301d729209e21d1cee5a0c43bb5` |
| Partial | create | `0xdca5c2a6e27f7ff4c6ad95953d4c2324400ec336b0cd798296e4016450937e54` |
| Partial | accept | `0x1220bf5d360830d6d1c1693f151af1afb35f8be22ffcbfa4dae16a3788e53f5d` |
| Partial | submit | `0xb3e96f83a309c94e33191b6c01324c055c83d3dbd9e98eb085d7ecb461862541` |
| Partial | evaluate | `0x71f0159766b3027960ffaf1600f8ffe0966acb8f9bfa1132e7d4f6702f52c380` |
| Partial | settle | `0xd961affd5f6c750baaf26ad8ea15e5bb43d3858e51ef33234ef1aae2e9684623` |
| Partial | withdraw | `0xbd20ae7210ab691f9b1be16ff456b66af7a8373cb00d7fc26e2224d1671959c6` |
| Reject | create | `0xac04ff92e12e429820d65f52e6f287310ee4ff698da0d090073a891dfe7f473d` |
| Reject | accept | `0x9eb7f26ff6f4eb5c0c6686ebd39cd88e0e38dde2ba58707efcd7344e7b6b5db0` |
| Reject | submit | `0xc7d1775eca9b8d86a5b3b598673bad7a04f04dcfa80e567bb87601d29f4d089c` |
| Reject | evaluate | `0xcddf8b7cd805533cab99fe304c378501f5a04259f7fbfbae4de47e2c0e4ddafb` |
| Reject | settle | `0x9857f6c8b2c85128280290491029a8cd6f9e29c389829be7de7b48651da5d1a2` |
| Reject | withdraw | `0xfe7aa216466fd9309b2e991569028c0aca7d9caacf47ce9be701a199d40496e9` |
| Challenge | create | `0x62cf0a6fdd75ee7c7d6716539bdc7df1d43885e6380eae942af08c6c48d70050` |
| Challenge | accept | `0xea121e76b95fbbf836d997283cc1ee0ff7b8db7129b9a22320a9d29906d5e6f0` |
| Challenge | submit | `0x9ec93f030af1bcf3a0b6794fd2fabeb31d5b77f9455cb714e9c4ae3a51aaaff4` |
| Challenge | evaluate 1 | `0x0cec85992b031bc937bd3941dc2b6830451c0121b0a7663b64930c157ea41e16` |
| Challenge | challenge | `0x39cf8b020bc72c1b7a6490d6b6607911f9c3e81b763b828860f951607143f058` |
| Challenge | evaluate 2 | `0x3d5cea7ba22c2ce8a421b6937d225edf78b44962cc1b7d26bccf3e57a28a227a` |
| Challenge | settle | `0x4fdd7e0165f764331336cd984972ed2a940b79d34979cd8e10d24303c1ecefef` |
| Challenge | withdraw | `0x9c862f6c606d19e6d9acc53cbd03821d38dc4699bf3729d50c90482b82c5c12e` |
| Expiry | create | `0x5d3d736cfe2fe9a0c9f89884ce0baeb3226ce11e55dbda837102d5836d38b8cf` |
| Expiry | accept | `0x463fb099de3a69cd8c4818d34b36776e3ebddddef114106bd3054165fbd026bf` |
| Expiry | claim_expired | `0xecdbf2fc8bf68f51d09b0da816e7d42401e019425a06808b464241e98bc313b8` |
| Expiry | withdraw | `0x2f7c4b85c1bd53f82c6be0061821b778ea17fa158454f123d26dc51a0d3bde0f` |
| Cancellation | create | `0x5a748a068e68da2a05f7d8e7dd8b3662134d697d00fcdd7a7bfb00d23036bea9` |
| Cancellation | cancel | `0x0616a1a82d77057761c734125755a9ea712a4ce5b592902f3df3c2c4219abc39` |
| Cancellation | withdraw | `0x844231addfd3c410d0c7fc83a7c10e480f655f8c3fb60ca196be35745ef20057` |
| Cancellation | transfer (send) | `0x85fdf22ffd26ba4201802e2c24f6f25615b5f332ad3b74c812d52f7ef566b133` |

---

## 5. Observed caveats

### 5.1 A failed payable call retained its attached value

The first expiry `create_agreement` used a deadline computed at process start.
Earlier transactions consumed the one-hour margin, so the call failed the
`MIN_DEADLINE_SECONDS` check with `E_DEADLINE_INVALID`:

- Transaction: [`0x0d53d9650b61ad827f8a30a7ef720615108b156039442e0d13f5780a21fcf2b5`](https://explorer-studio.genlayer.com/tx/0x0d53d9650b61ad827f8a30a7ef720615108b156039442e0d13f5780a21fcf2b5)
- Status: `FINALIZED`
- Leader `execution_result`: `ERROR`
- Attached value: `1000000000000000` wei
- Triggered transactions: none

The attached `0.001 GEN` stayed in the contract. v1 has no rescue or sweep
function, and no refund was emitted for the failed call. This is why the final
contract balance is `0.001 GEN` while `total_locked` is `0`. The contract's
tracked escrow and claims are correct; the extra balance is unattributed
native value. A future version should either reject payable calls before
value transfer where the platform allows it, or add an explicit rescue path
with a clear policy.

The retry used a deadline computed at creation time (`now + 4200` seconds) and
succeeded.

### 5.2 Claims are global per address

`get_claim` is keyed only by address. A claim accumulates credits from every
agreement that pays that address until it withdraws. This is intentional
pull-payment accounting, but it means claim snapshots are not per-agreement.
Use the verdict's `payout_buyer` and `payout_seller` for per-agreement amounts.

### 5.3 The first cancellation withdrawal was redundant

The first cancellation credited the buyer during the init phase. Its refund was
then withdrawn as part of the reject settlement, which cleared the buyer claim.
A later `withdraw` for the cancellation therefore hit `E_CLAIM_ZERO`:

- Transaction: [`0x8a841092dea90a12942ba01462a528bc9adb918a42b7aed334ca7352591bde27`](https://explorer-studio.genlayer.com/tx/0x8a841092dea90a12942ba01462a528bc9adb918a42b7aed334ca7352591bde27)
- Result: `ERROR` (`E_CLAIM_ZERO`)

This was a test-harness sequencing issue, not a contract defect: withdrawing a
zero claim is correctly rejected. Section 3.6 is the clean cancellation rerun
with its own create, cancel, and withdraw transactions. The smoke runner now
checks the claim balance before withdrawing.

### 5.4 Studionet enforces real time

Studionet rejects `sim_increaseTime` and `sim_getTime` (`Method not found`), so
the one-hour challenge windows and the expiry deadline were bridged with real
waits. The finalize phase started after the latest window closed. This makes
the run slow but exercises the real clock path rather than a simulator.

### 5.5 Objective-only manifests

This live run used `http_status` criteria only. It proves the deployment,
manifest flow, evidence fetch, objective checks, consensus path, verdict
storage, settlement, challenge re-evaluation, expiry, cancellation, and
withdrawal on the live network. It does not exercise a live `llm_rubric` call
against a provider. The subjective path, the teleological prompt, quote
verification, and the schema-valid-lie rejection are covered by the direct-mode
suite in `tests/direct/test_checks_subjective.py`,
`tests/direct/test_validator.py`, and `tests/direct/test_settlement.py`.

### 5.6 Not covered here

- Full GenVM localnet (glsim is the current integration target).
- Bradbury deployment and smoke test (deferred).
- External peer review (pending).

---

## 6. Reproduction

The committed runner reproduces this shape of run:

```bash
# 1. Put buyer/seller credentials outside version control.
#    .presense-smoke/ is gitignored.
#
#    .presense-smoke/credentials.json
#    {
#      "buyer":  {"name": "my-buyer",  "password": "..."},
#      "seller": {"name": "my-seller", "password": "..."}
#    }

# 2. Create and evaluate the agreements.
python scripts/studionet_smoke.py --phase init

# 3. After the challenge windows and the expiry deadline, settle and withdraw.
python scripts/studionet_smoke.py --phase finalize

# 4. Print the summary table from the saved state.
python scripts/studionet_smoke.py --phase summary
```

The runner defaults to the Studionet deployment and `0.001 GEN` escrow. It
stores transaction hashes, verdicts, claims, and errors in
`.presense-smoke/state.json` and appends events to `.presense-smoke/state.log.jsonl`.

This evidence file was produced from a run whose state lived outside the repo;
the transaction hashes above are the durable record.
