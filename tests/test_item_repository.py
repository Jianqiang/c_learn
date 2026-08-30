"""TDD for ItemRepository (plan section 7.2 #items).

Prior to this, item rows were only ever touched via ad-hoc raw SQL
scattered across test fixtures and services/application_service.py /
services/review_service.py (each doing its own narrow SELECT). CLI wiring
(learn drill/learn/recall, plan 12.1) needs to enumerate a concept's active
items and fetch a single item's full content (prompt, grading_mode,
reference_answer, rubric_json, answer_schema_json) to actually run a
session, so this gives it one real repository instead of another one-off
query.

Design under test:

- create(): plain insert, active defaults to True, content_version
  defaults to 1 (matching the DDL defaults in db.py).
- get(): raises KeyError for a missing id (repository convention already
  used by Module/Source/Concept/LearningOutput repositories).
- list_by_concept(): only returns active=1 rows, ordered by id ascending
  -- an item that has been deactivated (active=0) must not show up in a
  drill/recall session's candidate list.
"""
from __future__ import annotations

import sqlite3

import pytest

from learning_os.db import init_db
from learning_os.repositories import ConceptRepository, ItemRepository, ModuleRepository


@pytest.fixture()
def conn(tmp_path) -> sqlite3.Connection:
    c = init_db(tmp_path / "learning.db")
    yield c
    c.close()


@pytest.fixture()
def concept_id(conn) -> int:
    module = ModuleRepository(conn).create(slug="m1", name="Module 1", phase=1)
    return ConceptRepository(conn).create(
        module_id=module.id, slug="c1", name="Concept 1"
    ).id


@pytest.fixture()
def item_repo(conn) -> ItemRepository:
    return ItemRepository(conn)


def test_create_item_defaults(item_repo, concept_id):
    item = item_repo.create(
        concept_id=concept_id,
        type="numeric",
        prompt="What is 2+2?",
        grading_mode="deterministic",
        reference_answer="4",
    )
    assert item.active is True
    assert item.content_version == 1
    assert item.calibration_eligible is False
    assert item.prompt == "What is 2+2?"


def test_create_item_accepts_optional_fields(item_repo, concept_id):
    item = item_repo.create(
        concept_id=concept_id,
        type="explanation",
        prompt="Explain X",
        grading_mode="rubric",
        rubric_json='{"must_understand": ["a"]}',
        difficulty="medium",
        calibration_eligible=True,
    )
    assert item.rubric_json == '{"must_understand": ["a"]}'
    assert item.difficulty == "medium"
    assert item.calibration_eligible is True


def test_get_missing_item_raises_keyerror(item_repo):
    with pytest.raises(KeyError):
        item_repo.get(999)


def test_list_by_concept_orders_by_id(item_repo, concept_id):
    a = item_repo.create(
        concept_id=concept_id, type="numeric", prompt="q1",
        grading_mode="deterministic", reference_answer="1",
    )
    b = item_repo.create(
        concept_id=concept_id, type="numeric", prompt="q2",
        grading_mode="deterministic", reference_answer="2",
    )
    listed = item_repo.list_by_concept(concept_id)
    assert [i.id for i in listed] == [a.id, b.id]


def test_list_by_concept_excludes_inactive_items(item_repo, conn, concept_id):
    active = item_repo.create(
        concept_id=concept_id, type="numeric", prompt="q1",
        grading_mode="deterministic", reference_answer="1",
    )
    inactive = item_repo.create(
        concept_id=concept_id, type="numeric", prompt="q2",
        grading_mode="deterministic", reference_answer="2",
    )
    conn.execute("UPDATE items SET active=0 WHERE id=?", (inactive.id,))
    conn.commit()

    listed = item_repo.list_by_concept(concept_id)
    assert [i.id for i in listed] == [active.id]


def test_list_by_concept_empty_when_no_items(item_repo, concept_id):
    assert item_repo.list_by_concept(concept_id) == []


def test_list_by_concept_filters_other_concepts(item_repo, conn, concept_id):
    module = ModuleRepository(conn).create(slug="m2", name="Module 2", phase=1)
    other_concept = ConceptRepository(conn).create(
        module_id=module.id, slug="c2", name="Concept 2"
    )
    item_repo.create(
        concept_id=concept_id, type="numeric", prompt="q1",
        grading_mode="deterministic", reference_answer="1",
    )
    item_repo.create(
        concept_id=other_concept.id, type="numeric", prompt="other",
        grading_mode="deterministic", reference_answer="1",
    )
    listed = item_repo.list_by_concept(concept_id)
    assert len(listed) == 1
    assert listed[0].prompt == "q1"
