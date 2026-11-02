# 00 — Product Brief

**Project:** Presense
**Tagline:** The sense check before settlement.
**Version:** 0.1
**Status:** Specification
**Author:** Builder
**Last updated:** 2026-11-02

---

## 1. Executive summary

Presense is a GenLayer Intelligent Contract primitive for **acceptance adjudication**.

A buyer and a seller agree on an **Acceptance Manifest**: a JSON document that defines the objective checks and subjective rubrics a deliverable must satisfy. The buyer locks GEN escrow. The seller submits delivery evidence. GenLayer validators independently evaluate the evidence against the manifest and produce a structured verdict. Escrow is released, split, or refunded according to that verdict.

Presense is not a marketplace and not a court. It is the missing **acceptance layer** that marketplaces, agent escrows, grant programs, and bounty platforms can plug into when the happy path ends.

---

## 2. The problem

### 2.1 Agent work has no neutral acceptance layer

Agents can now negotiate, pay, and deliver work. The infrastructure for the happy path is shipping:

- **x402** moves payments.
- **ERC-8004** provides agent identity.
- **A2A** provides discovery and task exchange.

None of them answers: *did the work meet the agreement?*

When the buyer and seller disagree, every layer passes the problem down the line. The last layer is either a centralized platform, a single model, or a human court.

### 2.2 The three existing options are structurally weak

| Option | Failure |
|---|---|
| **Centralized platform** | The platform can be biased, captured, or unavailable. The seller and buyer may not trust the same platform. |
| **Single LLM prompt** | One model can be prompt-injected, hallucinate, or apply inconsistent standards. There is no evidence model and no independent verification. |
| **Human court** | Slow, expensive, jurisdiction-bound, and disproportionate for small agent transactions. |

### 2.3 The missing artifact is the acceptance spec

Most “AI judges the work” contracts fail because there is no agreed, machine-readable definition of acceptance. The buyer has a vague expectation. The seller has a vague deliverable. The judge is asked to resolve ambiguity that was never bounded.

Presense fixes this before the dispute exists:

- The buyer writes the manifest.
- The seller accepts it.
- The manifest is frozen on-chain.
- The evidence is pinned by URL and hash.
- The verdict is structured and comparable.

The dispute becomes: *does the evidence satisfy this manifest?* That is a question validators can actually answer.

---

## 3. Who it is for

### Primary users

1. **Agent marketplaces** that need neutral delivery acceptance.
2. **AI agencies and freelancers** delivering APIs, agents, datasets, content, or automations.
3. **Agent-to-agent commerce protocols** that already move money but lack dispute resolution.
4. **DAOs and grant programs** that need milestone acceptance against a rubric.
5. **Bounty platforms** that need to decide whether a submission met the brief.

### Secondary users

- **Internet Court** and similar agent-commerce standards that need an acceptance primitive.
- **Collective Memory** and agent marketplaces that need delivery verification.
- **Escrow providers** that want an adjudication backend without building one.
- **Builders** who want a reference implementation of evidence-based consensus.

---

## 4. Jobs to be done

| When… | I want to… | So that… |
|---|---|---|
| I hire an agent to build an API | freeze the acceptance criteria before work starts | the agent cannot argue about the standard later |
| I deliver work to a buyer | submit evidence and get a neutral decision | I get paid without trusting the buyer’s private judgment |
| I receive a deliverable | verify it against the agreed spec | I do not release escrow for incomplete work |
| A delivery is disputed | submit counter-evidence and get a re-evaluation | the outcome is based on evidence, not leverage |
| I run a marketplace | plug in a neutral acceptance primitive | I do not become the judge of every dispute |
| I run a grant program | evaluate milestone evidence against a rubric | funding decisions are auditable and consistent |

---

## 5. Product principles

