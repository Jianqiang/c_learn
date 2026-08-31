"""Seed-content loader (plan 5.3 vertical slice; plan 7.1 "内容定义...存放在
可审阅的 YAML/Markdown 文件中"; plan 13.2 suggested `content/` layout).

Two-phase, matching plan 7.1's source-of-truth split:

- `load_content()` is a pure parser: reads modules.yaml, sources.yaml,
  content/concepts/*.yaml, content/items/*.yaml (one file per concept slug),
  and an optional applications.yaml, and returns a plain in-memory
  `SeedContent` -- no DB access at all, so parsing is unit-testable and
  reusable by a future syllabus importer (plan section 8) without dragging
  a database connection into that code path too.
- `seed_database()` is the write side: turns a SeedContent into rows via
  the existing repositories/services (ModuleRepository, SourceRepository,
  ConceptRepository, ItemRepository, ApplicationService) -- never raw SQL,
  so every state-machine rule and evidence gate that already exists for
  those tables stays enforced exactly once, in exactly one place.

Idempotency (plan 8.2's "用 file path + heading + content hash 实现幂等
导入" principle, scaled down to hand-authored YAML rather than parsed
Markdown -- there is no content_hash column round-trip here, just a
straightforward "does a row with this identity already exist" check per
table, which is enough for re-running `learn init`-time seeding safely):

- modules/sources/concepts are matched by their unique `slug` column.
  A second seed_database() call finds the existing row and does not
  insert a duplicate or overwrite any field a user may have since changed
  via the CLI (e.g. workflow_status) -- it simply counts the row as
  "already present" and moves on.
- items have no slug column at all (plan 7.2 #items), so their identity
  for idempotency purposes is (concept_id, prompt) -- two items under the
  same concept with byte-identical prompt text are treated as the same
  item on re-seed.
- applications are an append-only evidence log with no natural key (plan
  7.2 #applications), so re-seeding intentionally does NOT replay every
  run; a seed application is only inserted if no existing application row
  for that concept already has the same `reference` text. This keeps
  `learn init` (or a future `seed` command) safe to run repeatedly without
  inflating the evidence-gate proxies in application_service.py (e.g.
  _successful_case_count) with duplicate rows.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from learning_os.repositories import (
    ConceptRepository,
    ItemRepository,
    ModuleRepository,
    SourceRepository,
)
from learning_os.services.application_service import ApplicationService


# ---------------------------------------------------------------------------
# Pure data model (load_content's return value)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SeedModule:
    slug: str
    name: str
    phase: int
    importance: Optional[str] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class SeedSource:
    slug: str
    module_slug: str
    title: str
    type: str
    resource_mode: str = "consumable"
    pace_mode: str = "self_paced"
    scope_note: Optional[str] = None
    scope_confirmed: bool = False
    source_file: Optional[str] = None
    source_line: Optional[int] = None
    url_or_path: Optional[str] = None
    estimated_minutes: Optional[int] = None
    priority: Optional[str] = None


@dataclass(frozen=True)
class SeedConcept:
    slug: str
    module_slug: str
    name: str
    importance: Optional[str] = None
    description: Optional[str] = None
    research_relevance: Optional[str] = None
    source_slugs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SeedConceptItems:
    concept_slug: str
    items: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class SeedApplication:
    concept_slug: str
    evidence_level: str
    reference_type: Optional[str] = None
    reference: Optional[str] = None
    note: Optional[str] = None
    evidence: Optional[str] = None
    result: str = "UNASSESSED"


@dataclass(frozen=True)
class SeedContent:
    modules: list[SeedModule]
    sources: list[SeedSource]
    concepts: list[SeedConcept]
    items: list[SeedConceptItems]
    applications: list[SeedApplication]


# ---------------------------------------------------------------------------
# load_content: parsing only, no DB
# ---------------------------------------------------------------------------

def _read_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_content(content_dir: str | Path) -> SeedContent:
    content_dir = Path(content_dir)

    modules_data = _read_yaml(content_dir / "modules.yaml").get("modules", [])
    modules = [
        SeedModule(
            slug=m["slug"], name=m["name"], phase=m["phase"],
            importance=m.get("importance"), notes=m.get("notes"),
        )
        for m in modules_data
    ]

    sources_data = _read_yaml(content_dir / "sources.yaml").get("sources", [])
    sources = [
        SeedSource(
            slug=s["slug"], module_slug=s["module_slug"], title=s["title"],
            type=s["type"], resource_mode=s.get("resource_mode", "consumable"),
            pace_mode=s.get("pace_mode", "self_paced"),
            scope_note=s.get("scope_note"),
            scope_confirmed=bool(s.get("scope_confirmed", False)),
            source_file=s.get("source_file"), source_line=s.get("source_line"),
            url_or_path=s.get("url_or_path"),
            estimated_minutes=s.get("estimated_minutes"),
            priority=s.get("priority"),
        )
        for s in sources_data
    ]

    concepts: list[SeedConcept] = []
    concepts_dir = content_dir / "concepts"
    if concepts_dir.is_dir():
        for concept_file in sorted(concepts_dir.glob("*.yaml")):
            raw = _read_yaml(concept_file)
            c = raw["concept"]
            concepts.append(
                SeedConcept(
                    slug=c["slug"], module_slug=c["module_slug"], name=c["name"],
                    importance=c.get("importance"), description=c.get("description"),
                    research_relevance=c.get("research_relevance"),
                    source_slugs=list(raw.get("sources", [])),
                )
            )

    items: list[SeedConceptItems] = []
    items_dir = content_dir / "items"
    if items_dir.is_dir():
        for concept in concepts:
            item_file = items_dir / f"{concept.slug}.yaml"
            if not item_file.exists():
                continue
            raw = _read_yaml(item_file)
            items.append(
                SeedConceptItems(
                    concept_slug=concept.slug, items=list(raw.get("items", [])),
                )
            )

    applications_file = content_dir / "applications.yaml"
    applications: list[SeedApplication] = []
    if applications_file.exists():
        raw = _read_yaml(applications_file).get("applications", [])
        applications = [
            SeedApplication(
                concept_slug=a["concept_slug"], evidence_level=a["evidence_level"],
                reference_type=a.get("reference_type"), reference=a.get("reference"),
                note=a.get("note"), evidence=a.get("evidence"),
                result=a.get("result", "UNASSESSED"),
            )
            for a in raw
        ]

    return SeedContent(
        modules=modules, sources=sources, concepts=concepts, items=items,
        applications=applications,
    )


# ---------------------------------------------------------------------------
# seed_database: write side, via repositories/services only
# ---------------------------------------------------------------------------

@dataclass
class SeedResult:
    modules_created: int = 0
    sources_created: int = 0
    concepts_created: int = 0
    items_created: int = 0
    applications_created: int = 0


class _DeferredCommitConnection:
    """A thin proxy around a real sqlite3.Connection that turns every
    `.commit()` call into a no-op until `_flush()` is called explicitly.

    Why this exists (2026-08-31 audit finding): every repository/service
    used by seed_database() below (ModuleRepository, SourceRepository,
    ConceptRepository, ItemRepository, ApplicationService) calls
    `self._conn.commit()` right after its own INSERT, independently of every
    other repository. That is the right default for normal CLI usage (each
    `learn drill`/`learn apply` etc. is one user action, one commit), but it
    means seed_database()'s multi-table write loop was never atomic: if
    module/source/concept rows for an earlier item in the loop had already
    committed by the time a later item raised (e.g. a malformed YAML file),
    those earlier rows stayed in the database permanently -- a half-seeded
    database with no way to tell "fully seeded" apart from "partially seeded
    then crashed" just by looking at row counts.

    Wrapping `conn` in this proxy for the duration of seed_database() lets
    every repository call site stay unchanged (they still call
    `self._conn.execute(...)` and `self._conn.commit()` exactly as before --
    `execute` and every other attribute pass straight through via
    `__getattr__`), while seed_database() itself decides once, at the very
    end, whether to actually commit (all writes succeeded) or roll back
    (any exception propagated) -- true all-or-nothing semantics without
    touching a single repository.
    """

    def __init__(self, real_conn: sqlite3.Connection):
        self._real_conn = real_conn

    def commit(self) -> None:
        pass  # deferred until seed_database() finishes successfully

    def _flush(self) -> None:
        self._real_conn.commit()

    def __getattr__(self, name: str):
        return getattr(self._real_conn, name)


def seed_database(conn: sqlite3.Connection, content_dir: str | Path) -> SeedResult:
    content = load_content(content_dir)
    result = SeedResult()

    deferred = _DeferredCommitConnection(conn)
    modules = ModuleRepository(deferred)
    sources = SourceRepository(deferred)
    concepts = ConceptRepository(deferred)
    item_repo = ItemRepository(deferred)
    applications_service = ApplicationService(deferred)

    try:
        _seed_all(content, result, modules, sources, concepts, item_repo, applications_service)
    except Exception:
        conn.rollback()
        raise
    else:
        deferred._flush()
    return result


def _seed_all(
    content: SeedContent,
    result: SeedResult,
    modules: ModuleRepository,
    sources: SourceRepository,
    concepts: ConceptRepository,
    item_repo: ItemRepository,
    applications_service: ApplicationService,
) -> None:

    module_ids: dict[str, int] = {}
    for m in content.modules:
        try:
            existing = modules.get_by_slug(m.slug)
            module_ids[m.slug] = existing.id
            continue
        except KeyError:
            pass
        created = modules.create(
            slug=m.slug, name=m.name, phase=m.phase, importance=m.importance,
            notes=m.notes,
        )
        module_ids[m.slug] = created.id
        result.modules_created += 1

    source_ids: dict[str, int] = {}
    for s in content.sources:
        try:
            existing = sources.get_by_slug(s.slug)
            source_ids[s.slug] = existing.id
            continue
        except KeyError:
            pass
        created = sources.create(
            module_id=module_ids[s.module_slug], title=s.title, type=s.type,
            resource_mode=s.resource_mode, pace_mode=s.pace_mode, slug=s.slug,
            url_or_path=s.url_or_path, estimated_minutes=s.estimated_minutes,
            priority=s.priority, scope_note=s.scope_note,
            scope_confirmed=s.scope_confirmed, source_file=s.source_file,
            source_line=s.source_line,
        )
        source_ids[s.slug] = created.id
        result.sources_created += 1

    concept_ids: dict[str, int] = {}
    for c in content.concepts:
        try:
            existing = concepts.get_by_slug(c.slug)
            concept_ids[c.slug] = existing.id
            continue
        except KeyError:
            pass
        created = concepts.create(
            module_id=module_ids[c.module_slug], slug=c.slug, name=c.name,
            importance=c.importance, description=c.description,
            research_relevance=c.research_relevance,
        )
        concept_ids[c.slug] = created.id
        result.concepts_created += 1
        for source_slug in c.source_slugs:
            concepts.link_source(created.id, source_ids[source_slug])

    for concept_items in content.items:
        concept_id = concept_ids[concept_items.concept_slug]
        existing_prompts = {
            item.prompt for item in item_repo.list_by_concept(concept_id)
        }
        for raw_item in concept_items.items:
            if raw_item["prompt"] in existing_prompts:
                continue
            item_repo.create(
                concept_id=concept_id, type=raw_item["type"],
                prompt=raw_item["prompt"], grading_mode=raw_item["grading_mode"],
                reference_answer=raw_item.get("reference_answer"),
                rubric_json=raw_item.get("rubric_json"),
                answer_schema_json=raw_item.get("answer_schema_json"),
                difficulty=raw_item.get("difficulty"),
                calibration_eligible=bool(raw_item.get("calibration_eligible", False)),
            )
            result.items_created += 1

    for a in content.applications:
        concept_id = concept_ids.get(a.concept_slug)
        if concept_id is None:
            concept_id = concepts.get_by_slug(a.concept_slug).id
        existing_refs = {
            app.reference for app in applications_service.list_applications(concept_id)
        }
        if a.reference in existing_refs:
            continue
        applications_service.record_application(
            concept_id=concept_id, evidence_level=a.evidence_level,
            reference_type=a.reference_type, reference=a.reference,
            note=a.note, evidence=a.evidence, result=a.result,
        )
        result.applications_created += 1
