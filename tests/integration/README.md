# Integration tests

These tests run against a live GenLayer network (Localnet, Studionet, or Bradbury).
They are intentionally separate from `tests/direct/` because they exercise real
consensus, web access, LLM calls, and message delivery.

Planned files:

- `test_localnet_lifecycle.py`
- `test_bradbury_lifecycle.py`

Run:

```bash
gltest tests/integration/ -v -s --network localnet
```

Accounts are read from `gltest.config.yaml`, using environment variables.
