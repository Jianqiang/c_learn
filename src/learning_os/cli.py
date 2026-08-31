"""Typer CLI (plan 12.1): the process-level entry point wired to the shared
service/repository layer. Deliberately thin: every command resolves the
database connection, instantiates the relevant repository/service, calls
it, prints a human-readable line, and closes the connection. No business
rule lives here -- evidence gates, state machines, scheduling math and
grading all stay in services/repositories/graders/schedulers, exactly as
plan 12.2 requires ("CLI 和 Web 必须调用相同的 service layer") so a future
Web layer can reuse the same calls without duplicating logic.

`--db` is a *top-level* option (e.g. `learn --db path.db focus set foo`,
not `learn focus set foo --db path.db`) so it works uniformly whether the
target command lives directly on `app` or on a nested Typer group (`focus
set`, `output list`/`output complete`). It is read once in the root
callback and stashed on `ctx.obj`; Click contexts inherit `obj` from their
parent by default, so nested groups see the same value with no extra
plumbing.

Minimal experience bar this module exists to satisfy (plan 12.1):
"一次命令能继续 session；中断后不丢 attempt；没有 LLM 时 drill/recall/manual
adjudication 仍能完成." start_or_resume()/record_attempt() (session_service)
already provide the first two guarantees; every grading path used below
(graders.deterministic) is LLM-free, satisfying the third.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

import typer
import yaml

from learning_os import config
from learning_os.db import init_db
from learning_os.graders.deterministic import grade_discrimination, grade_numeric, grade_symbolic
from learning_os.repositories import (
    ConceptRepository,
    FocusRepository,
    InvalidTransitionError,
    ItemRepository,
    LearningOutputRepository,
    ModuleRepository,
    Source,
    SourceRepository,
)
from learning_os.services import backup_service
from learning_os.services.application_service import ApplicationService, EvidenceGateError
from learning_os.services.review_service import ReviewService
from learning_os.services.seed_loader import seed_database
from learning_os.services.session_service import SessionService
from learning_os.services.syllabus_importer import ImportReport, import_syllabus

app = typer.Typer(add_completion=False, no_args_is_help=True)
output_app = typer.Typer(add_completion=False, no_args_is_help=True)
focus_app = typer.Typer(add_completion=False, no_args_is_help=True)
import_app = typer.Typer(add_completion=False, no_args_is_help=True)
app.add_typer(output_app, name="output")
app.add_typer(focus_app, name="focus")
app.add_typer(import_app, name="import")


@app.callback()
def main(
    ctx: typer.Context,
    db: Optional[str] = typer.Option(
        None, "--db", help="Database file path (default: data/learning.db)."
    ),
):
    """Personal Learning OS CLI. `--db` applies to every subcommand below."""
    ctx.obj = {"db": db}


def _db_from_ctx(ctx: typer.Context) -> Optional[str]:
    return (ctx.obj or {}).get("db")


def _connect(ctx: typer.Context) -> sqlite3.Connection:
    return init_db(config.resolve_db_path(_db_from_ctx(ctx)))


def _fail(message: str) -> None:
    """Print an error to stderr and exit non-zero, the one error-reporting
    convention every command below uses so tests can assert on `not found`/
    validation messages consistently regardless of which command raised."""
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=1)


def _resolve_concept_or_module(conn: sqlite3.Connection, slug: str):
    """Try concept first, then module -- concepts are the more common CLI
    target (drill/recall/apply/retire all address concepts), so checking
    them first avoids a wasted lookup in the common case."""
    concepts = ConceptRepository(conn)
    try:
        return "concept", concepts.get_by_slug(slug)
    except KeyError:
        pass
    modules = ModuleRepository(conn)
    try:
        return "module", modules.get_by_slug(slug)
    except KeyError:
        raise KeyError(f"'{slug}' is neither a known module nor concept slug")


# ---------------------------------------------------------------------------
# learn init
# ---------------------------------------------------------------------------

@app.command()
def init(ctx: typer.Context):
    """Initialize (or upgrade) the SQLite database. Safe to re-run."""
    path = config.resolve_db_path(_db_from_ctx(ctx))
    conn = init_db(path)
    conn.close()
    typer.echo(f"Database ready at {path}")


# ---------------------------------------------------------------------------
# learn seed --content-dir <path>
# ---------------------------------------------------------------------------

@app.command()
def seed(
    ctx: typer.Context,
    content_dir: str = typer.Option(
        "content", "--content-dir",
        help="Directory with modules.yaml/sources.yaml/concepts/*.yaml/items/*.yaml "
        "(plan 5.3 vertical-slice seed content, 13.2 suggested layout).",
    ),
):
    """Load hand-authored YAML seed content (plan 5.3) into the database.

    Idempotent by slug for modules/sources/concepts and by (concept, prompt)
    for items -- safe to re-run after `learn init` without duplicating rows.
    This is distinct from `learn import syllabus` (plan section 8's Markdown
    importer with ImportReport/dedup/content-hash, M1 scope): `seed` only
    replays already-reviewed YAML, it does not parse or interpret the
    original syllabus Markdown files at all.
    """
    conn = _connect(ctx)
    try:
        try:
            result = seed_database(conn, content_dir)
        except (KeyError, ValueError, yaml.YAMLError) as exc:
            # seed_database() is transactional (2026-08-31 audit fix): any
            # exception here has already rolled back every row from this
            # call, so the database is left exactly as it was before `seed`
            # ran. Report this plainly instead of a raw traceback -- and
            # confirm the "no partial rows left behind" guarantee so the
            # user does not have to inspect the DB by hand to trust it.
            _fail(
                f"seed content in {content_dir!r} is malformed ({exc}) -- "
                "no rows were written (seed_database is all-or-nothing); "
                "fix the YAML and re-run `learn seed`"
            )
            return
        typer.echo(
            f"Seeded from {content_dir}: modules={result.modules_created} "
            f"sources={result.sources_created} concepts={result.concepts_created} "
            f"items={result.items_created} applications={result.applications_created}"
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# learn focus set
# ---------------------------------------------------------------------------

@focus_app.command("set")
def focus_set(
    ctx: typer.Context,
    slug: str = typer.Argument(..., help="Module or concept slug to focus on."),
    rationale: Optional[str] = typer.Option(None, "--reason", help="Why this focus."),
):
    """Set the current focus to a module or concept, by slug."""
    conn = _connect(ctx)
    try:
        try:
            target_type, target = _resolve_concept_or_module(conn, slug)
        except KeyError as exc:
            _fail(str(exc))
            return
        focus_repo = FocusRepository(conn)
        current = focus_repo.get_current()
        current_phase = current.current_phase if current else 1
        focus = focus_repo.set_focus(
            current_phase=current_phase,
            target_type=target_type,
            target_id=target.id,
            rationale=rationale,
        )
        typer.echo(f"Focus set: {target_type} '{slug}' (phase {focus.current_phase})")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# learn status [<slug>]
# ---------------------------------------------------------------------------

@app.command()
def status(
    ctx: typer.Context,
    slug: Optional[str] = typer.Argument(None, help="Module or concept slug."),
):
    """Show module/concept status. With no slug, lists every module."""
    conn = _connect(ctx)
    try:
        if slug is None:
            rows = conn.execute(
                "SELECT slug, name, phase, status FROM modules ORDER BY id ASC"
            ).fetchall()
            if not rows:
                typer.echo("No modules yet.")
                return
            for m_slug, name, phase, m_status in rows:
                typer.echo(f"[module] {m_slug}  {name}  phase={phase}  {m_status}")
            return

        try:
            target_type, target = _resolve_concept_or_module(conn, slug)
        except KeyError as exc:
            _fail(str(exc))
            return

        if target_type == "concept":
            typer.echo(f"[concept] {target.slug}  {target.name}  {target.workflow_status}")
        else:
            typer.echo(f"[module] {target.slug}  {target.name}  phase={target.phase}  {target.status}")
            concept_rows = conn.execute(
                "SELECT slug, name, workflow_status FROM concepts "
                "WHERE module_id=? ORDER BY id ASC",
                (target.id,),
            ).fetchall()
            for c_slug, c_name, c_status in concept_rows:
                typer.echo(f"  [concept] {c_slug}  {c_name}  {c_status}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Shared drill/recall implementation
# ---------------------------------------------------------------------------

def _run_deterministic_session(
    conn: sqlite3.Connection,
    *,
    session_type: str,
    concept_slug: str,
    answer: str,
):
    from datetime import datetime

    concepts = ConceptRepository(conn)
    try:
        concept = concepts.get_by_slug(concept_slug)
    except KeyError:
        _fail(f"concept '{concept_slug}' not found")
        return

    items = ItemRepository(conn).list_by_concept(concept.id)
    if not items:
        _fail(f"concept '{concept_slug}' has no active items to {session_type}")
        return
    item = items[0]

    # A QUEUED concept has never been worked on. Running drill/recall against
    # it is itself the user's explicit act of starting to build/repair it
    # (plan 6.3: "当前正在建立或修复"), so this is not the "系统不得静默改变
    # concept 状态" violation plan 6.3 forbids -- the user just ran this
    # exact command. This was previously missing entirely: the CLI drill/
    # recall path never touched workflow_status at all, so a freshly seeded
    # concept stayed QUEUED forever no matter how many drills were run
    # against it, making every later `learn promote`/`learn retire` fail
    # (2026-08-30 audit finding, P0).
    if concept.workflow_status == "QUEUED":
        concepts.set_status(concept.id, "ACTIVE", reason=f"started via `learn {session_type}`")

    sessions = SessionService(conn)
    session = sessions.start_or_resume(session_type=session_type, target_type="concept", target_id=concept.id)

    outcome = _grade_deterministic(item, answer)
    attempt = sessions.record_attempt(session.id, item.id, answer=answer, outcome=outcome, evaluator_kind="deterministic")
    sessions.end(session.id)

    # Every graded attempt must feed the review scheduler, or review_state
    # is never created and `learn review` reports an empty queue forever
    # regardless of how much drilling happened (2026-08-30 audit finding,
    # P1: "CLI drill 没有更新 review_state"). SKIPPED is not a real outcome
    # here -- _grade_deterministic() never returns it -- so every call is a
    # real scheduling event.
    reviews = ReviewService(conn)
    try:
        reviews.record_outcome(item.id, outcome=outcome, now=datetime.now())
    except ValueError:
        # Item is already leeched (active=False) from a prior session; the
        # attempt above is still recorded, but the scheduler intentionally
        # refuses further updates until `learn repair` confirms a fix.
        typer.echo(
            f"[{session_type}] item {item.id}: {outcome} (attempt {attempt.id}) "
            "-- item is suspended pending repair; run `learn repair "
            f"{concept_slug}` before it can be scheduled again"
        )
        return

    typer.echo(f"[{session_type}] item {item.id}: {outcome} (attempt {attempt.id})")


def _grade_deterministic(item, answer: str) -> str:
    """Route to the matching Level-1 grader by item.type (plan 9.1). Only
    the subset of grading needed for a CLI smoke path -- explanation/
    counterfactual items require rubric/manual adjudication, which is out
    of scope for this synchronous one-shot command path."""
    if item.type == "numeric":
        try:
            return grade_numeric(answer=float(answer), reference=float(item.reference_answer))
        except (TypeError, ValueError):
            return "MISS"
    if item.type == "symbolic":
        return grade_symbolic(answer=answer, reference=item.reference_answer)
    if item.type == "discrimination":
        return grade_discrimination(answer=answer, correct=item.reference_answer)
    # unit-graded items encode "unit" via difficulty/rubric metadata that v1
    # doesn't fully model yet; fall back to a MISS with no crash rather than
    # a strict grader mismatch blocking the CLI's minimal smoke path.
    return "MISS"


# ---------------------------------------------------------------------------
# learn drill <concept-slug>
# ---------------------------------------------------------------------------

@app.command()
def drill(
    ctx: typer.Context,
    concept_slug: str = typer.Argument(...),
    answer: str = typer.Option(..., "--answer", help="Answer for the first active item."),
):
    """Run one deterministic drill item for a concept (no LLM required)."""
    conn = _connect(ctx)
    try:
        _run_deterministic_session(conn, session_type="drill", concept_slug=concept_slug, answer=answer)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# learn learn <source-slug>
# ---------------------------------------------------------------------------

@app.command("learn")
def learn_source(
    ctx: typer.Context,
    source_slug: str = typer.Argument(...),
    output: Optional[str] = typer.Option(None, "--output", help="Free-text user_output for this session."),
):
    """Record that a source was learned: opens a `learn` session, marks the
    source CONSUMED, and ends the session with the optional output note."""
    conn = _connect(ctx)
    try:
        sources = SourceRepository(conn)
        try:
            source = sources.get_by_slug(source_slug)
        except KeyError:
            _fail(f"source '{source_slug}' not found")
            return

        sessions = SessionService(conn)
        session = sessions.start_or_resume(session_type="learn", target_type="source", target_id=source.id)
        try:
            sources.set_status(source.id, "CONSUMED", reason="learned via `learn learn`")
        except InvalidTransitionError as exc:
            _fail(str(exc))
            return
        sessions.end(session.id, user_output=output)
        typer.echo(f"Source '{source_slug}' marked CONSUMED (session {session.id})")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# learn recall <concept-or-source-slug>
# ---------------------------------------------------------------------------

@app.command()
def recall(
    ctx: typer.Context,
    slug: str = typer.Argument(...),
    answer: str = typer.Option(..., "--answer"),
):
    """Closed-book recall check for a concept's first active item."""
    conn = _connect(ctx)
    try:
        _run_deterministic_session(conn, session_type="recall", concept_slug=slug, answer=answer)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# learn review
