# M00 dependency locks

Source: user-supplied CloudStudio `pip freeze --all` for commit
`954bfb341d638e62bf8243073b03f30850ae2d81`, Ubuntu 24.04.3 LTS x86_64,
Python 3.11.1. The user reported 13/13 SQLite PoC tests passed on that environment.
Fresh-environment lock replay: **NOT_RUN**. T-002 remains **PARTIAL**, not accepted.

| File | Role |
|---|---|
| `m00.in` | Original direct-dependency ranges, retained byte-for-byte; do not use ranges to replay |
| `m00-bootstrap.lock` | Exact environment bootstrap tools: pip 22.3.1, setuptools 65.5.0 |
| `m00.lock` | Exact 11 project/test packages, including transitive dependencies |

The union is exactly the supplied 13-package snapshot. No upgrades, downgrades,
replacement packages, inferred pins, wheel package or new package manager were added.
The two locks must be used together. Use `scripts/m00/replay_dependencies.sh` as described
in [the replay guide](../docs/m00-replay.md); it creates a fresh venv for each run.

The script installs bootstrap tools first, then all project/test pins with `--no-deps`.
This prevents resolving extra/unpinned dependencies; `pip check` must then establish
dependency consistency. A strict metadata comparison rejects missing packages, extra
packages, duplicate distributions and version differences, including bootstrap tools.
Names are normalized for case and hyphen/underscore equivalence; version strings must match.

Use venv + pip and pytest only. Installs use public PyPI, no inherited pip configuration,
no cache or source build, and exact wheels for the target environment. If a pinned wheel
cannot be obtained, stop and return the error; do not change versions to make it install.
The snapshot provided version pins, not wheel hashes, so these are exact-version locks,
not a claim of artifact hash verification. The interpreter/system version remains part
of the replay evidence; the script never installs or changes the Python interpreter.

This batch declares no frontend dependencies and creates no npm lock file or application.
All replay results stay in ignored `var/m00/`; return sanitized logs, actual commit,
`verification.json`, `junit.xml` and both exit-code files for review. Keep T-002 pending
until the user supplies the real replay evidence and explicitly accepts it.
