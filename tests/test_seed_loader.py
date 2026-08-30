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
