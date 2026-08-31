"""TDD for `learn import syllabus <path>` / `learn import approve <source>`
(plan 8.3's full "parse -> report -> persist draft -> approve PROPOSED ->
QUEUED" pipeline wired into the CLI). Kept separate from test_cli.py (see
that file's docstring) so the M1 importer's CLI tests sit together instead
of interleaved with the M0 command tests.

Drives the CLI exactly like tests/test_cli.py does: through Typer's
CliRunner with `--db` pointed at a tmp_path file, never through a raw
sqlite3 connection or the syllabus_importer module directly -- this file
tests wiring, not parser/import logic (already covered exhaustively by
tests/test_syllabus_importer.py).
"""
from __future__ import annotations

import textwrap

import pytest
from typer.testing import CliRunner

from learning_os.cli import app
from learning_os.db import init_db
from learning_os.repositories import SourceRepository

runner = CliRunner()


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "learning.db"


def _run(db_path, *args):
    return runner.invoke(app, ["--db", str(db_path), *args])


def _write_syllabus(tmp_path, name: str, content: str):
    path = tmp_path / name
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# learn import syllabus <path>
# ---------------------------------------------------------------------------

def test_import_syllabus_creates_draft_sources(db_path, tmp_path):
    _run(db_path, "init")
    syllabus = _write_syllabus(
        tmp_path,
        "syllabus.md",
        """
        # A. 数学 refresh

        # A1. Linear Algebra

        body text here.
        """,
    )
    result = _run(db_path, "import", "syllabus", str(syllabus))
    assert result.exit_code == 0, result.output
    assert "modules_created=1" in result.output
    assert "sources_created=1" in result.output

    conn = init_db(db_path)
    try:
        sources = SourceRepository(conn).list_all()
        assert len(sources) == 1
        assert sources[0].status == "PROPOSED"
        assert sources[0].title == "Linear Algebra"
    finally:
        conn.close()


def test_import_syllabus_missing_file_fails_cleanly(db_path):
    _run(db_path, "init")
    result = _run(db_path, "import", "syllabus", "/no/such/file.md")
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_import_syllabus_is_idempotent(db_path, tmp_path):
    _run(db_path, "init")
    syllabus = _write_syllabus(
        tmp_path,
        "syllabus.md",
        """
        # A. 数学 refresh

        # A1. Linear Algebra

        body text here.
        """,
    )
    first = _run(db_path, "import", "syllabus", str(syllabus))
    assert first.exit_code == 0, first.output
    second = _run(db_path, "import", "syllabus", str(syllabus))
    assert second.exit_code == 0, second.output
    assert "sources_created=0" in second.output
    assert "sources_updated=0" in second.output

    conn = init_db(db_path)
    try:
        assert len(SourceRepository(conn).list_all()) == 1
    finally:
        conn.close()


def test_import_syllabus_prints_warnings_and_unresolved(db_path, tmp_path):
    _run(db_path, "init")
    syllabus = _write_syllabus(
        tmp_path,
        "syllabus.md",
        """
        # 0. 整体地图

        some meta text with no reliable label.

        # A. 数学 refresh

        # A1. Linear Algebra

        body text here.
        """,
    )
    result = _run(db_path, "import", "syllabus", str(syllabus))
    assert result.exit_code == 0, result.output
    assert "Unresolved headings" in result.output
    assert "整体地图" in result.output


# ---------------------------------------------------------------------------
# learn import approve <source-id-or-slug>
# ---------------------------------------------------------------------------

def test_import_approve_by_slug_queues_source(db_path, tmp_path):
    _run(db_path, "init")
    syllabus = _write_syllabus(
        tmp_path,
        "syllabus.md",
        """
        # A. 数学 refresh

        # A1. Linear Algebra

        body text here.
        """,
    )
    _run(db_path, "import", "syllabus", str(syllabus))

    conn = init_db(db_path)
    try:
        src = SourceRepository(conn).list_all()[0]
    finally:
        conn.close()
    assert src.slug is not None, "expected an ASCII-friendly slug for this fixture"

    result = _run(db_path, "import", "approve", src.slug)
    assert result.exit_code == 0, result.output
    assert "QUEUED" in result.output

    conn = init_db(db_path)
    try:
        updated = SourceRepository(conn).get_by_slug(src.slug)
        assert updated.status == "QUEUED"
    finally:
        conn.close()


def test_import_approve_by_id_when_slug_is_none(db_path, tmp_path):
    # Two distinct CJK-heavy titles that collapse to the same ASCII slug
    # (see syllabus_importer._slugify / test_slug_collision_between_...):
    # the second one persists with slug=None and must be addressable by id.
    _run(db_path, "init")
    syllabus = _write_syllabus(
        tmp_path,
        "syllabus.md",
        """
        # F. 工具

        # F1. Codex：我认为长期价值反而最大

        first entry about Codex.

        # F2. 让 Codex 做哪些工作？

        second, unrelated entry that happens to slugify the same way.
        """,
    )
    _run(db_path, "import", "syllabus", str(syllabus))

    conn = init_db(db_path)
    try:
        sources = SourceRepository(conn).list_all()
        unslugged = next(s for s in sources if s.slug is None)
    finally:
        conn.close()

    result = _run(db_path, "import", "approve", str(unslugged.id))
    assert result.exit_code == 0, result.output
    assert "QUEUED" in result.output


def test_import_approve_unknown_source_fails_cleanly(db_path):
    _run(db_path, "init")
    result = _run(db_path, "import", "approve", "does-not-exist")
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_import_approve_requires_confirm_scope_when_scope_note_present(db_path, tmp_path):
    _run(db_path, "init")
    syllabus = _write_syllabus(
        tmp_path,
        "syllabus.md",
        """
        # A. 数学 refresh

        # A1. Linear Algebra

        不完整刷，只看：第三章。跳过其余部分。
        """,
    )
    _run(db_path, "import", "syllabus", str(syllabus))

    conn = init_db(db_path)
    try:
        src = SourceRepository(conn).list_all()[0]
        assert src.scope_confirmed is False
    finally:
        conn.close()

    # Without --confirm-scope, QUEUED must be refused (set_status()'s own
    # scope_confirmed gate, exercised end-to-end through the CLI).
    without_confirm = _run(db_path, "import", "approve", str(src.id))
    assert without_confirm.exit_code != 0
    assert "scope_confirmed" in without_confirm.output

    with_confirm = _run(db_path, "import", "approve", str(src.id), "--confirm-scope")
    assert with_confirm.exit_code == 0, with_confirm.output
    assert "QUEUED" in with_confirm.output
