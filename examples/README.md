# Examples

Example Acceptance Manifests. `tests/direct/test_examples.py` validates each
file through `check_manifest`, so the examples cannot drift from the schema.

| File                          | Result                   | Notes                                                        |
| ----------------------------- | ------------------------ | ------------------------------------------------------------ |
| `manifest.weather-api.json`   | Valid                    | Five criteria covering all five checks; weights sum to 100.  |
| `manifest.docs-delivery.json` | Valid                    | Four criteria for a documentation delivery; weights sum 100. |
| `manifest.bad-example.json`   | `E_MANIFEST_INVALID`     | Weights sum to 90; used to show the rejection path.          |

`check_manifest` returns the canonical JSON string and its SHA-256 hash. Use the
canonical form when comparing manifests off-chain; the contract stores that
form and pins the hash at `create_agreement`.

The URLs use `example.com` domains, so the examples are structural rather than
runnable evidence sources. Replace them with the domains listed in
`evidence_policy.allowed_domains` for a real agreement.
