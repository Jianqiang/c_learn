# c_learn — Personal Learning OS (v1)

Local-first, concept-centric learning workbench. See
`Personal_Learning_OS_v1_Tech_Plan.md` for the full design.

## 当前模式：Deliberate Practice Bootcamp v3 — module 制（M0-M7）

Manifest：`content/bootcamp_modules.yaml`（8 module，知识优先）
进度状态：`data/module_progress.yaml`
产物：`outputs/`
**AI 协作契约：`AGENTS.md`** — 任何 agent session 开始前必须先读

```bash
.venv/bin/python scripts/modules.py status       # module 总览
.venv/bin/python scripts/modules.py show M0      # 单个 module 详情
.venv/bin/python scripts/modules.py log M0 --hours 2.5 --kind material --note "..."
.venv/bin/python scripts/modules.py forecast add M7 "..." --metric "..." --threshold "..." --resolves 2027-06-30 --source "..."
.venv/bin/python scripts/modules.py dashboard    # 生成 outputs/dashboard.html
```

核心约束：AI 永远晚于用户的第一次 attempt；概念要能跨公司迁移；Phase A（M0-M7）知识优先，
真正的闭卷/迁移/下注检验留给 Phase B（80% 真实候选 underwriting）。

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

As of the last verified run: **318/318 tests passing**. Re-run the
command above yourself before trusting this number — it can drift with
every commit.

## Quickstart (CLI)

Once installed (see Setup above), the `learn` console-script is on your
`PATH` inside the venv. This is the full `QUEUED → ACTIVE → USABLE →
STABLE → RETIRED` lifecycle from a clean environment, seeding the real
vertical-slice content shipped in this repo's `content/` directory — every
command below was re-run against a fresh temp SQLite file on 2026-08-31
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

learn backup                                # data/backups/learning_<timestamp>.db, a restorable copy
learn export --out ./export_out             # dumps every runtime table to JSON
```

## Active core curriculum

The active learning basis is the 16-week project-led curriculum in
[`content/core_curriculum.yaml`](/Users/jma/PycharmProjects/c_learn/content/core_curriculum.yaml).
It starts on 2026-08-31 (the current calendar week) and follows:

`Tech Change → Constraint → Architecture → Rent → Capital Response → FCF → Expectations → Position`

Each week is a bounded plan for selective learning, one real project,
decision reps, and one output. The manifest is orchestration metadata: it
does not create concepts, queue every source, or claim mastery. Use the CLI
to see the current week or inspect another week:

```bash
learn curriculum show
learn curriculum show --week 8
learn curriculum show --date 2026-09-04
```

Then explicitly connect the week's work to the existing OS with `learn
focus set`, `learn import approve`, `learn drill`/`recall`, `learn apply`,
and `learn output complete` as evidence becomes available.

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

```bash
learn backup                                # -> data/backups/learning_<YYYYMMDD_HHMMSS>.db
learn backup --out /tmp/my-backups          # custom backup directory
learn restore data/backups/learning_20260101_090000.db   # overwrites the current --db target
```

`learn backup` (added 2026-08-31 — before this, backup/restore was only
reachable from Python, see below) uses SQLite's own online backup API
(`sqlite3.Connection.backup()`), so it is safe to run even with a session
in flight elsewhere against the same file — it copies page-by-page under
SQLite's own locking rather than risking a raw file copy mid-write.
`--out` defaults to `backups/` next to the current `--db` path (matching
plan 13.2's suggested `data/backups/` layout).

`learn restore <backup-path>` refuses to treat an arbitrary file as a
backup: it raises a clean `Error: ...` (not a traceback) if the path
doesn't exist, or if it exists but isn't a SQLite file with this
project's `schema_migrations` table — a path typo fails loudly instead of
silently producing a target database that breaks on the first real query.

The same logic is also available directly from Python if you need it
outside the CLI (e.g. scripting a backup rotation):

```python
from datetime import datetime
from learning_os.db import init_db
from learning_os.services.backup_service import backup_database, restore_database

