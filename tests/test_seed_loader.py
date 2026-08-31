"""TDD for the seed-content loader (plan section 5.3 vertical slice, section
7.1 "内容定义...存放在可审阅的 YAML/Markdown 文件中", section 13.2 suggested
`content/` layout: modules.yaml, sources.yaml, concepts/*.yaml, items/*.yaml).

Design under test:

- `load_content(content_dir)` is a pure parser: reads modules.yaml,
  sources.yaml, content/concepts/*.yaml (each with an embedded `sources:`
  list of source slugs to link), content/items/*.yaml (one file per concept
  slug, matching the concept file's slug), and an optional applications.yaml.
  Returns a plain `SeedContent` dataclass -- no DB access, so the parsing
  logic is testable without a connection and reusable by a future importer.
- `seed_database(conn, content_dir)` is the write side: turns a SeedContent
  into modules/sources/concepts/concept_sources/items/applications rows via
  the existing repositories/services (never raw SQL, so state machine rules
  and evidence gates stay enforced exactly once).
- Idempotent by slug: modules/sources/concepts are matched by their unique
  slug column and skipped (not duplicated, not overwritten) if already
  present -- calling seed twice must not double every row. Items have no
  slug column (plan 7.2 #items has no slug field), so idempotency for items
  matches on (concept_id, prompt) instead.
- Applications have no natural idempotency key at all (plan 7.2 #applications
  is an append-only evidence log), so re-running seed intentionally does NOT
  re-insert an application whose reference already exists for that concept
  -- this loader treats the seed applications.yaml as "make sure this
  application exists at least once", not as a log to replay every run.
"""
from __future__ import annotations

import textwrap

import pytest

from learning_os.db import init_db
from learning_os.repositories import (
    ConceptRepository,
    ItemRepository,
    ModuleRepository,
    SourceRepository,
)
from learning_os.services.application_service import ApplicationService
from learning_os.services.seed_loader import load_content, seed_database

# 每张表都独立 `.commit()`（见 seed_loader.py 顶部 docstring），2026-08-31 owner
# 审计指出：如果 seed 在写到一半时失败（例如某个 items/*.yaml 文件里有格式错误
# 的行），之前已经 commit 过的 modules/sources/concepts 行会永久留在数据库里，
# 而不是全部撤销——半成品数据库。下面这组测试断言 seed_database() 必须是
# all-or-nothing：任何一步失败，此前在同一次调用里写入的所有行都必须回滚。


@pytest.fixture()
def conn(tmp_path):
    c = init_db(tmp_path / "learning.db")
    yield c
    c.close()


@pytest.fixture()
def content_dir(tmp_path):
    """A tiny two-concept seed tree, structurally identical to
    content/ at the repo root but small enough to assert on exactly."""
    root = tmp_path / "content"
    (root / "concepts").mkdir(parents=True)
    (root / "items").mkdir(parents=True)

    (root / "modules.yaml").write_text(
        textwrap.dedent(
            """
            modules:
              - slug: mod-a
                name: "Module A"
                phase: 1
                importance: core
                notes: "test module"
            """
        )
    )
    (root / "sources.yaml").write_text(
        textwrap.dedent(
            """
            sources:
              - slug: src-a
                module_slug: mod-a
                title: "Source A"
                type: course
                resource_mode: consumable
                pace_mode: self_paced
                scope_note: "only the intro"
                scope_confirmed: true
                source_file: "syllabus.md"
                source_line: 42
            """
        )
    )
    (root / "concepts" / "concept-a.yaml").write_text(
        textwrap.dedent(
            """
            concept:
              slug: concept-a
              module_slug: mod-a
              name: "Concept A"
              importance: core
              description: "a test concept"
              research_relevance: "because tests"
            sources:
              - src-a
            """
        )
    )
    (root / "items" / "concept-a.yaml").write_text(
        textwrap.dedent(
            """
            items:
              - type: numeric
                prompt: "2+2?"
                grading_mode: deterministic
                reference_answer: "4"
                difficulty: easy
                calibration_eligible: true
              - type: discrimination
                prompt: "A or B?"
                grading_mode: deterministic
                reference_answer: "A"
                answer_schema_json: '{"disqualifiers": ["B"]}'
                difficulty: easy
            """
        )
    )
    (root / "applications.yaml").write_text(
        textwrap.dedent(
            """
            applications:
              - concept_slug: concept-a
                evidence_level: STRONG
                reference_type: research_note
                reference: "used concept-a in a real analysis"
                note: "seed application"
            """
        )
    )
    return root


