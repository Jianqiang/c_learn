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
dependency ranges; the lock file is what actually reproduces a clean run.

## Running tests

```bash
source .venv/bin/activate
python -m pytest -q
```

As of the last verified run: **128/128 tests passing**. Re-run the
command above yourself before trusting this number — it can drift with
every commit.

## Verifying a clean working tree

```bash
git status --short
```

Should print nothing. If you see `?? .workbuddy/...`, that's the local
agent work-memory directory (gitignored, not part of the product).

## What's implemented (M0 vertical slice, in progress)

Core backend layers, each with its own TDD suite:

- SQLite schema + idempotent migration runner (`learning_os/db.py`)
- Module/Source/Concept repository layer with explicit state machines
  and audit trail (`learning_os/repositories.py`)
- Level-1 deterministic grader: numeric/unit/symbolic/discrimination
  (`learning_os/graders/deterministic.py`)
- Level-2 rubric grader + manual/LLM-assisted adjudication
  (`learning_os/graders/rubric.py`)
- Session & attempt service with interrupt-safe resume
  (`learning_os/services/session_service.py`)
- Baseline review scheduler (1/3/7/14/30-day ladder, leech detection)
  + budget-aware review service
  (`learning_os/schedulers/baseline.py`,
  `learning_os/services/review_service.py`)

## Not yet implemented

- Applications & concept status evidence gates (USABLE/STABLE/RETIRED)
- Next Best Actions recommendation service (P1–P4 rules)
- Backup / export commands
- CLI (Typer) wiring for `learn` subcommands
- Seed vertical-slice content (YAML) + loader
- End-to-end integration test (full M0 acceptance flow)

Until the CLI, seed content, and end-to-end test land, this is a
verified backend, not yet a runnable end-user tool.
