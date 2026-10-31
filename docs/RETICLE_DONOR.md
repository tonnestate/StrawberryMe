# Reticle donor — independently observable UI assertion

Donor: [reticlehq/reticle](https://github.com/reticlehq/reticle).

StrawberryMe retains its architecture map, source identity, existing SQLite verification history, and independent conformance checks. Reticle is a donor for runtime UI evidence, **not** a replacement for StrawberryMe, BananaMe, AppleMe or the host's authority.

## Explicit local verification

After the operator separately installs/configures the upstream Reticle CLI and connects the running application, create one JSON assertion file *inside the repository*, for example `tests/reticle-heading.json`. The assertion follows upstream Reticle's `--expect-file` schema, e.g. `{"kind":"element","query":{"role":"heading","name":"Welcome"},"state":"visible"}`.

Run from an existing source checkout:

```bash
strawberry --root . reticle-verify --url http://127.0.0.1:8765/ --expect-file tests/reticle-heading.json
```

This invokes `reticle verify <url> --expect-file <path>` on operator request. Only explicit loopback HTTP endpoints with valid ports and an in-repository bounded JSON assertion are accepted. The upstream `--expect-file` path requires a running, connected local Reticle daemon: this adapter does not start one. The configured `--timeout` is passed to the Reticle CLI in milliseconds; the subprocess is given five additional seconds for teardown. A Reticle exit code of 0 is `PASS` according to the upstream single-assertion contract; every nonzero/timeout/unavailable outcome is `INCONCLUSIVE`, never a claimed successful fix.

The receipt is appended through the existing `Store.append_verification` and bound to StrawberryMe's current source snapshot. To prevent assertion-content drift during verification, the adapter snapshots the validated JSON bytes into a private temporary file for the CLI, hashes those exact bytes, deletes the temporary file after execution, and reports `INCONCLUSIVE` when the original assertion changed or disappeared during execution. `strawberry status` and `strawberry verify` now project the most recent Reticle assertion separately as `external_ui`, explicitly labeling `CURRENT`, `STALE`, or `UNATTESTED_SOURCE` (when no Git source identity exists); neither a passed assertion nor a current source hash grants completion authority or proves that the deployed URL serves this checkout. It stores only status, result/expectation hashes and loopback host:port, never the raw browser output, page contents, secrets, query parameters or user messages. A later source change does not automatically turn an old result into a current pass. CI can consume the CLI exit status; no new UI dashboard or external cloud service is required.

`reticle init`, saved flows, SDK instrumentation and cloud sync are **not** enabled here. Different web stacks may need separate integration; AnanasMe's Python/HTML/JS frontend has not been proven Reticle-compatible by this Git-only change.

Tests: `python -m pytest -q tests/test_reticle_donor.py tests/test_reticle_assurance_projection.py` (mocked subprocess, no real browser).
