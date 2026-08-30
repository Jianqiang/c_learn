# c_learn — Personal Learning OS (v1)

Local-first, concept-centric learning workbench. See
`Personal_Learning_OS_v1_Tech_Plan.md` for the full design.

## Setup (reproducible)

Bare `python3` on this machine has no project dependencies installed —
always use the project virtualenv, not the system interpreter.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install -r requirements-lock.txt   # pins exact versions used in dev
```

`requirements-lock.txt` is a `pip freeze` snapshot of the environment the
test suite was last verified against (pytest, sympy, pint, typer, pyyaml
+ transitive deps). `pyproject.toml` lists the abstract/minimum
dependency ranges; the lock file pins the exact versions that were last
verified to work, given a matching Python version and platform.

**Reproducibility caveat**: this is a version-pin snapshot, not a
hermetic lock. It does not pin the Python/pip version, does not use
platform markers, does not pin package hashes, and does not lock build
dependencies. In practice it reproduces the verified dependency versions
on a similar Python 3.11+ environment on the same OS family — it is not
a guarantee of bit-for-bit reproducibility across arbitrary machines.

## Running tests

```bash
source .venv/bin/activate
python -m pytest -q
```

As of the last verified run: **271/271 tests passing**. Re-run the
command above yourself before trusting this number — it can drift with
every commit.

## Quickstart (CLI)

Once installed (see Setup above), the `learn` console-script is on your
`PATH` inside the venv. A full run from a clean environment, seeding the
real vertical-slice content shipped in this repo's `content/` directory:

```bash
source .venv/bin/activate
learn init                                  # creates data/learning.db
learn seed --content-dir content            # loads modules/sources/concepts/items/applications
learn status                                # list modules
learn status kv-cache                       # show one concept's workflow_status
learn drill kv-cache --answer 21.47         # deterministic drill, records a PASS/MISS attempt
learn apply kv-cache --ref "real application note" --strong
learn review                                # show today's due-for-review batch (12 item / 20 min budget)
learn retire kv-cache --reason "pausing active review"
learn export --out ./export_out             # dumps every runtime table to JSON
```

`--db <path>` is a top-level option that works before any subcommand
(default: `data/learning.db`, relative to the current working directory):

```bash
learn --db /tmp/scratch.db init
```

Every command above was smoke-tested end-to-end in a fresh temp directory
while writing this README (`init` → `seed` → `drill` → `apply` → `review`
→ `status` → `export`, all against a brand-new SQLite file) — this is the
same path `tests/test_end_to_end.py` exercises at the service layer,
confirming plan section 14's M0 acceptance criterion: "新环境初始化后，可从
drill 走到 apply，SQLite 中有完整可追溯记录。"

## Backup & restore

Backup/restore is implemented as a service (`learning_os.services.
backup_service.backup_database()` / `restore_database()`, tested in
`tests/test_backup_export.py`) but does **not** yet have a `learn backup`/
`learn restore` CLI command — only `learn export` (JSON dump, not a
restorable backup) is wired to the CLI so far. To back up or restore
today, call the service functions directly from a Python shell:

```python
from datetime import datetime
from learning_os.db import init_db
from learning_os.services.backup_service import backup_database, restore_database

conn = init_db("data/learning.db")
backup_database(conn, "data/backups", now=datetime.now())   # -> data/backups/learning_<timestamp>.db
restore_database("data/backups/learning_20260101_090000.db", "data/learning_restored.db")
```

`backup_database()` uses SQLite's own online backup API (`sqlite3.
Connection.backup()`), so it is safe to call against a connection with a
session in flight. `restore_database()` refuses to treat an arbitrary
file as a backup — it raises `ValueError` if the source isn't a SQLite
file with this project's `schema_migrations` table, so a path typo fails
loudly instead of producing a broken target database.

## Verifying a clean working tree

```bash
git status --short
```

Should print nothing. If you see `?? .workbuddy/...`, that's the local
agent work-memory directory (gitignored, not part of the product).

## What's implemented (M0 vertical slice — complete)

Every M0 acceptance item from `Personal_Learning_OS_v1_Tech_Plan.md`
section 14 is done, each backed by its own TDD suite:

- SQLite schema + idempotent migration runner (`learning_os/db.py`)
- Module/Source/Concept repository layer with explicit state machines
  and audit trail (`learning_os/repositories.py`)
- Level-1 deterministic grader: numeric/unit/symbolic/discrimination
  (`learning_os/graders/deterministic.py`)
- Level-2 rubric grader + manual/LLM-assisted adjudication
  (`learning_os/graders/rubric.py`)
- Session & attempt service with interrupt-safe resume, and an audit
  trail that refuses to silently overwrite an already-submitted attempt
  (`learning_os/services/session_service.py`)
- Baseline review scheduler (1/3/7/14/30-day ladder, leech detection,
  12-item/20-minute hard budget) + budget-aware review service
  (`learning_os/schedulers/baseline.py`,
  `learning_os/services/review_service.py`)
- Applications & concept status evidence gates
  (QUEUED→ACTIVE→USABLE→STABLE→RETIRED→REACTIVATED, each promotion to
  USABLE/STABLE/RETIRED mechanically checked against real attempt/
  application rows, never bypassable by a hand-written reason string)
  (`learning_os/services/application_service.py`)
- Next Best Actions recommendation service
  (`learning_os/services/recommendation_service.py`)
- SQLite single-file backup/restore (service-level, see "Backup &
  restore" above) and JSON/CSV export
  (`learning_os/services/backup_service.py`)
- CLI (Typer) wiring for every `learn` subcommand listed in the
  Quickstart above (`learning_os/cli.py`)
- Seed vertical-slice content (7 real concepts across 3 modules,
  10–15 items, 2 real research-note applications — `content/*.yaml`)
  + idempotent loader (`learning_os/services/seed_loader.py`)
- End-to-end integration test covering the full M0 acceptance path —
  drill → leech/repair → recall → apply → promote_to_usable → review
  selection → apply (2 more SUCCESS cases) → promote_to_stable → retire
  — against the real `content/` seed, asserting the resulting
  `status_events`/`attempts`/`applications`/`concept_sources` rows are a
  complete, traceable record (`tests/test_end_to_end.py`)

## Known limitations / deferred to later milestones

- `learn backup` / `learn restore` CLI commands don't exist yet — the
  underlying service (`backup_service.backup_database()`/
  `restore_database()`) is implemented and tested, but only reachable
  from Python today (see "Backup & restore" above); only `learn export`
  (JSON dump) is CLI-wired so far.
- No Markdown syllabus importer yet (M1: import report, source
  location/hash, duplicate warning, PROPOSED→QUEUED confirmation flow,
  `focus_state`/phase gate, CLI Next Best Actions) — `learn seed` only
  replays already-reviewed YAML, it does not parse the original syllabus
  Markdown files (`投资技术学习清单.md`, `投资知识补充syllabus2.md`) at all.
- Grader breadth is a deliberately small M0 subset (M2 scope: more
  numeric/unit/symbolic/discrimination edge cases and boundary tests
  beyond the KV cache/parameter memory/FLOPs concepts already covered).
- No web UI (M4 scope, gated on pilot evidence that CLI navigation cost
  is actually a problem).
- No 3–4 week real-usage pilot has been run yet (M5) — the pilot metrics
  in plan section 15.2/16 (weekly usage frequency, overhead %, real
  application evidence count, etc.) have not been measured against real
  usage.

This is now a runnable end-to-end tool, not just a verified backend —
see the Quickstart above for the exact commands that were smoke-tested
against a fresh SQLite file while writing this README.
