# 09 — Roadmap & Grants

**Project:** Presense
**Version:** 0.1
**Purpose:** Define what to build after v1, how to integrate with the ecosystem, and how to fund the work without diluting the primitive.

---

## 1. Thesis

Presense should follow a **primitive → integration → product** path.

1. **Primitive:** a correct, reusable acceptance contract with a clear manifest schema.
2. **Integration:** SDKs, manifest linter, and adapters for agent marketplaces and escrow flows.
3. **Product:** a hosted “delivery court” experience for buyers, sellers, and marketplaces.

Do not start with the product. A frontend over a weak primitive is a demo. A strong primitive with a clear integration path is infrastructure.

---

## 2. Version map

| Version | Theme | Key additions | Success signal |
|---|---|---|---|
| **v1.0** | Correct primitive | Manifest, objective/subjective checks, validator, escrow, claims, one challenge. | Full lifecycle on Bradbury; adversarial tests pass; portal accepted. |
| **v1.1** | Economic hardening | Challenge bonds, slashing to counterparty, evaluation attempts, manifest linter. | Challenges are economically bounded; no spam griefing. |
| **v1.2** | Integrator kit | TypeScript SDK, React hooks, webhook/indexer, manifest generator, templates. | One external marketplace integrates. |
| **v2.0** | Multi-party and private evidence | Milestones, multi-party agreements, commit/reveal evidence, ERC-20 escrow, reputation hooks. | Production pilot with a marketplace or grant program. |
| **v2.x** | Cross-ecosystem | x402/ERC-8004/A2A adapters, cross-chain settlement, appeal routing. | Agent-to-agent commerce integration. |

---

## 3. v1.1 — Economic hardening

### Features

1. **Challenge bond**
   - Challenger stakes a bond.
   - If the challenge changes the payout in the challenger’s favor beyond a threshold, the bond is returned.
   - If not, the bond is paid to the opposing party.
   - This prices frivolous challenges.

2. **Evaluation attempts**
   - Track `evaluation_attempts`.
   - After N `UNDETERMINED` results, allow a fallback policy:
     - refund,
     - split,
     - extend the deadline.
   - The fallback must be agreed in the manifest, not chosen by an admin.

3. **Manifest linter**
   - Off-chain CLI that validates a manifest before it is funded.
   - Checks ambiguity, missing objective checks, overlapping criteria, unreachable URLs, and weight balance.
   - Outputs a human-readable report.

4. **Better challenge evidence**
   - Multiple counter-evidence URLs.
   - Per-criterion counter-evidence, not just global.
   - A reason field tied to criterion IDs.

### Why

v1 has one challenge and no bond. That is enough for correctness but not for adversarial scale. v1.1 makes the challenge credible.

### Definition of done

- Challenge bond accounting is conserved.
- A failed challenge pays the bond to the counterparty.
- A successful challenge returns the bond.
- No new admin key.
- Tests cover bond edge cases.

---

## 4. v1.2 — Integrator kit

### Features

1. **TypeScript SDK**
   - `createAgreement`
   - `acceptAgreement`
   - `submitDelivery`
   - `evaluate`
   - `challenge`
   - `settle`
   - `withdraw`
   - `getAgreement`, `getVerdict`, `getClaim`
   - Manifest builder and validator.

2. **React hooks**
   - `useAgreement(id)`
   - `useVerdict(id)`
   - `useClaim(address)`
   - `useCreateAgreement()`

3. **Indexer / webhook**
   - Watch `AgreementCreated`, `DeliverySubmitted`, `VerdictStored`, `Settled`, `Withdrawn`.
   - Send webhooks to marketplaces.
   - Note: if GenLayer events are not available for a given field, poll the view methods.

4. **Manifest templates**
   - API delivery.
   - Documentation delivery.
   - Dataset delivery.
   - Code repository delivery.
   - Content/article delivery.
   - Grant milestone.

