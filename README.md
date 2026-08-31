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

As of the last verified run: **280/280 tests passing**. Re-run the
command above yourself before trusting this number — it can drift with
every commit.

## Quickstart (CLI)

Once installed (see Setup above), the `learn` console-script is on your
`PATH` inside the venv. This is the full `QUEUED → ACTIVE → USABLE →
STABLE → RETIRED` lifecycle from a clean environment, seeding the real
vertical-slice content shipped in this repo's `content/` directory — every
command below was re-run against a fresh temp SQLite file on 2026-08-30
and confirmed to work exactly as shown (see "What's implemented" below for
the earlier README claim about this quickstart that turned out **not** to
be true, and how it was fixed):

```bash
source .venv/bin/activate
learn init                                  # creates data/learning.db
learn seed --content-dir content            # loads modules/sources/concepts/items/applications
learn status kv-cache                       # QUEUED

learn drill kv-cache --answer 21.47         # PASS attempt; auto-advances QUEUED -> ACTIVE
learn status kv-cache                       # ACTIVE

learn apply kv-cache --ref "real application note"      # PARTIAL evidence, unlocks USABLE gate
learn promote kv-cache --to usable --reason "core rubric atom passed + evidence on file"
learn status kv-cache                       # USABLE

learn recall kv-cache --answer 21.47        # delayed-recall PASS, required for the STABLE gate
learn apply kv-cache --ref "case A" --strong --result SUCCESS   # 1st distinct SUCCESS case
learn apply kv-cache --ref "case B" --strong --result SUCCESS   # 2nd distinct SUCCESS case
learn promote kv-cache --to stable --reason "delayed recall + two distinct SUCCESS cases + strong evidence"
learn status kv-cache                       # STABLE

learn review                                # today's due-for-review batch (12 item / 20 min budget)
learn retire kv-cache --reason "pausing active review"
learn status kv-cache                       # RETIRED

learn export --out ./export_out             # dumps every runtime table to JSON
```

Notes on the commands above:

