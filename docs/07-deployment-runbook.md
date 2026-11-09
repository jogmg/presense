# 07 — Deployment Runbook

**Project:** Presense
**Version:** 0.1
**Purpose:** Exact steps to take Presense from a local repository to a verified Studionet deployment. Bradbury is deferred.

---

## 1. Prerequisites

| Tool | Version | Why |
|---|---|---|
| Python | 3.12+ | Contract linting and tests. |
| Node.js | 18+ | GenLayer CLI and GenLayerJS. |
| npm | 9+ | CLI install. |
| Git | any recent | Version control. |
| Docker | 26+ | Optional; local Studio with full GenVM. |
| GenLayer CLI | current | Deploy, call, inspect. |
| A funded account | Studionet GEN (current); Bradbury GEN when that phase resumes | Deployment and test escrow. |

### 1.1 Install the CLI

```bash
npm install -g genlayer
genlayer --version
```

### 1.2 Install Python dependencies

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

`requirements.txt` pins the tested toolchain:

```text
genlayer-test==0.29.2
genvm-linter==0.11.0
pytest>=9,<10
pytest-cov>=7,<8
```

The linter is provided by `genvm-linter`. Verify:

```bash
genvm-lint --help
```

### 1.3 Verify the repo

```bash
genvm-lint check contracts/Presense.py
pytest tests/direct/ -v
```

Do not proceed past Studionet until both pass.

`tests/conftest.py` includes two compatibility shims for the pinned
`genlayer-test` release: a fallback to GenVM's renamed runner bundle and a
Windows-safe temp-file cleanup. Set `PRESENSE_SKIP_TOOLCHAIN_SHIMS=1` to
disable them after upgrading the toolchain.

---

## 2. Network reference

| Network | Alias | Chain ID | RPC | Explorer | Use |
|---|---|---|---|---|---|
| Localnet | `localnet` | 61127 | `http://localhost:4000/api` | `http://localhost:8080` | Full local GenVM. |
| Studionet | `studionet` | 61999 | `https://studio.genlayer.com/api` | `https://explorer-studio.genlayer.com` | Current deployment target. |
| Studio dev | `studio-dev` | 61997 | `https://studio-dev.genlayer.com/api` | `https://explorer-studio-dev.genlayer.com` | Release-candidate validation only. |
| Bradbury | `testnet-bradbury` | 4221 | Use the Phase 2 GenLayer node RPC from the release announcement, or your own qualified node. | `https://scan.testnet-chain.genlayer.com/` | Deferred. |

### 2.1 Bradbury endpoints (deferred)

These endpoints are recorded for the deferred phase; Studionet is the current
target.

| Setting | Value |
|---|---|
| GenLayer RPC | Phase 2 node RPC from the release announcement, or your own qualified node. |
| GenLayer Chain RPC | `https://rpc.testnet-chain.genlayer.com` |
| Chain ID | `4221` |
| Currency | GEN |
| Explorer | `https://scan.testnet-chain.genlayer.com/` |
| Faucet | `https://testnet-faucet.genlayer.foundation` |
| Staking UI | `https://stakegen.com/explore/` |

**Important:** `gen_*` calls require a GenLayer node RPC. The Conduit L2 RPC does not serve `gen_call`. Use the CLI alias `testnet-bradbury` so the CLI resolves the correct RPC and consensus deployment.

Before signing:

```bash
genlayer network set testnet-bradbury
genlayer network info
```

Confirm the RPC, chain ID, explorer, and contract addresses. If the CLI resolves a different genesis or chain ID, stop.

---

## 3. Account setup

### 3.1 Create or import an account

```bash
genlayer account create
genlayer account list
genlayer account use <name>
genlayer account show
```

Or import an existing key:

```bash
genlayer account import <name>
```

### 3.2 Fund the account

1. Open `https://testnet-faucet.genlayer.foundation`.
2. Paste the address from `genlayer account show`.
3. Request test GEN.
4. Confirm the balance:

```bash
genlayer account show
```

### 3.3 Security

- Never commit a private key.
- Use a dedicated testnet account.
- Do not reuse a mainnet key.
- Keep the keystore out of the repo.
- For CI, use a secret manager, not a plain `.env` in git.

### 3.4 `gltest.config.yaml`

Integration tests read network accounts from `gltest.config.yaml`. The repository ships a safe template:

```bash
cp gltest.config.yaml.example gltest.config.yaml
```

```yaml
networks:
  testnet_bradbury:
    accounts:
      - "${ACCOUNT_PRIVATE_KEY_1}"
```

