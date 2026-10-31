# Reticle donor — independently observable UI assertion

Donor: [reticlehq/reticle](https://github.com/reticlehq/reticle).

StrawberryMe retains its architecture map, source identity, existing SQLite verification history, and independent conformance checks. Reticle is a donor for runtime UI evidence, **not** a replacement for StrawberryMe, BananaMe, AppleMe or the host's authority.

## Explicit local verification

After the operator separately installs/configures the upstream Reticle CLI and connects the running application, create one JSON assertion file *inside the repository*, for example `tests/reticle-heading.json`. The assertion follows upstream Reticle's `--expect-file` schema, e.g. `{"kind":"element","query":{"role":"heading","name":"Welcome"},"state":"visible"}`.

Run from an existing source checkout:

```bash
strawberry --root . reticle-verify --url http://127.0.0.1:8765/ --expect-file tests/reticle-heading.json
```

This invokes `reticle verify <url> --expect-file <path>` on operator request. Only explicit loopback HTTP endpoints with valid ports and an in-repository bounded JSON assertion are accepted. A Reticle exit code of 0 is `PASS` according to the upstream single-assertion contract; every nonzero/timeout/unavailable outcome is `INCONCLUSIVE`, never a claimed successful fix.

The receipt is appended through the existing `Store.append_verification` and bound to StrawberryMe's current source snapshot. It stores only status, result/expectation hashes and loopback host:port, never the raw browser output, page contents, secrets, query parameters or user messages. A later source change does not automatically turn an old result into a current pass. CI can consume the CLI exit status; no new UI dashboard or external cloud service is required.

`reticle init`, saved flows, SDK instrumentation and cloud sync are **not** enabled here. Different web stacks may need separate integration; AnanasMe's Python/HTML/JS frontend has not been proven Reticle-compatible by this Git-only change.

Test: `python -m pytest -q tests/test_reticle_donor.py` (mocked subprocess, no real browser).
