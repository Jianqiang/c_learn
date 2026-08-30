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

`learn import-syllabus` is intentionally not implemented here -- it belongs
to the seed-content task (plan 8's importer), not to this command-wiring
task.

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
    SourceRepository,
)
from learning_os.services import backup_service
from learning_os.services.application_service import ApplicationService, EvidenceGateError
from learning_os.services.review_service import ReviewService
from learning_os.services.seed_loader import seed_database
from learning_os.services.session_service import SessionService

app = typer.Typer(add_completion=False, no_args_is_help=True)
output_app = typer.Typer(add_completion=False, no_args_is_help=True)
focus_app = typer.Typer(add_completion=False, no_args_is_help=True)
app.add_typer(output_app, name="output")
app.add_typer(focus_app, name="focus")


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
    This is distinct from the not-yet-implemented `learn import-syllabus`
    (plan section 8's Markdown importer with ImportReport/dedup/content-hash,
    explicit M1 scope): `seed` only replays already-reviewed YAML, it does
    not parse or interpret the original syllabus Markdown files at all.
    """
    conn = _connect(ctx)
    try:
        result = seed_database(conn, content_dir)
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

    sessions = SessionService(conn)
    session = sessions.start_or_resume(session_type=session_type, target_type="concept", target_id=concept.id)

    outcome = _grade_deterministic(item, answer)
    attempt = sessions.record_attempt(session.id, item.id, answer=answer, outcome=outcome, evaluator_kind="deterministic")
    sessions.end(session.id)
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
        application = applications.record_application(
            concept_id=concept.id,
            evidence_level="STRONG" if strong else "PARTIAL",
            reference=ref,
        )
        typer.echo(
            f"Application recorded for '{concept_slug}': "
            f"{application.evidence_level} (application {application.id})"
        )
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


if __name__ == "__main__":
    app()
