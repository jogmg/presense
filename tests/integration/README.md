# Integration tests

These tests exercise the deployed contract through a real RPC surface (consensus,
web access, time, and transaction receipts). They are separate from
`tests/direct/` so that a plain `pytest` run never needs a live network.

## What is covered

`test_localnet_lifecycle.py` currently runs two scenarios:

- create → accept → submit → evaluate → settle → withdraw, asserting the
  verdict, payouts, claims, and final statuses.
- create → accept → advance time → `claim_expired` → withdraw, asserting the
  buyer refund.

The manifest is objective-only (`https://example.com/`), so the evaluation does
not need an LLM provider.

## Run against glsim

```bash
python scripts/run_glsim.py --no-browser   # terminal 1
gltest tests/integration -v -s --network localnet   # terminal 2
```

`scripts/run_glsim.py` exists because `glsim` 0.29.2 needs four toolchain
shims on this project:

1. A fallback for GenVM's renamed runner bundle.
2. A Windows-safe temp-file cleanup for the direct loader.
3. Caching the real contract class instead of `gltest`'s calldata proxy.
4. Applying a write transaction's native value to the simulated VM; without
   it, `gl.message.value` is always zero and payable methods fail.

The tests also assert `leader_receipt.execution_result == "SUCCESS"` because
glsim reports a reverted deterministic call as a `FINALIZED` transaction.

## Accounts and configuration

Copy `gltest.config.yaml.example` to `gltest.config.yaml` and set
`ACCOUNT_PRIVATE_KEY_1` and `ACCOUNT_PRIVATE_KEY_2` in `.env`. The simulator
does not require funded accounts; the suite funds both test accounts through
`sim_fundAccount`. `gltest.config.yaml` is gitignored.

Run the same suite against a full GenVM localnet or Bradbury by pointing
`--network` at the corresponding configured network. Those live-network runs
remain part of Phase 7.