# ---------------------------------------------------------------------------
# load_content: pure parsing, no DB
# ---------------------------------------------------------------------------

def test_load_content_parses_modules_sources_concepts_items_applications(content_dir):
    content = load_content(content_dir)

    assert len(content.modules) == 1
    assert content.modules[0].slug == "mod-a"
    assert content.modules[0].phase == 1

    assert len(content.sources) == 1
    assert content.sources[0].slug == "src-a"
    assert content.sources[0].module_slug == "mod-a"
    assert content.sources[0].scope_confirmed is True

    assert len(content.concepts) == 1
    assert content.concepts[0].slug == "concept-a"
    assert content.concepts[0].module_slug == "mod-a"
    assert content.concepts[0].source_slugs == ["src-a"]

    assert len(content.items) == 1
    assert content.items[0].concept_slug == "concept-a"
    assert len(content.items[0].items) == 2
    assert content.items[0].items[0]["prompt"] == "2+2?"

    assert len(content.applications) == 1
    assert content.applications[0].concept_slug == "concept-a"
    assert content.applications[0].evidence_level == "STRONG"


def test_load_content_missing_applications_file_is_optional(content_dir):
    (content_dir / "applications.yaml").unlink()
    content = load_content(content_dir)
    assert content.applications == []


def test_load_content_concept_without_matching_items_file_is_ok(content_dir):
    (content_dir / "items" / "concept-a.yaml").unlink()
    content = load_content(content_dir)
    assert content.items == []


# ---------------------------------------------------------------------------
# seed_database: write side, via repositories/services (never raw SQL)
# ---------------------------------------------------------------------------

def test_seed_database_creates_full_graph(conn, content_dir):
    result = seed_database(conn, content_dir)

    assert result.modules_created == 1
    assert result.sources_created == 1
    assert result.concepts_created == 1
    assert result.items_created == 2
    assert result.applications_created == 1

    module = ModuleRepository(conn).get_by_slug("mod-a")
    assert module.name == "Module A"

    source = SourceRepository(conn).get_by_slug("src-a")
    assert source.module_id == module.id
    assert source.scope_confirmed is True

    concept = ConceptRepository(conn).get_by_slug("concept-a")
    assert concept.module_id == module.id

    items = ItemRepository(conn).list_by_concept(concept.id)
    assert len(items) == 2
    prompts = {item.prompt for item in items}
    assert prompts == {"2+2?", "A or B?"}

    applications = ApplicationService(conn).list_applications(concept.id)
    assert len(applications) == 1
    assert applications[0].evidence_level == "STRONG"
    assert applications[0].reference == "used concept-a in a real analysis"

    # concept_sources link was created too.
    linked = conn.execute(
        "SELECT source_id FROM concept_sources WHERE concept_id=?", (concept.id,)
    ).fetchall()
    assert [row[0] for row in linked] == [source.id]


def test_seed_database_is_idempotent_for_modules_sources_concepts(conn, content_dir):
    first = seed_database(conn, content_dir)
    second = seed_database(conn, content_dir)

    assert first.modules_created == 1
    assert second.modules_created == 0
    assert second.sources_created == 0
    assert second.concepts_created == 0

    # Exactly one module/source/concept row exists, not two.
    assert conn.execute("SELECT COUNT(*) FROM modules").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0] == 1


def test_seed_database_is_idempotent_for_items_by_concept_and_prompt(conn, content_dir):
    seed_database(conn, content_dir)
    second = seed_database(conn, content_dir)

    assert second.items_created == 0
    assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 2