The real `gltest.config.yaml` is ignored by git. Use environment variables, keep the file out of git if it contains secrets, and confirm the network key matches the `gltest` command (`testnet_bradbury` with an underscore; the CLI alias is `testnet-bradbury` with a hyphen).

Direct-mode tests do not need this file. If it is absent, `pytest tests/direct/` runs with the default local configuration.

---

## 4. Local workflow

### 4.1 Lint

```bash
genvm-lint check contracts/Presense.py
```

Fix every error before testing. Use `--json` for CI.

### 4.2 Direct tests

```bash
pytest tests/direct/ -v
```

Expected:

- Phase 1: all manifest parsing, canonicalization, policy, URL, and check-param tests pass.
- Later phases add lifecycle, objective-check, validator, settlement, and security tests.

### 4.3 Coverage

```bash
pytest tests/direct/ --cov=contracts --cov-report=term-missing
```

Target: ≥ 85% for `contracts/Presense.py`. Current Phase 1 result: 96%.

### 4.4 GLSim (optional, fast)

```bash
pip install "genlayer-test[sim]"
glsim --port 4000 --validators 5
```

In another terminal:

```bash
gltest tests/integration/ -v -s
```

GLSim is fast but runs the Python runner natively, not inside GenVM. Use it for iteration; validate on localnet before Studionet (current) or Bradbury (deferred).

### 4.5 Localnet (full GenVM)

```bash
genlayer init
genlayer up
genlayer network set localnet
genlayer network info
```

Studio UI: `http://localhost:8080/`
RPC: `http://localhost:4000/api`

Run integration tests:

```bash
gltest tests/integration/ -v -s --network localnet
```

### 4.6 Studionet (current deployment)

```bash
genlayer network set studionet
genlayer deploy --contract contracts/Presense.py
```

Presense is deployed on Studionet:

| Field | Value |
|---|---|
| Network | Studionet |
| Chain ID | `61999` |
| Contract address | `0x1905d0Af801cc32D817Eed228b81902Dd1eB7DA9` |
| Explorer | [GenLayer Studio Explorer](https://explorer-studio.genlayer.com/address/0x1905d0Af801cc32D817Eed228b81902Dd1eB7DA9) |
| Deployment status | Finalized; GenVM result `SUCCESS` |

Studionet state is temporary. Keep the address and explorer link in the portal
evidence before it is reset. Bradbury remains deferred.

---

## 5. Deploy to Bradbury (deferred)

Bradbury is deferred. Studionet is the current deployment; use this section only
when the project resumes the persistent testnet phase.

### 5.1 Pre-deploy checklist

- [x] `genvm-lint check` passes.
- [x] Direct tests pass.
- [x] Localnet integration tests pass against `glsim` (full GenVM localnet pending).
- [x] Studionet deployment is verified and recorded.
- [ ] Bradbury account is funded.
- [ ] `genlayer network info` shows the expected chain.
- [x] The contract has no constructor arguments.
- [x] The magic comment is exact.
- [x] No private keys or secrets are in the repo.

### 5.2 Deploy

```bash
genlayer network set testnet-bradbury
genlayer network info
genlayer deploy --contract contracts/Presense.py
```

Expected output:

```text
Contract deployed successfully!
Transaction Hash: 0x...
Contract Address: 0x...
```

Save both values:

```text
PRESENSE_ADDRESS=0x...
DEPLOY_TX=0x...
```

### 5.3 Verify the deployment

```bash
genlayer receipt <DEPLOY_TX>
genlayer schema <PRESENSE_ADDRESS>
genlayer code <PRESENSE_ADDRESS>
```

Check the explorer:

```text
https://scan.testnet-chain.genlayer.com/address/<PRESENSE_ADDRESS>
```

Confirm:

- the contract exists,
- the source matches the repo,
- the schema exposes the expected methods,
- the deploy transaction is finalized.

### 5.4 If the CLI asks for fees

Consensus v0.6 deployments may be fee-charging. The CLI and SDK handle fee estimation, but verify the effective fee before signing. For scripted deployments, use `estimateTransactionFeesForWrite` or a checked-in `fee-profile.json`.

Do not hardcode a fee that was measured on a different network.

---

## 6. Deploy script (optional)

The repository should include `deploy/001_deploy_presense.ts` for repeatable deployment when the CLI is not enough. The official GenLayer boilerplate provides the fee-aware helper; use it rather than hand-rolling fee math.

Minimal shape:

```ts
import fs from "node:fs";
import { createClient } from "genlayer-js";
// Bradbury template. For the current Studionet deployment, use the matching
// chain export from "genlayer-js/chains".
import { testnetBradbury } from "genlayer-js/chains";

// Use the funded account pattern from the GenLayer boilerplate.
// Do not hardcode a private key.
const client = createClient({
  chain: testnetBradbury,
  account: fundedAccount,
});

const code = fs.readFileSync("contracts/Presense.py", "utf8");

const tx = await client.deployContract({
  code,
  args: [],
});

const receipt = await client.waitForFinalization({ hash: tx });
console.log(JSON.stringify(receipt, null, 2));
```

Replace `fundedAccount` with the boilerplate’s account setup. The exact helper may change; the official deploy-script docs are the source of truth.

---

## 7. Smoke test on Studionet (current) or Bradbury (deferred)

**Status: not yet run.** Studionet is deployed and the explorer link resolves;
the live lifecycle smoke test remains pending. Use the same flow on Bradbury
when that phase resumes.

Use a small escrow (e.g., 0.01 GEN). Do not test with more than you are prepared to lose.

### 7.1 Create

Use the Studio UI or GenLayerJS. The buyer is the transaction sender.

```ts
const createTx = await client.writeContract({
  address: presenseAddress,
  functionName: "create_agreement",
  args: [
    "agr_smoke_001",
    sellerAddress,
    manifestJson,
    "",
    BigInt(Math.floor(Date.now() / 1000) + 7 * 86400),
    BigInt(86400),
    "",
  ],
  value: 10_000_000_000_000_000n, // 0.01 GEN
});
await client.waitForFinalization({ hash: createTx });
```

### 7.2 Read status

```bash
genlayer call <PRESENSE_ADDRESS> get_status
```

Or:

```ts
const status = await client.readContract({
  address: presenseAddress,
  functionName: "get_status",
  args: ["agr_smoke_001"],
});
```

Expected: `CREATED`.

### 7.3 Accept as seller

Switch to the seller account in Studio or use the seller client:

```ts
await client.writeContract({
  address: presenseAddress,
  functionName: "accept_agreement",
  args: ["agr_smoke_001"],
});
```

Expected: `ACTIVE`.

### 7.4 Submit

```ts
await client.writeContract({
  address: presenseAddress,
  functionName: "submit_delivery",
  args: [
    "agr_smoke_001",
    ["https://your-evidence.example/health", "https://your-evidence.example/docs"],
    ["", ""],
    "Smoke test delivery.",
  ],
});
```

Expected: `SUBMITTED`.

### 7.5 Evaluate

```ts
const evalTx = await client.writeContract({
  address: presenseAddress,
  functionName: "evaluate",
  args: ["agr_smoke_001"],
});
const evalReceipt = await client.waitForFinalization({ hash: evalTx });
```

Expected: `EVALUATED`, with a verdict ID.

### 7.6 Read the verdict

```ts
const verdict = await client.readContract({
  address: presenseAddress,
  functionName: "get_verdict",
  args: ["agr_smoke_001:verdict:1"],
});
```

Verify:

- `decision` is one of `ACCEPT`, `PARTIAL`, `REJECT`,
- `score` is 0–100,
- `payout_buyer + payout_seller == escrow`,
- every criterion is present.

### 7.7 Challenge (optional)

If the verdict is wrong, call `challenge` with counter-evidence within the window. Then re-evaluate.

### 7.8 Settle

After the challenge window:

```ts
const settleTx = await client.writeContract({
  address: presenseAddress,
  functionName: "settle",
  args: ["agr_smoke_001"],
});
await client.waitForFinalization({ hash: settleTx });
```

Expected: `SETTLED`.

### 7.9 Withdraw

As buyer:

```ts
await client.writeContract({
  address: presenseAddress,
  functionName: "withdraw",
  args: ["evm"],
});
```

As seller:

```ts
await client.writeContract({
  address: presenseAddress,
  functionName: "withdraw",
  args: ["evm"],
});
```

Confirm claims are zero:

```ts
await client.readContract({
  address: presenseAddress,
  functionName: "get_claim",
  args: [buyerAddress],
});
```

### 7.10 Record evidence

Save:

- contract address,
- deploy transaction hash,
- create/accept/submit/evaluate/settle/withdraw hashes,
- verdict JSON,
- explorer links,
- latency notes,
- any failures and retries.

This evidence goes into the portal submission.

---

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `genlayer deploy` uses the wrong chain | Network alias not set. | `genlayer network set studionet` (current) or `testnet-bradbury` (deferred); `genlayer network info`. |
| `gen_call` fails | Using the L2 chain RPC instead of a GenLayer node RPC. | Use the Phase 2 node RPC or the CLI alias. |
| Deployment reverts on manifest | Manifest validation failed. | Run the manifest linter; check duplicate keys, weights, URLs. |
| Evaluation returns `UNDETERMINED` | Evidence unavailable or validators disagree. | Check evidence URLs, retry, add alternative sources. |
| Challenge rejected | Window closed or already challenged. | Check `evaluated_at` and `challenge_count`. |
| Settlement rejected | Window still open. | Wait for `evaluated_at + challenge_window`. |
| Withdraw reverts | No claim or bad kind. | Check `get_claim`; use `"evm"` or `"ic"`. |
| Transaction stuck | Consensus/fee issue. | `genlayer receipt <hash>`, `genlayer trace <hash>`, check fees. |
| Explorer shows no contract | Wrong explorer or wrong chain. | Use `explorer-studio.genlayer.com` with chain ID 61999 for Studionet, or `scan.testnet-chain.genlayer.com` with chain ID 4221 for Bradbury. |
| Faucet does not credit | Wrong address or faucet network. | Recheck address; confirm faucet target. |
| Lint fails on storage | Used `dict`/`list`. | Use `TreeMap`/`DynArray`. |
| Lint fails on nondet | Web/LLM call outside a nondet block. | Move it into `run_nondet_unsafe` or the appropriate block. |

### 8.1 Useful commands

```bash
genlayer network list
genlayer network info
genlayer account show
genlayer receipt <txHash>
genlayer trace <txHash>
genlayer schema <contractAddress>
genlayer code <contractAddress>
genlayer call <contractAddress> <method>
genlayer write <contractAddress> <method>
```

---

## 9. Fee handling

GenLayer Consensus v0.6 introduces fee-funded writes and deployments.

### 9.1 For development

Use the Studio/GLSim gasless modes where available. Do not ship a fee model based on gasless behavior.

### 9.2 For production-like tests

1. Measure the write with `estimateTransactionFeesForWrite`.
2. Save the result in `fee-profile.json`.
3. Pass the resulting `fees` object to `writeContract` / `deployContract`.
4. Re-profile after contract changes.

### 9.3 What to watch

- Leader and validator time-unit allocations.
- Execution budget per round.
- Message fees for withdrawal transfers.
- Appeal rounds.
- Rotations.

A withdrawal emits a value transfer, so it may need a larger message-fee budget than a simple state write. Profile it separately.

---

## 10. Rollback and upgrade

v1 is immutable. There is no proxy and no admin.

If a critical bug is found:

1. Stop promoting the address.
2. Deploy a v2 contract.
3. Publish a migration notice.
4. Keep v1 online so existing agreements can settle or expire.
5. Do not attempt an admin rescue; none exists.

For a stuck agreement:

- retry evaluation,
- add alternative evidence via challenge,
- use permissionless `settle` or `claim_expired`,
- escalate to GenLayer if the issue is protocol-level.

---

## 11. Pre-submission security checklist

- [x] Lint clean.
- [x] Direct tests pass.
- [x] Localnet integration passes against `glsim` (full GenVM localnet pending).
- [x] Studionet deployment verified (address and explorer link recorded).
- [ ] Studionet smoke test passes.
- [ ] Bradbury smoke test passes. Deferred.
- [x] No admin keys.
- [x] No upgrade proxy.
- [x] No `dict`/`list` storage.
- [x] No unbounded loops.
- [x] Manifest size cap enforced.
- [x] URL policy enforced.
- [x] Evidence quote verified.
- [x] Payout conservation tested.
- [x] Double withdrawal tested.
- [x] Challenge window tested.
- [x] Withdraw tested for both `evm` and `ic`.
- [x] README links the docs.
- [ ] Portal evidence saved.

---

## 12. Handoff to portal submission

Once the smoke test is complete, collect:

- GitHub repo URL,
- Studionet contract address (`0x1905d0Af801cc32D817Eed228b81902Dd1eB7DA9`),
- deploy transaction hash from the Studionet explorer,
- explorer link,
- verdict JSON,
- test summary,
- architecture diagram,
- consensus explanation.

Then follow [08 — Portal Submission](08-portal-submission.md).

---

## 13. Next document

Read [08 — Portal Submission](08-portal-submission.md) for the contribution narrative and evidence checklist.