1. **Freeze the standard before the work.** The manifest is agreed before delivery, not invented during a dispute.
2. **Evidence over narrative.** Every subjective score must cite a quote from the evidence.
3. **Deterministic before probabilistic.** If a check can be computed, compute it. Use the LLM only for judgment.
4. **Independent verification.** Validators re-run the task; they do not trust the leader’s formatting.
5. **Structured outcomes.** `ACCEPT`, `PARTIAL`, `REJECT`, `UNDETERMINED`. No free-text verdict.
6. **Fail closed.** Missing evidence is not a pass.
7. **No privileged operator.** No admin pause, no upgrade proxy, no secret override.
8. **Reusable primitive.** The contract should be easy to integrate, not a one-off demo.
9. **Small scope, high rigor.** Five check types done well beats fifty shallow checks.
10. **Public evidence only.** Privacy-sensitive flows are a later version with commit/reveal.

---

## 6. v1 scope

### In scope

- One buyer, one seller.
- Native GEN escrow.
- On-chain manifest (JSON, max 16 KiB).
- Objective checks:
  - `http_status`
  - `json_has_keys`
  - `file_hash`
  - `text_contains`
- Subjective check:
  - `llm_rubric`
- Evidence policy: HTTPS, allowed domains, size limits.
- One challenge per agreement, with counter-evidence and re-evaluation.
- Challenge window before settlement.
- Pull-payment claims and `withdraw`.
- Expiry refund if no delivery by deadline.
- Read methods for agreements, submissions, verdicts, claims, and status.

### Out of scope for v1

- Multiple milestones or tranches.
- Multi-party agreements.
- Challenge bonds and slashing.
- Private or encrypted evidence.
- ERC-20 or fiat escrow.
- Automatic GenLayer protocol appeal integration.
- A hosted frontend.
- Reputation writes to ERC-8004.
- Cross-chain settlement.

---

## 7. User stories

### US-1 — Create an agreement

As a buyer, I create an agreement by providing:
- seller address,
- manifest JSON,
- manifest URL (optional, for humans),
- deadline,
- challenge window,
- metadata URL (optional).

I attach GEN equal to the escrow. The contract validates the manifest, stores it canonically, and sets status to `CREATED`.

**Acceptance:** invalid manifests are rejected with a specific error; a valid manifest is retrievable by hash; escrow equals `gl.message.value`.

### US-2 — Accept an agreement

As the seller, I accept the agreement. Status becomes `ACTIVE`.

**Acceptance:** only the seller can accept; cannot accept twice; cannot accept after cancellation or expiry.

### US-3 — Submit delivery

As the seller, I submit artifact URLs, hashes, and notes before the deadline. Status becomes `SUBMITTED`.

**Acceptance:** only the seller can submit; only in `ACTIVE`; deadline not passed; at least one artifact; URLs pass the evidence policy.

### US-4 — Evaluate

As either party (or any caller), I trigger evaluation. The contract runs the manifest checks and stores a verdict. Status becomes `EVALUATED`.

**Acceptance:** evaluation only in `SUBMITTED` or `DISPUTED`; verdict contains one result per criterion; payout math is conserved; missing evidence produces `UNDETERMINED`.

### US-5 — Challenge

As either party, within the challenge window, I submit counter-evidence and a reason. Status becomes `DISPUTED`.

**Acceptance:** only buyer or seller; only in `EVALUATED`; only within window; only one challenge per agreement in v1; counter-evidence passes the evidence policy.

### US-6 — Settle

As any caller, after the challenge window, I settle an `EVALUATED` agreement. Status becomes `SETTLED`; claims are credited.

**Acceptance:** cannot settle before the window; cannot settle twice; buyer claim + seller claim equals escrow.

### US-7 — Withdraw

As a party with a claim, I withdraw GEN by declaring my recipient kind (`evm` or `ic`).

**Acceptance:** claim is reduced by the withdrawn amount; invalid kind is rejected; zero claim is rejected.

### US-8 — Expire

As any caller, if the seller did not submit by the deadline, I expire the agreement and refund the buyer.

**Acceptance:** only in `ACTIVE`; deadline passed; no submission; buyer claim equals escrow.

---

## 8. Success metrics

### Product metrics

| Metric | Target for v1 |
|---|---|
| Time from submission to verdict | < 30 minutes common case |
| Verdict finalization rate | > 95% of evaluations produce a verdict |
| Undetermined rate | < 10% on well-formed manifests |
| Dispute rate | < 20% of agreements |
| Settlement conservation | 100% (`buyer + seller == escrow`) |
| Validator disagreement on clear cases | < 5% in tests |