5. **Manifest generator**
   - CLI/interactive prompt that turns a plain-English brief into a draft manifest.
   - Always requires human review before funding.

### Why

A primitive is only reusable if integration is cheap. The SDK and templates reduce the time from “I have a delivery dispute” to “I have a funded agreement.”

### Definition of done

- One external builder completes a test integration.
- SDK covers the full lifecycle.
- Templates pass the linter.
- Docs include a 10-minute quickstart.

---

## 5. v2.0 — Multi-party and private evidence

### Features

1. **Milestones**
   - Multiple tranches per agreement.
   - Each tranche has its own manifest, deadline, and payout.
   - The agreement settles per milestone.

2. **Multi-party agreements**
   - Buyer, seller, and optional guarantor/arbiter.
   - Quorum rules for acceptance.
   - Split payouts.

3. **Private evidence**
   - Commit/reveal: seller commits a hash before delivery, reveals later.
   - Encrypted evidence with validator-only access (requires protocol support).
   - Zero-knowledge proofs for specific checks (long-term).

4. **ERC-20 escrow**
   - Accept standard tokens, not only GEN.
   - Per-token accounting.
   - Price volatility is out of scope.

5. **Reputation hooks**
   - Write acceptance outcomes to an ERC-8004-compatible reputation registry.
   - Opt-in only.
   - Do not make reputation transferable or soulbound without design review.

6. **Appeal routing**
   - Integrate with Internet Court or a similar dispute standard for post-verdict escalation.
   - Presense remains the acceptance layer; escalation is a separate contract.

### Why

Real marketplaces have milestones, multiple parties, and private artifacts. v2 turns Presense from a single-delivery primitive into a settlement layer.

### Definition of done

- A milestone agreement completes end to end.
- A multi-party agreement completes end to end.
- Private evidence is either supported or explicitly out of scope with a migration path.
- No admin key is introduced.

---

## 6. Ecosystem integrations

### 6.1 Internet Court

Internet Court is a broader agent-to-agent contract and dispute standard. Presense can be the acceptance primitive that Internet Court-compatible agents call when they need a structured delivery decision.

**Integration idea:**

- Internet Court agreement references a Presense manifest hash.
- On delivery, the court calls Presense or reads its verdict.
- If the verdict is `UNDETERMINED`, the court handles escalation.

**Status:** research conversation.

### 6.2 Collective Memory

Collective Memory is a platform where humans hire autonomous AI agents for digital tasks; it uses GenLayer as a quality-assurance layer before releasing escrowed funds. Presense can verify delivery against a structured manifest before settlement.

**Integration idea:**

- Marketplace creates a Presense agreement per task.
- Seller submits the deliverable.
- Presense verdict triggers marketplace payout.
- Marketplace displays the verdict and evidence.

**Status:** integration target.

### 6.3 x402

x402 handles payment. Presense handles the condition for release.

**Integration idea:**

- x402 payment is escrowed or conditionally released on a Presense verdict.
- The payment reference includes the agreement ID.
- The marketplace listens for `SETTLED`.

**Status:** conceptual.

### 6.4 ERC-8004

ERC-8004 provides agent identity. Presense provides delivery history.

**Integration idea:**

- Agent’s profile links to its Presense agreements.
- Reputation includes acceptance rate, dispute rate, and average score.
- Opt-in and privacy-preserving.

**Status:** conceptual.

### 6.5 A2A

A2A provides agent discovery and task exchange. Presense provides the acceptance contract for a task.

**Integration idea:**

- A2A task includes a Presense manifest URL/hash.
- The seller accepts the manifest before starting.
- The buyer uses Presense to settle.

**Status:** conceptual.

### 6.6 Grant programs and bounties

Grant programs need milestone acceptance against a rubric. Presense can adjudicate:

- milestone deliverables,
- bounty submissions,
- documentation quality,
- dataset completeness,
- code repository requirements.

**Status:** near-term pilot.

---

## 7. Grant fit

### 7.1 GenLayer Foundation grants

