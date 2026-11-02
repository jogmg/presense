# 08 — Portal Submission

**Project:** Presense
**Category:** Intelligent Contracts (portal type `52`)
**Version:** 0.1
**Purpose:** Package the work so a reviewer can verify it quickly and see why it is a real consensus primitive, not a demo.

> **Verify the live rules before submitting.** The portal changes. The figures below were observed on 2026-11-02 and should be re-checked on the contribution page (`?type=52`).

---

## 1. Category snapshot (observed 2026-11-02)

| Item | Value |
|---|---|
| Category | Intelligent Contracts |
| Type ID | `52` |
| Max points | 10 |
| Multiplier | 50× |
| Submission limit | 2 per week |
| Total submissions at observation | 2,160 |
| Review | AI review + standard review |
| Required evidence | `(Studio contract OR GitHub repo) AND deployed explorer contract` |

### What the category rejects

- Basic examples and hello-world contracts.
- Simple storage contracts.
- Thin LLM wrappers.
- Format-only validators.
- Boilerplate forks.
- Generic “AI decides X” demos.

### What the category rewards

- Real consensus logic.
- A clear reason the contract needs GenLayer.
- Independent validator verification.
- Evidence handling.
- A reusable primitive.
- A deployed contract with observable behavior.
- Tests that prove the hard cases.

---

## 2. Positioning for reviewers

### One-liner

**Presense is a reusable GenLayer primitive for adjudicating whether agent-delivered work met an agreed acceptance manifest, then settling escrow according to a structured, independently verified verdict.**

### Short description

> Agent commerce has payments, identity, and messaging, but no neutral acceptance layer. Presense fixes that. A buyer and seller freeze a machine-readable Acceptance Manifest before work begins. The seller submits evidence. GenLayer validators independently evaluate objective checks and subjective rubrics, verify evidence quotes, and produce a structured verdict: ACCEPT, PARTIAL, REJECT, or UNDETERMINED. Escrow is released, split, or refunded accordingly. Presense is not a generic AI judge; it is an evidence-first acceptance primitive that other agent marketplaces can integrate.

### Why it needs GenLayer

> The core question — “does this delivery satisfy the agreed rubric?” — is subjective and evidence-based. A normal smart contract cannot fetch the evidence, interpret a rubric, or tolerate model variance. Presense uses GenLayer’s non-deterministic execution and Equivalence Principle: the leader proposes a verdict, validators independently re-fetch evidence and re-evaluate, and the contract compares only decision-critical fields. Deterministic checks run before any LLM call, and every subjective score must cite a quote that the validator verifies in code.

### What is novel

1. **Acceptance Manifest as a frozen artifact.** The standard is agreed before the dispute and stored on-chain, not fetched from a mutable URL.
2. **Objective/subjective split.** Deterministic checks carry the load; the LLM is used only where judgment is unavoidable.
3. **Evidence-quote verification.** A model cannot cite a sentence that is not in the evidence.
4. **Decision-field equivalence.** Validators compare `passed`, `decision`, score tolerance, and quote validity, not raw text.
5. **Pull-payment settlement.** Claims and explicit `evm`/`ic` withdrawal avoid payout routing guesses.
6. **Reusable primitive.** Other marketplaces can integrate the manifest schema and contract instead of building adjudication.

---

## 3. Evidence checklist

The portal requires both a code artifact and a deployed contract. Prepare all of the following.

### 3.1 Code artifact

- [ ] Public GitHub repository.
- [ ] `README.md` with:
  - project summary,
  - problem,
  - architecture diagram,
  - contract address,
  - test commands,
  - consensus explanation,
  - limitations.
- [ ] `contracts/Presense.py`.
- [ ] `tests/direct/` with the adversarial tests.
- [ ] `tests/integration/` with localnet/Bradbury tests.
- [ ] `docs/` with this spec pack.
- [ ] `examples/manifest.weather-api.json`.
- [ ] `LICENSE`.
- [ ] No secrets, private keys, or `.env` files.

### 3.2 Deployed contract

- [ ] Bradbury contract address.
- [ ] Explorer link: `https://scan.testnet-chain.genlayer.com/address/<address>`.
- [ ] Deploy transaction hash.
- [ ] At least one create transaction.
- [ ] At least one accept transaction.
- [ ] At least one submit transaction.
- [ ] At least one evaluate transaction.
- [ ] At least one settle transaction.
- [ ] At least one withdraw transaction.
- [ ] Verdict JSON.