### Builder metrics

| Metric | Target |
|---|---|
| Direct-mode tests | ≥ 30 |
| Adversarial tests | ≥ 10 |
| Integration tests on Bradbury | ≥ 5 |
| Lint errors | 0 |
| Portal submission | Accepted in Intelligent Contracts category |
| Reuse | At least one external builder imports the manifest schema |

### Ecosystem metrics

- One integration conversation with an agent marketplace or Internet Court ecosystem project.
- One public demo manifest for an API delivery.
- One public write-up explaining the objective/subjective split.

---

## 9. Competitive landscape

| Project | What it does | Relationship to Presense |
|---|---|---|
| **Internet Court** | Open skill and standard for agent-to-agent contracts and disputes. | Presense can be an acceptance primitive that Internet Court-compatible agents call. Not a competitor. |
| **Collective Memory** | Agent-work platform using GenLayer for quality assurance. | Potential integrator: Presense verifies delivery against a structured manifest before settlement. |
| **Rally** | Performance-based marketing verification. | Adjacent; Presense is generic acceptance, not marketing-specific. |
| **Intelligent Oracle** | Prediction markets and parametric insurance. | Different problem; Presense is delivery acceptance, not event resolution. |
| **MicroMarkets** | Small truth markets (in development). | Different problem. |
| **Traditional escrow** | Holds funds and releases on buyer approval. | Presense adds neutral adjudication and evidence. |
| **Centralized AI judge** | Single model decides. | Presense adds independent validators, frozen criteria, and appeals. |

**Positioning statement:** Presense is the acceptance layer for agent work: the primitive that turns a vague “did they deliver?” into a structured, evidence-based decision that both sides agreed to in advance.

---

## 10. Risks and assumptions

### Assumptions

1. Agent marketplaces will pay for neutral acceptance rather than build their own.
2. Buyers can write or generate a machine-readable manifest.
3. Public evidence is sufficient for most agent-delivered work (APIs, docs, code, content).
4. GenLayer’s web and LLM access is reliable enough for acceptance checks.
5. Validators can independently fetch the same evidence.

### Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Buyers write vague manifests | High | Provide templates and a manifest linter; reject manifests with no objective checks. |
| Evidence disappears | High | Store manifest on-chain; require hashes; allow `UNDETERMINED`; encourage multiple sources. |
| Prompt injection in evidence | High | Delimit evidence, instruct models to ignore embedded instructions, verify quotes, use greyboxing. |
| LLM scores vary | Medium | Tolerance bands; compare pass/fail; evidence-quote verification. |
| Validators disagree on subjective criteria | Medium | Clear rubrics; one criterion per dimension; threshold gates; `UNDETERMINED` instead of guessing. |
| Payout message failure | Medium | Pull-payment claims; explicit recipient kind; document residual risk. |
| Gas/storage costs | Medium | Cap manifest size and criteria count; avoid storing raw evidence. |
| Legal overclaim | Medium | Frame as evidence-based settlement, not legal judgment; include terms. |
| Scope creep | High | Freeze v1 scope; move milestones, bonds, privacy to v2. |

---

## 11. Naming story

**Presense** = **pre** + **sense**.

- **Pre:** before settlement, before the dispute escalates, before money moves.
- **Sense:** the act of making sense of evidence against an agreed standard.

The name is intentionally close to “presence” — the contract is present at the moment of delivery, sensing whether the agreement was kept.

---

## 12. Definition of success for v1

Presense v1 is successful when:

1. A buyer and seller can complete the full lifecycle on Bradbury.
2. The contract produces a structured verdict with per-criterion evidence.
3. A malicious leader cannot force a false verdict in tests.
4. The manifest schema is documented well enough for another builder to generate one.
5. The submission is accepted in the GenLayer builder portal’s Intelligent Contracts category.
6. At least one external builder or agent framework expresses interest in integrating it.

---

## 13. Next document

Read [01 — Architecture](01-architecture.md) for the system design and state machine.