Presense fits the foundation’s interest in:

- AI-powered applications with real consensus logic,
- developer tools and primitives,
- testnet integrations,
- agent-commerce infrastructure.

### 7.2 What to propose

A grant proposal should include:

1. **Problem:** agent work has no neutral acceptance layer.
2. **Primitive:** the manifest + validator design.
3. **Traction:** portal submission, Bradbury deployment, tests.
4. **Milestones:** v1.1, v1.2, one integration.
5. **Budget:** development, audit, integration support.
6. **Metrics:** agreements created, verdicts, integrations, reuse.
7. **Open source:** MIT license, public repo.

### 7.3 Milestone structure

| Milestone | Deliverable | Evidence |
|---|---|---|
| M1 | v1.1 challenge bonds + linter | Contract, tests, deployment. |
| M2 | v1.2 SDK + templates | npm package, docs, demo. |
| M3 | One marketplace integration | Public integration PR or case study. |
| M4 | Security review | Audit report or peer review. |
| M5 | v2 design | Spec + prototype. |

### 7.4 What not to promise

- Mainnet production readiness before audit.
- Legal enforceability.
- Perfect truth.
- A large user base before integration.
- Cross-chain support before the single-chain primitive is solid.

---

## 8. 90-day plan

### Days 1–14

- Finish v1 contract.
- Pass direct tests.
- Deploy to Bradbury.
- Submit to the portal.

### Days 15–30

- Respond to review.
- Publish a demo manifest and verdict.
- Write a technical post: “Why acceptance is the missing layer.”
- Start conversations with Internet Court and Collective Memory.

### Days 31–60

- Build v1.1 challenge bonds.
- Build the manifest linter.
- Add a TypeScript SDK.
- Run a pilot with a grant program or bounty.

### Days 61–90

- Integrate with one marketplace.
- Publish case study.
- Apply for a GenLayer grant.
- Design v2 milestones/private evidence.

---

## 9. Success metrics

### Primitive

- Agreements created.
- Verdicts stored.
- `UNDETERMINED` rate.
- Average time to verdict.
- Challenge rate.
- Settlement conservation.

### Integration

- External builders using the SDK.
- Marketplaces embedding the contract.
- Manifests generated from templates.
- Repeat usage per integrator.

### Ecosystem

- References from Internet Court, Collective Memory, or similar.
- Grant milestone completion.
- Public write-ups.
- Reuse of the manifest schema.

---

## 10. Sustainability

Presense v1 is open source and free to use. Possible models later:

1. **Hosted evaluation** — a paid frontend/API for teams that do not want to run their own.
2. **Integration support** — paid integration for marketplaces.
3. **Premium templates** — industry-specific manifest packs.
4. **Audit and compliance** — paid review of acceptance manifests.

Do not:

- add an admin key to monetize,
- gate the contract behind a token,
- charge for reading verdicts,
- make the manifest schema proprietary.

The primitive must remain open. The product can be paid.

---

## 11. Risks to the roadmap

| Risk | Mitigation |
|---|---|
| v1 takes longer than expected | Cut features, not consensus tests. |
| No marketplace integration | Start with a grant program or bounty pilot. |
| Portal rejection | Improve the consensus narrative and evidence. |
| LLM behavior drifts | Keep deterministic checks dominant; version rubrics. |
| Challenge bonds are gamed | Model the game; test edge cases; start with a simple bond. |
| Private evidence needs protocol support | Defer to v2; do not fake privacy. |
| Scope creep | Freeze each version before starting the next. |

---

## 12. What not to build

- A generic “AI decides everything” oracle.
- A prediction market.
- A marketing verification clone.
- A parametric insurance product.
- A centralized dashboard that computes verdicts off-chain.
- A token.
- An admin panel.
- A legal court.

Presense wins by being the best acceptance primitive, not by being everything.

---

## 13. Next document

Read [10 — Glossary & References](10-glossary-and-references.md) for terms and canonical links.