conn = init_db("data/learning.db")
backup_database(conn, "data/backups", now=datetime.now())   # -> data/backups/learning_<timestamp>.db
restore_database("data/backups/learning_20260101_090000.db", "data/learning_restored.db")
```

## Importing a Markdown syllabus (M1)

`learn import syllabus <path>` parses a hand-written Markdown syllabus
(the two real files in this repo's root, `投资技术学习清单.md` and
`投资知识补充syllabus2.md`, are the M1 fixture target) and persists every
module/source/learning-output it finds as `PROPOSED` drafts — nothing it
creates is scheduled for review yet. Idempotent by (source file, heading
line) + a content hash, so re-running it against an unmodified file is a
no-op, and re-running it after you edit the Markdown only touches the
sections that actually changed:

```bash
learn import syllabus "投资技术学习清单.md"
learn import syllabus "投资知识补充syllabus2.md"
```

Each run prints a full `ImportReport`: created/updated/skipped counts,
duplicate-title candidates (e.g. a paper referenced from both files),
unresolved headings the parser could not confidently classify, and
warnings for every lower-confidence guess it made (inferred
`resource_mode`/`pace_mode`, extracted `scope_note`, unlabeled H2
headings treated as low-confidence sources, slug collisions between two
distinct CJK titles, etc.). Nothing on that list is applied silently —
review it, then explicitly approve the sources you actually want to
start working through:

```bash
learn import approve <source-slug-or-id>                    # PROPOSED -> QUEUED
learn import approve <source-slug-or-id> --confirm-scope     # also confirms an extracted scope_note
```

`<source-slug-or-id>` accepts either the slug (most sources get one) or
the numeric row id — the importer intentionally leaves `slug` unset
rather than guessing a disambiguating suffix whenever two distinct
titles would otherwise collapse to the same ASCII slug (real example:
"Codex：我认为长期价值反而最大" and "让 Codex 做哪些工作？" both slugify
to `codex`), so an id-based lookup is the only way to address those rows.
`--confirm-scope` is required whenever the importer extracted a
`scope_note` candidate (e.g. "不完整刷，只看第三章") — `set_status()`
refuses to queue a source with `scope_confirmed=False`, exactly the same
gate `learn apply`/`learn promote` rely on elsewhere, so a source with an
unreviewed scope restriction can never silently start consuming normal
review budget.

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
- SQLite single-file backup/restore, now CLI-wired via `learn backup`/
  `learn restore` (added 2026-08-31 — before this only the underlying
  service functions existed, with no CLI command reaching them at all),
  plus JSON/CSV export (`learning_os/services/backup_service.py`)
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
  records — `content/*.yaml`) + an idempotent, **atomic** loader
  (`learning_os/services/seed_loader.py`) — `seed_database()` wraps every
  repository/service call in a deferred-commit proxy and only flushes a
  single real commit if every module/source/concept/item/application
  insert succeeds; any exception rolls back the entire call instead of
  leaving already-inserted rows from earlier in the same run committed
  (2026-08-31 audit fix; `learn seed` also now reports a malformed-YAML
  failure as a clean `Error: ...` line instead of a raw traceback)
- Markdown syllabus importer (M1, plan section 8), CLI-wired via `learn
  import syllabus <path>` / `learn import approve <source-slug-or-id>
  [--confirm-scope]` — parses either real syllabus file in this repo's
  root into `PROPOSED`-draft modules/sources/learning_outputs, idempotent
  by (source_file, source_line) + content hash, with duplicate-title
  detection across files (the Teece 1986 case), an `ImportReport` printed
  in full (created/updated/skipped/duplicates/unresolved/warnings), and
  an explicit approval step before anything enters the review queue
  (`learning_os/services/syllabus_importer.py`,
  `SourceRepository.confirm_scope()`) — see "Importing a Markdown
  syllabus" above for the full command reference
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
  - CLI review scheduling, time-travel-tested (`tests/test_cli_e2e.py`'s
    `test_review_only_surfaces_an_item_once_its_due_at_has_actually_passed`,
    added 2026-08-30): `learn review` calls `datetime.now()` internally
    with no injection point and this project has no `freezegun`
    dependency, so the test instead rewrites the persisted `due_at` string
    directly in SQLite (the same format `ReviewService` itself writes) to
    simulate the clock advancing, then asserts `learn review` is silent
    before that point and correctly surfaces the item once due_at is in
    the past — proving the CLI genuinely reads and respects `due_at`
    rather than always returning everything or nothing

## Known limitations / deferred to later milestones

- `focus_state`/phase gate and CLI Next Best Actions surfacing for
  freshly imported sources are not yet wired to the importer above (M1
  scope leftover) — a `PROPOSED`/`QUEUED` source created by `learn import
  syllabus` does not yet automatically appear in `learn status`'s phase
  view or influence `learning_os/services/recommendation_service.py`'s
  suggestions the way hand-seeded content does.
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
CLI-level tests behind the full drill→retire lifecycle, a working
backup/restore command pair, and a Markdown syllabus importer with an
explicit approval gate — see the Quickstart above for the exact
commands, which were re-run against a fresh SQLite file on 2026-08-31 and
match `tests/test_cli_e2e.py`'s assertions. See "Known limitations" above
for what is still genuinely missing (Next Best Actions integration for
imported sources, broader grader coverage, web UI, real-usage pilot).
