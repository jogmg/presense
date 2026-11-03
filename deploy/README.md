# Deploy scripts

Deployment scripts will live here once the contract interface stabilizes.

Expected files:

- `001_deploy_presense.ts` — fee-aware Bradbury deployment

The CLI path is documented in `docs/07-deployment-runbook.md`:

```bash
genlayer network set testnet-bradbury
genlayer deploy --contract contracts/Presense.py
```