def test_seed_database_does_not_duplicate_applications_with_same_reference(conn, content_dir):
    seed_database(conn, content_dir)
    second = seed_database(conn, content_dir)

    assert second.applications_created == 0
    assert conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0] == 1


def test_seed_database_real_content_dir_loads_cleanly(conn):
    """Smoke test against the actual repo-root content/ directory (the real
    vertical-slice seed, plan 5.3: 3 LLM deterministic + 2 math/stat + 2
    econ/strategy concepts, 10-15 items, 2 application references)."""
    from pathlib import Path

    real_content_dir = Path(__file__).resolve().parents[1] / "content"
    result = seed_database(conn, real_content_dir)

    assert result.modules_created == 3
    assert result.concepts_created == 7
    assert 10 <= result.items_created <= 15
    assert result.applications_created == 2


# ---------------------------------------------------------------------------
# seed_database: transactional all-or-nothing (2026-08-31 audit finding)
# ---------------------------------------------------------------------------
#
# Before this fix, every repository call inside seed_database() committed
# independently. If a later YAML file turned out to be malformed (e.g. an
# item missing a required key), seed_database() would raise -- but every
# module/source/concept/item already inserted in that same call stayed
# committed. Re-running `learn seed` after fixing the bad file would then
# hit "slug already exists" idempotency short-circuits for the partial rows
# and silently skip re-validating them, leaving a half-seeded database that
# looks superficially fine. seed_database() must instead behave as a single
# atomic unit: any exception rolls back every row written during that call.

@pytest.fixture()
def content_dir_with_malformed_second_concept(content_dir):
    """content_dir (concept-a, valid) plus a second concept (concept-b)
    whose item file is missing the required `grading_mode` key. Module
    mod-a / concept-a / concept-a's items are all well-formed and would
    succeed on their own -- concept-b is what blows up load-side processing
    partway through seed_database()'s write loop, after concept-a's rows
    have already been written by earlier iterations of the same call."""
    (content_dir / "concepts" / "concept-b.yaml").write_text(
        textwrap.dedent(
            """
            concept:
              slug: concept-b
              module_slug: mod-a
              name: "Concept B"
              importance: core
            sources: []
            """
        )
    )
    (content_dir / "items" / "concept-b.yaml").write_text(
        textwrap.dedent(
            """
            items:
              - type: numeric
                prompt: "broken item, no grading_mode"
                reference_answer: "0"
            """
        )
    )
    return content_dir


def test_seed_database_rolls_back_everything_on_a_malformed_item(
    conn, content_dir_with_malformed_second_concept
):
    with pytest.raises(KeyError):
        seed_database(conn, content_dir_with_malformed_second_concept)

    # Nothing from this failed call should have been left committed --
    # not concept-a's module/source/concept/items (written by earlier loop
    # iterations in the same call), and not concept-b itself (written just
    # before the malformed item that caused the KeyError).
    assert conn.execute("SELECT COUNT(*) FROM modules").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0] == 0


def test_seed_database_succeeds_normally_after_a_rolled_back_attempt(
    conn, content_dir_with_malformed_second_concept
):
    """A rollback must not leave the connection/transaction state broken --
    a subsequent successful seed_database() call (e.g. after the user fixes
    the YAML) must still work and must not be blocked by phantom
    already-exists rows from the failed attempt."""
    with pytest.raises(KeyError):
        seed_database(conn, content_dir_with_malformed_second_concept)

    # Fix concept-b's item file and retry -- this should now fully succeed,
    # including the rows that were rolled back on the first attempt.
    (content_dir_with_malformed_second_concept / "items" / "concept-b.yaml").write_text(
        textwrap.dedent(
            """
            items:
              - type: numeric
                prompt: "fixed item"
                grading_mode: deterministic
                reference_answer: "0"
            """
        )
    )
    result = seed_database(conn, content_dir_with_malformed_second_concept)

    assert result.modules_created == 1
    assert result.concepts_created == 2
    assert conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 3