# ---------------------------------------------------------------------------

@app.command()
def review(ctx: typer.Context):
    """Show the current review batch (plan 10.5 selection, 10.1 budget)."""
    from datetime import datetime

    conn = _connect(ctx)
    try:
        review_service = ReviewService(conn)
        selected = review_service.select_batch(now=datetime.now())
        if not selected:
            typer.echo("No items due for review.")
            return
        for entry in selected:
            flag = " [budget exception]" if entry.budget_exception else ""
            typer.echo(f"item {entry.item_id}: {entry.reason}{flag}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# learn apply <concept-slug> --ref "..."
# ---------------------------------------------------------------------------

@app.command()
def apply(
    ctx: typer.Context,
    concept_slug: str = typer.Argument(...),
    ref: str = typer.Option(..., "--ref", help="Reference describing the application."),
    strong: bool = typer.Option(False, "--strong", help="Mark as STRONG evidence (real research/case)."),
    result: str = typer.Option(
        "UNASSESSED", "--result",
        help="SUCCESS/PARTIAL/FAILURE/UNASSESSED. promote_to_stable()'s "
             "'2 different cases' gate only counts result=SUCCESS rows, so "
             "this must be set explicitly to ever reach STABLE via the CLI "
             "-- previously there was no way to set it at all here.",
    ),
):
    """Record an application of a concept to a real problem or output."""
    conn = _connect(ctx)
    try:
        concepts = ConceptRepository(conn)
        try:
            concept = concepts.get_by_slug(concept_slug)
        except KeyError:
            _fail(f"concept '{concept_slug}' not found")
            return
        applications = ApplicationService(conn)
        try:
            application = applications.record_application(
                concept_id=concept.id,
                evidence_level="STRONG" if strong else "PARTIAL",
                reference=ref,
                result=result,
            )
        except ValueError as exc:
            _fail(str(exc))
            return
        typer.echo(
            f"Application recorded for '{concept_slug}': "
            f"{application.evidence_level} (application {application.id})"
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# learn promote <concept-slug> --to usable|stable
# ---------------------------------------------------------------------------

@app.command()
def promote(
    ctx: typer.Context,
    concept_slug: str = typer.Argument(...),
    to: str = typer.Option(..., "--to", help="Target status: usable or stable."),
    reason: Optional[str] = typer.Option(None, "--reason", help="Why this concept is ready."),
    confirm_stable: bool = typer.Option(
        False, "--confirm-stable",
        help="User explicitly confirms stability, bypassing the 2-case count "
             "requirement (plan 6.4's escape hatch). Only relevant for --to stable.",
    ),
):
    """Promote a concept across its evidence-gated states (plan 6.4):
    ACTIVE -> USABLE or USABLE -> STABLE. This is the CLI's only entry point
    to ApplicationService.promote_to_usable()/promote_to_stable() -- before
    this command existed, those gates were only reachable from the service
    layer or a test, never from `learn` itself (2026-08-30 audit finding,
    P0), so `learn apply` could record evidence but nothing in the CLI
    could ever act on it to advance workflow_status."""
    to_normalized = to.strip().upper()
    if to_normalized not in {"USABLE", "STABLE"}:
        _fail(f"--to must be 'usable' or 'stable', got {to!r}")
        return

    conn = _connect(ctx)
    try:
        concepts = ConceptRepository(conn)
        try:
            concept = concepts.get_by_slug(concept_slug)
        except KeyError:
            _fail(f"concept '{concept_slug}' not found")
            return
        applications = ApplicationService(conn)
        try:
            if to_normalized == "USABLE":
                updated = applications.promote_to_usable(concept.id, reason=reason)
            else:
                updated = applications.promote_to_stable(
                    concept.id, reason=reason, user_confirms_stable=confirm_stable,
                )
        except (EvidenceGateError, InvalidTransitionError) as exc:
            _fail(str(exc))
            return
        typer.echo(f"Concept '{concept_slug}' -> {updated.workflow_status}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# learn repair <concept-slug>
# ---------------------------------------------------------------------------

@app.command()
def repair(
    ctx: typer.Context,
    concept_slug: str = typer.Argument(...),
    answer: Optional[str] = typer.Option(
        None, "--answer",
        help="If given, also records a fresh attempt on the leeched item "
             "before confirming repair (a common real workflow: fix the "
             "misunderstanding, then immediately re-attempt it).",
    ),
):
    """Confirm a leeched item has been repaired (plan 10.4: 'rewrite item /
    split concept / add source / manual / retire item' is the human choice
    this command records having been made), putting it back on the 1-day
    ladder. Before this command existed, ReviewService.confirm_repair() had
    no CLI entry point at all, so a leeched item (3 consecutive MISS, or
    4-of-5 non-PASS) could never be reviewed again via the CLI (2026-08-30
    audit finding, related to P1 'CLI drill 没有更新 review_state')."""
    from datetime import datetime

    conn = _connect(ctx)
    try:
        concepts = ConceptRepository(conn)
        try:
            concept = concepts.get_by_slug(concept_slug)
        except KeyError:
            _fail(f"concept '{concept_slug}' not found")
            return
        items = ItemRepository(conn).list_by_concept(concept.id)
        if not items:
            _fail(f"concept '{concept_slug}' has no items to repair")
            return
        item = items[0]

        reviews = ReviewService(conn)
        try:
            state = reviews.confirm_repair(item.id, now=datetime.now())
        except KeyError:
            _fail(f"item {item.id} has no review_state yet -- nothing to repair")
            return
        except ValueError as exc:
            _fail(str(exc))
            return

        if answer is not None:
            sessions = SessionService(conn)
            session = sessions.start_or_resume(
                session_type="drill", target_type="concept", target_id=concept.id,
            )
            outcome = _grade_deterministic(item, answer)
            attempt = sessions.record_attempt(
                session.id, item.id, answer=answer, outcome=outcome,
                evaluator_kind="deterministic",
            )
            sessions.end(session.id)
            state = reviews.record_outcome(item.id, outcome=outcome, now=datetime.now())
            typer.echo(
                f"Item {item.id} repaired and re-attempted: {outcome} "
                f"(attempt {attempt.id}); due {state.due_at}"
            )
        else:
            typer.echo(f"Item {item.id} repaired; back on the review ladder (due {state.due_at})")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# learn output list [<module-slug>]
# ---------------------------------------------------------------------------

@output_app.command("list")
def output_list(
    ctx: typer.Context,
    module_slug: Optional[str] = typer.Argument(None),
):
    """List learning_outputs, optionally filtered to one module."""
    conn = _connect(ctx)
    try:
        outputs_repo = LearningOutputRepository(conn)
        if module_slug is not None:
            modules = ModuleRepository(conn)
            try:
                module = modules.get_by_slug(module_slug)
            except KeyError:
                _fail(f"module '{module_slug}' not found")
                return
            outputs = outputs_repo.list_by_module(module.id)
        else:
            module_ids = [row[0] for row in conn.execute("SELECT id FROM modules ORDER BY id ASC").fetchall()]
            outputs = [o for mid in module_ids for o in outputs_repo.list_by_module(mid)]

        if not outputs:
            typer.echo("No learning outputs yet.")
            return
        for o in outputs:
            typer.echo(f"[{o.id}] {o.title}  {o.status}  kind={o.kind}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# learn output complete <output-id> --ref "..."
# ---------------------------------------------------------------------------

@output_app.command("complete")
def output_complete(
    ctx: typer.Context,
    output_id: int = typer.Argument(...),
    ref: str = typer.Option(..., "--ref", help="Reference to the completed output artifact."),
):
    """Explicitly complete a learning output by submitting its reference.

    Never triggered automatically by a source being CONSUMED (plan 7.2) --
    this command is the only path that reaches SUBMITTED.
    """
    conn = _connect(ctx)
    try:
        outputs_repo = LearningOutputRepository(conn)
        try:
            result = outputs_repo.complete(output_id, reference=ref)
        except KeyError:
            _fail(f"learning_output {output_id} not found")
            return
        except (ValueError, InvalidTransitionError) as exc:
            _fail(str(exc))
            return
        typer.echo(f"Output {result.id} '{result.title}' -> {result.status} (ref={result.reference})")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# learn retire <concept-slug>
# ---------------------------------------------------------------------------

@app.command()
def retire(
    ctx: typer.Context,
    concept_slug: str = typer.Argument(...),
    reason: Optional[str] = typer.Option(None, "--reason", help="Required: why review is stopping."),
):
    """Retire a concept from active review (plan 6.4: requires an explicit
    reason -- there is no automated signal for this confirmation)."""
    conn = _connect(ctx)
    try:
        concepts = ConceptRepository(conn)
        try:
            concept = concepts.get_by_slug(concept_slug)
        except KeyError:
            _fail(f"concept '{concept_slug}' not found")
            return
        applications = ApplicationService(conn)
        try:
            updated = applications.retire(concept.id, reason=reason or "")
        except (EvidenceGateError, InvalidTransitionError) as exc:
            _fail(str(exc))
            return
        typer.echo(f"Concept '{concept_slug}' -> {updated.workflow_status}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# learn reactivate <concept-slug>
# ---------------------------------------------------------------------------

@app.command()
def reactivate(
    ctx: typer.Context,
    concept_slug: str = typer.Argument(...),
    reason: Optional[str] = typer.Option(None, "--reason"),
):
    """Reactivate a RETIRED concept back into the active queue."""
    conn = _connect(ctx)
    try:
        concepts = ConceptRepository(conn)
        try:
            concept = concepts.get_by_slug(concept_slug)
        except KeyError:
            _fail(f"concept '{concept_slug}' not found")
            return
        applications = ApplicationService(conn)
        try:
            updated = applications.reactivate(concept.id, reason=reason)
        except InvalidTransitionError as exc:
            _fail(str(exc))
            return
        typer.echo(f"Concept '{concept_slug}' -> {updated.workflow_status}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# learn export --out <path>
# ---------------------------------------------------------------------------

@app.command()
def export(
    ctx: typer.Context,
    out: str = typer.Option(..., "--out", help="Output directory for JSON export."),
    ):
    """Export every runtime table to `<out>/<table>.json` (plan 7.1, 12.1)."""
    conn = _connect(ctx)
    try:
        written = backup_service.export_json(conn, out)
        typer.echo(f"Exported {len(written)} tables to {Path(out)}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# learn backup [--out <dir>] / learn restore <backup-path>
# ---------------------------------------------------------------------------
#
# backup_service.backup_database()/restore_database() have existed and been
# unit-tested since M0 (tests/test_backup_export.py), but no CLI command
# ever called them (2026-08-31 audit finding, P2) -- `learn export` (JSON
# dump) was the only CLI-wired path, so plan 14's M0 acceptance line "SQLite
# 单文件 backup 和 JSON export 的最小命令可用" was only half-satisfied: the
# backup *service* existed, the backup *command* did not.

@app.command()
def backup(
    ctx: typer.Context,
    out: Optional[str] = typer.Option(
        None, "--out",
        help="Directory to write the backup file into (default: "
             "'backups/' next to the current database file, matching "
             "plan 13.2's suggested project layout).",
    ),
):
    """Write a full-fidelity, restorable SQLite backup of the current
    database to `<out>/learning_<YYYYMMDD_HHMMSS>.db` (plan 7.1: 'SQLite 单
    文件 backup，支持从 backup 恢复'). Uses sqlite3's online backup API, so
    it is safe to run even if another process has an open session against
    the same database file -- it copies page-by-page under SQLite's own
    locking rather than risking a raw file copy mid-write.
    """
    from datetime import datetime

    db_path = config.resolve_db_path(_db_from_ctx(ctx))
    backup_dir = Path(out) if out else Path(db_path).parent / "backups"

    conn = _connect(ctx)
    try:
        backup_path = backup_service.backup_database(conn, backup_dir, now=datetime.now())
    finally:
        conn.close()
    typer.echo(f"Backup written to {backup_path}")


@app.command()
def restore(
    ctx: typer.Context,
    backup_path: str = typer.Argument(
        ..., help="Path to a backup file previously produced by `learn backup`.",
    ),
):
    """Restore the current database from a backup file, overwriting
    whatever is currently at the resolved `--db` path (plan 7.1's 'backup
    支持从 backup 恢复' round-trip requirement). Refuses to restore a file
    that is not a valid learning_os SQLite database (wrong path, or a file
    that is not this project's schema at all) rather than silently
    producing a target DB that fails on the first real query.

    This closes the current connection to the database *before* restoring
    (SQLite's own backup API cannot safely overwrite a file a live
    connection still has open), then reopens it afterwards only long enough
    to confirm the restore succeeded.
    """
    target_path = config.resolve_db_path(_db_from_ctx(ctx))
    try:
        backup_service.restore_database(backup_path, target_path)
    except FileNotFoundError as exc:
        _fail(str(exc))
        return
    except ValueError as exc:
        _fail(str(exc))
        return
    typer.echo(f"Restored {target_path} from {backup_path}")


# ---------------------------------------------------------------------------
# learn import syllabus <path> / learn import approve <source-id-or-slug>
# ---------------------------------------------------------------------------
#
# syllabus_importer.py (plan section 8 / M1 milestone) has existed and been
# unit-tested against both real syllabus files since before this CLI wiring,
# but -- like `learn backup`/`restore` before the 2026-08-31 audit fix --
# had no command anywhere that called it, so plan 8.3's full "parse -> report
# -> persist draft -> approve PROPOSED -> QUEUED" pipeline was only reachable
# from a test or a Python REPL, never from `learn` itself.

def _print_import_report(report: ImportReport, path: str) -> None:
    """Prints the ImportReport summary the plan 12.2 Web page's future
    "Import Report: 确认/修改/批准导入对象" view is meant to mirror -- every
    field on the report gets a line, not just the create/update counters,
    so a human reviewing stdout has everything needed to decide what to
    `learn import approve` next without re-running the importer or opening
    the DB by hand."""
    typer.echo(
        f"Imported {path}: modules_created={report.modules_created} "
        f"sources_created={report.sources_created} "
        f"sources_updated={report.sources_updated} "
        f"sources_skipped_duplicate={report.sources_skipped_duplicate} "
        f"sources_skipped_locked={report.sources_skipped_locked} "
        f"learning_outputs_created={report.learning_outputs_created}"
    )
    if report.duplicate_candidates:
        typer.echo(f"Duplicate candidates ({len(report.duplicate_candidates)}):")
        for dup in report.duplicate_candidates:
            typer.echo(f"  '{dup.clean_title}':")
            for source_file, source_line, raw_heading in dup.occurrences:
                typer.echo(f"    {source_file}:{source_line}  {raw_heading}")
    if report.unresolved:
        typer.echo(f"Unresolved headings ({len(report.unresolved)}):")
        for line in report.unresolved:
            typer.echo(f"  {line}")
    if report.warnings:
        typer.echo(f"Warnings ({len(report.warnings)}):")
        for line in report.warnings:
            typer.echo(f"  {line}")


@import_app.command("syllabus")
def import_syllabus_cmd(
    ctx: typer.Context,
    path: str = typer.Argument(..., help="Path to a syllabus Markdown file to parse and import."),
):
    """Parse a syllabus Markdown file and persist its modules/sources/
    learning_outputs as PROPOSED drafts (plan 8.3: parse -> report ->
    persist draft). Safe to re-run against an unchanged or edited file --
    idempotent by (source_file, source_line) + content_hash, never
    silently overwrites a source that has already progressed past
    PROPOSED/VISIBLE (see syllabus_importer.import_syllabus's docstring).
    Nothing this command creates is QUEUED yet; run `learn import approve`
    afterwards for each source you have reviewed and want to schedule.
    """
    if not Path(path).exists():
        _fail(f"file not found: {path}")
        return
    conn = _connect(ctx)
    try:
        report = import_syllabus(conn, path)
        _print_import_report(report, path)
    finally:
        conn.close()


def _resolve_source_by_id_or_slug(conn: sqlite3.Connection, identifier: str) -> Source:
    """Sources are the only content type with a nullable slug (plan 7.2:
    not every source is meant to be addressed directly) -- the importer's
    slug-collision fallback (`syllabus_importer._slugify`) means a freshly
    imported draft may have no slug at all, so `learn import approve` must
    also accept the numeric row id, not just a slug like every other CLI
    target in this file. Tries a numeric id first only when `identifier`
    parses as one; a slug that happens to be all-digits is not a real
    possibility today (see `_slugify`'s ASCII-only, letter-containing
    output) but even if it were, id lookup failing would fall through to
    the slug lookup below rather than masking a real slug match."""
    sources = SourceRepository(conn)
    if identifier.isdigit():
        try:
            return sources.get(int(identifier))
        except KeyError:
            pass
    return sources.get_by_slug(identifier)


@import_app.command("approve")
def import_approve(
    ctx: typer.Context,
    source: str = typer.Argument(
        ..., help="Source id or slug (imported drafts without a slug must be "
        "addressed by id -- see `learn import syllabus`'s printed report)."
    ),
    confirm_scope: bool = typer.Option(
        False, "--confirm-scope",
        help="Also confirm scope_note before queuing (required whenever the "
             "importer extracted a scope_note candidate -- set_status() "
             "refuses QUEUED with scope_confirmed=False otherwise).",
    ),
    reason: Optional[str] = typer.Option(
        None, "--reason", help="Why this source is approved to enter the review queue.",
    ),
):
    """Explicit PROPOSED -> QUEUED approval step (plan 8.3: "approve
    PROPOSED -> QUEUED"; "未确认的 source 不得进入 Next Best Actions"). This
    is the only CLI path that lets an imported draft start consuming
    normal drill/review budget -- `learn import syllabus` never does this
    automatically, no matter how confident the parse looked.
    """
    conn = _connect(ctx)
    try:
        try:
            src = _resolve_source_by_id_or_slug(conn, source)
        except KeyError:
            _fail(f"source '{source}' not found (by id or slug)")
            return
        sources = SourceRepository(conn)
        if confirm_scope:
            sources.confirm_scope(src.id, reason=reason)
        try:
            updated = sources.set_status(src.id, "QUEUED", reason=reason)
        except InvalidTransitionError as exc:
            _fail(str(exc))
            return
        typer.echo(f"Source '{updated.slug or updated.id}' -> {updated.status}")
    finally:
        conn.close()


if __name__ == "__main__":
    app()
