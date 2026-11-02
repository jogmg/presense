# 10 — Glossary & References

**Project:** Presense
**Version:** 0.1
**Purpose:** Shared vocabulary and canonical links for builders, reviewers, and integrators.

---

## 1. Glossary

### Acceptance Manifest

A JSON document that defines the objective checks and subjective rubrics a delivery must satisfy. It is frozen on-chain before work begins. In Presense, the manifest is the contract. Also called the **Acceptance Test Manifest** in the original project concept.

### Agreement

The on-chain record binding buyer, seller, manifest, escrow, deadline, challenge window, and status.

### Appeal

A GenLayer protocol mechanism that escalates a transaction to a larger validator committee. Presense does not implement appeals; it inherits them.

### Bradbury

GenLayer’s production-like public testnet. Chain ID `4221`. Used for persistent, real-AI workloads.

### Challenge

A Presense-level request by the buyer or seller, within the challenge window, to submit counter-evidence and trigger re-evaluation. This is not a GenLayer protocol appeal.

### Challenge window

The period after a verdict during which either party can challenge. v1 range: 1 hour to 7 days.

### Claim

A withdrawable GEN balance credited by settlement, cancellation, or expiry. Claims are pulled by the recipient via `withdraw`.

### Consensus

The GenLayer process by which validators agree on the result of a transaction. Presense uses a custom equivalence rule inside this process.

### Deterministic

Code whose output depends only on its inputs and state. Presense’s payout math and state transitions are deterministic.

### Equivalence Principle

GenLayer’s rule that validators may accept non-identical outputs if they satisfy the contract’s validation criteria. Presense uses it for LLM judgments.

### Escrow

GEN held by the contract until a verdict or refund path releases it.

### Evidence

The artifacts, URLs, and text a seller submits to prove delivery. Evidence is public in v1.

### Evidence policy

The manifest section that restricts allowed domains, HTTPS, source size, and redirects.

### Evidence quote

An exact substring of the evidence that supports a subjective score. The validator verifies it in code.

### Finality

The point at which a GenLayer transaction is settled and cannot be reversed except through the protocol’s rules. Common-case finality is roughly 30 minutes; full escalation can take hours.

### Ghost contract

The EVM contract at an Intelligent Contract’s address. It holds the IC’s GEN balance and relays calls into the IC.

### GLSim

A lightweight local GenLayer simulator. Starts quickly, no Docker. Runs the Python runner natively, not inside GenVM.

### Greyboxing

A validator strategy where validators re-run the task with the same public inputs but without trusting the leader’s internal trace or curated summary.

### Intelligent Contract (IC)

A Python smart contract on GenLayer that can access the web, call LLMs, and make subjective decisions under validator consensus.

### Leader

The validator selected to propose the first result for a transaction.

### Manifest hash

`sha256(canonical_manifest_json)`. Stored on-chain and compared by validators.

### Non-deterministic block

A section of an Intelligent Contract that may produce different outputs across nodes, such as web fetches or LLM calls. Consensus is reached through the Equivalence Principle.

### Optimistic Democracy

GenLayer’s consensus model: a leader proposes, validators vote, and appeals escalate to larger committees.

### Partial

A verdict where the delivery meets some criteria but not enough for full acceptance. Payout is pro rata by score.

### Presense

The project in this repository. A portmanteau of **pre** + **sense**: the sense check before settlement.

### Pull payment

A settlement pattern where the contract credits a claim and the recipient withdraws. Presense uses this instead of automatic pushes.

### Reject

A verdict where the delivery fails mandatory criteria or falls below the partial threshold. The buyer is refunded.

### run_nondet_unsafe

The GenVM API used to run a non-deterministic block with a custom validator. Presense uses it to compare decision-critical fields instead of raw output.

### Schema-valid lie

A leader result that parses correctly but is false. Presense’s validator is designed to reject it.

### Settlement

The state transition that converts escrow into claims according to the verdict.

### strict_eq

A GenLayer equivalence helper that requires exact equality. It is unsuitable for raw LLM output and is not used for Presense’s subjective checks.

### Submission

The seller’s delivery record: artifact URLs, optional hashes, notes, timestamp, and submitter.

### Subjective criterion

A criterion that requires judgment, evaluated by an LLM against a rubric with a threshold and a required evidence quote.