### 3.3 Consensus evidence

- [ ] Explanation of the leader/validator split.
- [ ] The equivalence table (which fields are compared).
- [ ] The evidence-quote verification rule.
- [ ] A test showing a schema-valid lie is rejected.
- [ ] A test showing prompt injection does not produce a false ACCEPT.
- [ ] The `UNDETERMINED` policy.

### 3.4 Test evidence

- [ ] `pytest tests/direct/ -v` output.
- [ ] Coverage summary.
- [ ] Localnet integration output.
- [ ] Bradbury smoke test summary.
- [ ] Any known failures and their status.

### 3.5 Demo evidence

- [ ] A sample manifest.
- [ ] A sample verdict.
- [ ] A short screen recording or screenshots of the Studio flow.
- [ ] A sequence diagram.
- [ ] A “what happens on a bad delivery” example.

---

## 4. Suggested submission fields

### Title

Choose one:

- **Presense — Acceptance Adjudication for Agent Work**
- **Presense — The Sense Check Before Settlement**
- **Presense — A Reusable Acceptance Manifest Primitive**

Recommended: **Presense — Acceptance Adjudication for Agent Work**.

### Category

Intelligent Contracts (`52`).

### Short summary (≈100 words)

> Presense is a GenLayer primitive that decides whether agent-delivered work met an agreed acceptance manifest, then settles escrow. Buyers and sellers freeze objective checks and subjective rubrics on-chain. Sellers submit evidence. Validators independently re-fetch evidence, run deterministic checks, evaluate LLM rubrics, and verify evidence quotes. The contract compares decision-critical fields and produces ACCEPT, PARTIAL, REJECT, or UNDETERMINED. Settlement uses pull-payment claims. Presense is built for agent marketplaces, freelance escrow, grant milestones, and bounty platforms that need neutral acceptance without a centralized judge.

### Long description template

```markdown
## Problem

Agent commerce has payments (x402), identity (ERC-8004), and messaging (A2A), but no neutral acceptance layer. When an agent delivers work, the buyer and seller need an answer to one question: did the delivery satisfy the agreement? Today the answer comes from a centralized platform, a single LLM prompt, or a human court.

## Solution

Presense makes acceptance a first-class primitive. Before work begins, the buyer and seller freeze an Acceptance Manifest on-chain. The manifest contains:

- objective checks (HTTP status, JSON keys, file hash, text phrases),
- subjective rubrics with thresholds,
- an evidence policy (allowed domains, size caps),
- a decision policy (accept/partial/reject thresholds),
- payout rules.

After the seller submits evidence, GenLayer validators evaluate it. The leader proposes a verdict. Validators independently re-fetch the evidence and re-evaluate. The contract compares decision-critical fields, verifies evidence quotes in code, and stores the accepted verdict. Escrow is released, split, or refunded.

## Why GenLayer

The acceptance question is subjective and evidence-based. A normal smart contract cannot fetch web evidence or interpret a rubric. A single LLM is not a consensus. Presense uses GenLayer's non-deterministic execution and Equivalence Principle to turn a single-model judgment into an independently verified, bounded decision.

## What is novel

- The manifest is stored on-chain, not fetched from a mutable URL.
- Deterministic checks run before any LLM call.
- Every subjective score must cite an exact quote from the evidence.
- Validators compare decision fields, not raw model text.
- Missing evidence produces UNDETERMINED, not a guessed verdict.
- Settlement uses pull-payment claims with explicit EVM/IC withdrawal.

## Status

- Contract: deployed on Bradbury at 0x...
- Tests: direct-mode suite passing; adversarial leader and prompt-injection tests passing.
- Docs: full spec pack in the repo.
- Limitations: one buyer/seller, one escrow, one challenge, public evidence only.

## Links

- Repo: ...
- Explorer: ...
- Demo manifest: ...
- Demo verdict: ...
```

---

## 5. Reviewer questions to answer in advance

### “Is this just an LLM wrapper?”

No. The contract has:

- a frozen manifest schema,
- deterministic objective checks,
- a leader/validator equivalence rule,
- evidence-quote verification in code,
- a structured verdict,
- escrow accounting,
- a challenge window,
- pull-payment settlement.

The LLM is used only for subjective criteria. The consensus design is the product.

### “Why can’t the leader lie?”

The validator re-fetches evidence and re-runs every check. It compares objective pass/fail exactly, subjective pass/fail exactly, score within a bounded tolerance, and verifies that the evidence quote exists in the fetched text. A schema-valid lie fails.

### “What happens if the evidence is down?”

The manifest’s `missing_evidence` policy applies. It can produce `UNDETERMINED`, which stores no verdict and allows a retry. It does not silently pass or fail without evidence.

### “What if validators disagree?”

The transaction retries with a new leader committee. If disagreement persists, evaluation returns `UNDETERMINED`. The agreement remains in `SUBMITTED` or `DISPUTED`.

### “Is there an admin?”

No. No admin key, no pause, no upgrade proxy. v1 is immutable.

### “How is this different from Internet Court?”

Internet Court is a broader agent-to-agent contract and dispute standard. Presense is an acceptance primitive that those agents can call. It is complementary, not a competitor.

### “How is this different from a prediction market?”

A prediction market resolves an external event. Presense adjudicates whether a delivery met an agreed acceptance manifest. The evidence and payout logic are different.

### “What is the business model?”

The primitive is open source. Integrators can pay per evaluation, white-label the frontend, or use it as a settlement backend. v1 focuses on correctness and reuse, not monetization.

---

## 6. Do and don’t

### Do

- Lead with the consensus design.
- Show the adversarial test.
- Show the manifest and verdict.
- Link the deployed contract.
- State the limitations honestly.
- Use “acceptance adjudication,” not “AI judge.”
- Explain why the manifest is on-chain.
- Include the test commands.

### Don’t

- Claim it replaces courts.
- Claim perfect truth.
- Claim it is fully decentralized if it depends on a single frontend.
- Submit a hello-world or a thin wrapper.
- Hide the LLM dependency.
- Overstate test coverage.
- Use screenshots without explorer links.
- Submit before the Bradbury smoke test passes.

---

## 7. Submission steps

1. **Finalize the repo**
   - README complete.
   - Docs linked.
   - Tests passing.
   - License added.
   - No secrets.

2. **Finalize the deployment**
   - Bradbury address confirmed.
   - Explorer source verified.
   - Smoke test transactions saved.

3. **Prepare the evidence pack**
   - Create a `submission/` folder or a gist with:
     - contract address,
     - transaction hashes,
     - verdict JSON,
     - test output,
     - screenshots.

4. **Open the portal**
   - Go to the builder contributions page.
   - Select type `52` (Intelligent Contracts).
   - Re-check the current points, multiplier, and weekly limit.

5. **Fill the form**
   - Title.
   - Short summary.
   - Long description.
   - GitHub repo URL.
   - Studio contract URL or deployed contract address.
   - Explorer URL.
   - Test evidence.
   - Limitations.

6. **Submit**
   - Confirm the evidence links are public.
   - Confirm the contract address is correct.
   - Submit.

7. **Respond to review**
   - Answer AI/standard review questions with links, not claims.
   - Fix issues in the repo and redeploy if needed.
   - Keep the deployed address stable during review.

---

## 8. Post-submission

- Monitor the review status.
- Keep the Bradbury contract online.
- Do not change the repo in a way that invalidates the evidence.
- If you deploy a v2, publish the new address and keep v1 online.
- Save the submission ID and reviewer feedback.
- Use the feedback to improve the next contribution.

---

## 9. Re-check before submitting

- [ ] Category rules still match this document.
- [ ] Required evidence is still `(Studio OR repo) AND deployed explorer contract`.
- [ ] The contract address is on Bradbury, not a localnet.
- [ ] The explorer link resolves.
- [ ] The repo is public.
- [ ] The README explains the consensus design.
- [ ] The adversarial test is visible.
- [ ] The prompt-injection test is visible.
- [ ] The verdict JSON is included.
- [ ] The limitations are stated.
- [ ] No secrets are in the repo.
- [ ] The submission is within the weekly limit.

---

## 10. Next document

Read [09 — Roadmap & Grants](09-roadmap-and-grants.md) for what to build after v1.
