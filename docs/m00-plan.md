# M00 execution plan

Scope: prepare T-001–T-003 on Windows; execute and accept tests later in CloudStudio Ubuntu.
Authority: local `handoff/hrms-m00/Codex_执行指令_T001-T003.md`, seven approved designs,
and the user's GitHub Public/main/agent commit-and-push instructions.

1. Preserve original files, copy handoff, verify seven SHA-256 values, initialize main.
2. T-001: publish only baseline index/hashes and a fail-closed verifier. Keep full designs local.
3. T-002: provisional pip constraints, Ubuntu version checker, empty environment template,
   installation/replay instructions. No guessed runtime versions or verified lock claim.
4. T-003: pytest assertions first, then isolated sqlite3/SQLAlchemy connection helpers,
   Alembic fixture revisions and shell runner. New temporary file database per case/run.
   Exercise lock rejection/wait, CAS, uniqueness/NULL, global markers, incident races,
   rollback, real FK/integrity checks, migration failure quarantine and online backup.
5. Statically inspect syntax/line endings and public staged contents on Windows.
   No Windows PoC execution; every CloudStudio result stays NOT_RUN.
6. Review scripts against the requirements, commit with existing Git identity,
   authenticate via official gh browser login, inspect name conflicts, create public hrms,
   push without force and verify remote main SHA and visibility.

Review focus: never reuse/delete a user database; bound concurrency waits; fail if a
negative case unexpectedly succeeds; do not assume SQLite DDL rollback; include committed
WAL contents in online backup; public clone must explain why private handoff is absent.
No T-004, production recovery CLI, employee/attendance/payroll models or trust initialization.