### Objective criterion

A criterion that can be computed deterministically from fetched bytes, such as HTTP status, JSON keys, file hash, or text presence.

### UNDETERMINED

A verdict value meaning the evidence or consensus was insufficient for a reliable decision. Presense does not store an `UNDETERMINED` verdict; it raises an error so evaluation can be retried.

### Validator

A GenLayer node that independently checks the leader’s result.

### Verdict

The structured decision: `ACCEPT`, `PARTIAL`, `REJECT`, or `UNDETERMINED`, with per-criterion results and payout.

### Withdraw

The method that sends a claimant’s GEN. The caller declares `"evm"` or `"ic"` so the contract routes the transfer correctly.

---

## 2. Canonical GenLayer links

### Core

- [GenLayer](https://genlayer.com)
- [Documentation](https://docs.genlayer.com)
- [What is GenLayer?](https://docs.genlayer.com/understand-genlayer-protocol/what-is-genlayer)
- [How GenLayer works](https://docs.genlayer.com/understand-genlayer-protocol/optimistic-democracy-how-genlayer-works)
- [Use cases](https://docs.genlayer.com/understand-genlayer-protocol/typical-use-cases)
- [Core concepts](https://docs.genlayer.com/understand-genlayer-protocol/core-concepts)

### Build

- [Getting started](https://docs.genlayer.com/developers)
- [Intelligent Contracts introduction](https://docs.genlayer.com/developers/intelligent-contracts/introduction)
- [When to use GenLayer](https://docs.genlayer.com/developers/intelligent-contracts/when-to-use-genlayer)
- [Development setup](https://docs.genlayer.com/developers/intelligent-contracts/tooling-setup)
- [Your first contract](https://docs.genlayer.com/developers/intelligent-contracts/first-contract)
- [Testing](https://docs.genlayer.com/developers/intelligent-contracts/testing)
- [Deploying](https://docs.genlayer.com/developers/intelligent-contracts/deploying)
- [CLI deployment](https://docs.genlayer.com/developers/intelligent-contracts/deploying/cli-deployment)
- [Network configuration](https://docs.genlayer.com/developers/intelligent-contracts/deploying/network-configuration)
- [Deploy scripts](https://docs.genlayer.com/developers/intelligent-contracts/deploying/deploy-scripts)

### Features

- [Storage](https://docs.genlayer.com/developers/intelligent-contracts/features/storage)
- [Collections](https://docs.genlayer.com/developers/intelligent-contracts/types/collections)
- [Dataclasses](https://docs.genlayer.com/developers/intelligent-contracts/types/dataclasses)
- [Primitive types](https://docs.genlayer.com/developers/intelligent-contracts/types/primitive)
- [Value transfers](https://docs.genlayer.com/developers/intelligent-contracts/features/value-transfers)
- [Messages](https://docs.genlayer.com/developers/intelligent-contracts/features/messages)
- [Transaction context](https://docs.genlayer.com/developers/intelligent-contracts/features/transaction-context)
- [Error handling](https://docs.genlayer.com/developers/intelligent-contracts/features/error-handling)
- [Web access](https://docs.genlayer.com/developers/intelligent-contracts/features/web-access)
- [Calling LLMs](https://docs.genlayer.com/developers/intelligent-contracts/features/calling-llms)
- [Non-determinism](https://docs.genlayer.com/developers/intelligent-contracts/features/non-determinism)
- [Equivalence Principle](https://docs.genlayer.com/developers/intelligent-contracts/equivalence-principle)
- [Prompt injection](https://docs.genlayer.com/developers/intelligent-contracts/security-and-best-practices/prompt-injection)
- [Prompt & data techniques](https://docs.genlayer.com/developers/intelligent-contracts/crafting-prompts)
- [Upgradability](https://docs.genlayer.com/developers/intelligent-contracts/features/upgradability)

### Networks and tools

- [Networks](https://docs.genlayer.com/developers/networks)
- [GenLayer CLI](https://docs.genlayer.com/api-references/genlayer-cli)
- [GenLayerJS](https://docs.genlayer.com/api-references/genlayer-js)
- [GenLayerPY](https://docs.genlayer.com/api-references/genlayer-py)
- [GenLayer Testing Suite](https://docs.genlayer.com/api-references/genlayer-test)
- [Direct mode testing](https://docs.genlayer.com/api-references/genlayer-test/direct)
- [Integration testing](https://docs.genlayer.com/api-references/genlayer-test/integration)
- [glsim](https://docs.genlayer.com/api-references/genlayer-test/glsim)
- [genvm-linter](https://docs.genlayer.com/api-references/genlayer-linter)
- [GenLayer Node API](https://docs.genlayer.com/api-references/genlayer-node)

### Protocol

- [Optimistic Democracy](https://docs.genlayer.com/understand-genlayer-protocol/core-concepts/optimistic-democracy)
- [Equivalence Principle (protocol)](https://docs.genlayer.com/understand-genlayer-protocol/core-concepts/optimistic-democracy/equivalence-principle)
- [Appeals](https://docs.genlayer.com/understand-genlayer-protocol/core-concepts/optimistic-democracy/appeal-process)
- [Finality](https://docs.genlayer.com/understand-genlayer-protocol/core-concepts/optimistic-democracy/finality)
- [Validators and roles](https://docs.genlayer.com/understand-genlayer-protocol/core-concepts/validators-and-validator-roles)
- [Staking](https://docs.genlayer.com/understand-genlayer-protocol/core-concepts/optimistic-democracy/staking)
- [Slashing](https://docs.genlayer.com/understand-genlayer-protocol/core-concepts/optimistic-democracy/slashing)

### Networks

- [Bradbury explorer](https://scan.testnet-chain.genlayer.com/)
- [Bradbury faucet](https://testnet-faucet.genlayer.foundation)
- [Studionet](https://studio.genlayer.com)
- [Studio dev](https://studio-dev.genlayer.com)
- [Staking UI](https://stakegen.com/explore/)

### Ecosystem

- [GenLayer Foundation](https://genlayer.foundation)
- [GenLayer Labs](https://www.genlayerlabs.com/)
- [Builder portal](https://portal.genlayer.foundation)
- [GenLayer ecosystem](https://www.genlayer.com/ecosystem)
- [Internet Court](https://internetcourt.org)
- [Collective Memory (GitHub)](https://github.com/collective-memory-dev)
- [Rally](https://www.rally.fun/)

> Ecosystem links change. Verify before citing them in a submission.

---

## 3. Presense document index

| Document | Purpose |
|---|---|
| [README](../README.md) | Project overview and docs index. |
| [00 — Product Brief](00-product-brief.md) | Problem, users, scope, metrics. |
| [01 — Architecture](01-architecture.md) | System context, flows, state machine. |
| [02 — Contract Spec](02-contract-spec.md) | API, data model, manifest, payouts, errors. |
| [03 — Consensus Design](03-consensus-design.md) | Leader/validator logic and equivalence. |
| [04 — Security & Threat Model](04-security-threat-model.md) | Threats, mitigations, residual risks. |
| [05 — Testing Strategy](05-testing-strategy.md) | Test plan and adversarial cases. |
| [06 — Implementation Plan](06-implementation-plan.md) | Build phases and definition of done. |
| [07 — Deployment Runbook](07-deployment-runbook.md) | Localnet, Bradbury, deploy, verify. |
| [08 — Portal Submission](08-portal-submission.md) | Evidence and reviewer narrative. |
| [09 — Roadmap & Grants](09-roadmap-and-grants.md) | v1.1, v1.2, v2, funding. |
| [10 — Glossary & References](10-glossary-and-references.md) | This document. |

---

## 4. Version notes

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-11-02 | Initial spec pack. |

---

## 5. Maintenance

When the contract interface changes:

1. Update [02 — Contract Spec](02-contract-spec.md).
2. Update [03 — Consensus Design](03-consensus-design.md) if the equivalence rule changes.
3. Update [05 — Testing Strategy](05-testing-strategy.md) if a new path needs a test.
4. Update [07 — Deployment Runbook](07-deployment-runbook.md) if deployment changes.
5. Update [08 — Portal Submission](08-portal-submission.md) if the reviewer narrative changes.
6. Bump the version table above.

When a GenLayer API changes:

1. Re-check the canonical link.
2. Update the relevant section.
3. Re-run lint and tests.
4. Note the change in the version table.