- `learn drill` / `learn recall` auto-advance a `QUEUED` concept to
  `ACTIVE` the first time you run them — this is treated as your explicit
  act of starting to work the concept, not a silent transition (plan 6.3).
  They also write the attempt's outcome into `review_state`, so `learn
  review` actually reflects what you've drilled instead of always showing
  an empty queue.
- `--ref` on `learn apply` must be a **distinct** string per case you want
  counted separately toward the STABLE gate's "2 different cases" proxy —
  submitting the same `--ref` text twice only counts once (whitespace-
  trimmed comparison).
- `--result SUCCESS` on `learn apply` is required for a case to count
  toward that same STABLE gate; the default is `UNASSESSED`, which does
  not count.
- `learn promote --to usable|stable` is the only CLI path that actually
  moves `workflow_status` forward past `ACTIVE`; recording an application
  with `learn apply` by itself does not advance the concept.
- Right after `promote --to stable`, `learn review` reporting "No items
  due for review" is expected, not a bug — a PASS attempt schedules the
  item roughly a day out, so it legitimately has nothing due yet.
- If an item gets 3 consecutive MISS/MISCONCEPTION outcomes it is
  "leeched" (suspended from scheduling); `learn drill`/`learn recall`
  against it will report this and point you at `learn repair
  <concept-slug> [--answer ...]`, which confirms the repair and,
  optionally, records one more attempt in the same command.

`--db <path>` is a top-level option that works before any subcommand
(default: `data/learning.db`, relative to the current working directory):

```bash
learn --db /tmp/scratch.db init
```

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

## What's implemented (M0 vertical slice)

Every M0 acceptance item from `Personal_Learning_OS_v1_Tech_Plan.md`
section 14 is done, each backed by its own TDD suite. **Status note
(2026-08-30):** an earlier version of this README claimed the CLI layer
was fully closed based on the service-level test suite passing. An owner
audit that day showed this was false — running the quickstart above by
hand, `drill` never advanced `workflow_status` past `QUEUED`, `review`
always reported an empty queue, and `retire` failed outright, because no
CLI command ever called `set_status()`/`promote_to_usable()`/
`promote_to_stable()`. That gap has since been closed (see "CLI (Typer)
wiring" below) and is now covered by a real subprocess-style CLI test
(`tests/test_cli_e2e.py`) in addition to the service-level test — the
quickstart above is the actual, re-verified command chain.

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
  application rows, never bypassable by a hand-written reason string;
  STABLE's "delayed recall" proxy requires the recalled item to have an
  earlier non-recall attempt, and its "2 different cases" proxy dedupes
  by trimmed `reference` text, so neither can be satisfied by a single
  exposure or a repeated submission — 2026-08-30 audit fix)
  (`learning_os/services/application_service.py`)
- Next Best Actions recommendation service
  (`learning_os/services/recommendation_service.py`)
- SQLite single-file backup/restore (service-level, see "Backup &
  restore" above) and JSON/CSV export
  (`learning_os/services/backup_service.py`)
- CLI (Typer) wiring for every `learn` subcommand listed in the
  Quickstart above, **including `learn promote` and `learn repair`**
  (added 2026-08-30) — before these existed, `promote_to_usable()`,
  `promote_to_stable()`, and `ReviewService.confirm_repair()` had no CLI
  entry point at all, and `drill`/`recall` never wrote to `review_state`
  or advanced `workflow_status`, so the CLI could record evidence via
  `apply` but never act on it (`learning_os/cli.py`)
- Seed vertical-slice content (7 real concepts across 3 modules,
  10–15 items, 2 evidence-backed applications — one PARTIAL, one pair of
  STRONG applications recorded live in `tests/test_end_to_end.py`;
  `content/applications.yaml`'s seed rows were downgraded from STRONG to
  PARTIAL on 2026-08-30 because they are unverified personal-research
  recollections with no locatable episode/file artifact, not checkable
  records — `content/*.yaml`) + idempotent loader
  (`learning_os/services/seed_loader.py`)
- End-to-end integration tests covering the full M0 acceptance path at
  two layers:
  - service layer (`tests/test_end_to_end.py`): drill → leech/repair →
    recall → apply → promote_to_usable → review selection → apply
    (2 more SUCCESS cases) → promote_to_stable → retire, asserting the
    resulting `status_events`/`attempts`/`applications`/`concept_sources`
    rows are a complete, traceable record
  - CLI layer (`tests/test_cli_e2e.py`, added 2026-08-30): the same
    lifecycle driven exclusively through Typer's `CliRunner` (no service-
    layer shortcuts), proving the commands in the Quickstart above
    actually work, not just the services behind them

## Known limitations / deferred to later milestones

- `learn backup` / `learn restore` CLI commands don't exist yet — the
  underlying service (`backup_service.backup_database()`/
  `restore_database()`) is implemented and tested, but only reachable
  from Python today (see "Backup & restore" above); only `learn export`
  (JSON dump) is CLI-wired so far. Plan section 14's M0 acceptance
  criterion literally asks for "SQLite 单文件 backup 和 JSON export 的最小
  命令可用" — the backup/restore *service* meets this, but there is no
  minimal *CLI command* for backup/restore yet, so this line item is only
  partially satisfied at the CLI layer.
- `seed_database()` (`learning_os/services/seed_loader.py`) is not
  transactional — each repository's `create()` call commits independently
  as modules/sources/concepts/items/applications are inserted in
  sequence. If seeding fails partway through (e.g. malformed YAML further
  down the file, or a DB error), the rows already committed before the
  failure point remain in the database — there is no preflight validation
  of the whole YAML set and no all-or-nothing transaction wrapping the
  five insert loops. Rerunning `learn seed` against the same DB is
  idempotent for rows that already exist (matched by prompt/reference),
  so a fresh `learn init` + `learn seed` from scratch is the safe recovery
  path if a seed run is suspected to have failed partway (2026-08-30 audit
  finding, not yet fixed).
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

This is a runnable end-to-end CLI tool with both service-level and
CLI-level tests behind the full drill→retire lifecycle — see the
Quickstart above for the exact commands, which were re-run against a
fresh SQLite file on 2026-08-30 and match `tests/test_cli_e2e.py`'s
assertions. See "Known limitations" above for what is still genuinely
missing (backup/restore CLI commands, seed transactionality, syllabus
import, broader grader coverage, web UI, real-usage pilot).
