"""TDD for the syllabus Markdown importer (plan section 8 / M1 milestone).

Design under test (see `learning_os/services/syllabus_importer.py` module
docstring for the full rationale):

- `parse_syllabus(path)` is a pure parser -- no DB access, returns an
  `ImportReport` describing modules/sources/learning_outputs/duplicate
  candidates/unresolved headings/warnings.
- `import_syllabus(conn, path)` persists that report via the existing
  repository layer (never raw SQL) as PROPOSED drafts, and is idempotent
  by (source_file, source_line) + content_hash.

Fixtures below are deliberately small, hand-written Markdown strings (not
the real 1200-line syllabi) so each test isolates exactly one plan-8.2/8.4
rule. Plan 14's M1 fixture list is covered explicitly:
- reference-style link                  -> test_reference_style_link_resolves
- link definition block                  -> (same test; definitions parsed
                                             from the trailing block)
- Teece 1986 duplicate across two files   -> test_duplicate_candidate_across_files
- R/reference source                      -> test_r_marker_becomes_reference_mode
- H/sensor source                         -> test_h_module_becomes_sensor_source
- G/external-paced source                 -> test_g_module_becomes_external_paced
- selective scope                         -> test_scope_note_extracted_and_unconfirmed
- at least two syllabus outputs           -> test_bold_named_outputs_become_learning_outputs
  (covers 2 output names in one fixture)
"""
from __future__ import annotations

import textwrap

import pytest

from learning_os.db import init_db
from learning_os.repositories import LearningOutputRepository, SourceRepository
from learning_os.services.syllabus_importer import (
    import_syllabus,
    parse_syllabus,
)


def _write(tmp_path, name: str, content: str):
    path = tmp_path / name
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# parse_syllabus: pure parsing behavior
# ---------------------------------------------------------------------------


def test_module_and_source_headings_classified(tmp_path):
    path = _write(
        tmp_path,
        "syllabus.md",
        """
        # A. 数学 refresh

        intro text

        # A1. ★ Linear Algebra

        body text here.

        [3Blue1Brown](https://youtube.com/watch?v=abc)
        """,
    )
    report = parse_syllabus(path)

    assert len(report.modules) == 1
    assert report.modules[0].title == "数学 refresh"

    assert len(report.sources) == 1
    src = report.sources[0]
    assert src.title == "Linear Algebra"
    assert src.priority == "★"
    assert src.type == "video"  # inferred from youtube.com link
    assert src.source_line == 5  # the "# A1. ..." heading line


def test_unresolved_heading_recorded_not_dropped(tmp_path):
    path = _write(
        tmp_path,
        "syllabus.md",
        """
        # 0. 整体地图

        some overview text with no reliable label.
        """,
    )
    report = parse_syllabus(path)
    assert report.modules == []
    assert report.sources == []
    assert any("0. 整体地图" in u for u in report.unresolved)


def test_reference_style_link_resolves_against_definition_block(tmp_path):
    path = _write(
        tmp_path,
        "syllabus.md",
        """
        # B. LLM 技术

        # B2. ★ 论文

        参见 [DPO 论文][14]。

        [14]: https://arxiv.org/abs/2305.18290 "Direct Preference Optimization"
        """,
    )
    report = parse_syllabus(path)
    assert len(report.sources) == 1
    links = report.sources[0].links
    assert len(links) == 1
    assert links[0].kind == "reference"
    assert links[0].url == "https://arxiv.org/abs/2305.18290"
    assert links[0].text == "DPO 论文"


def test_reference_style_link_with_missing_definition_warns(tmp_path):
    path = _write(
        tmp_path,
        "syllabus.md",
        """
        # B. LLM 技术

        # B2. ★ 论文

        参见 [某论文][99]，但文末没有定义块。
        """,
    )
    report = parse_syllabus(path)
    assert report.sources[0].links == []
    assert any("[99]" in w for w in report.warnings)


def test_inline_link_captured(tmp_path):
    path = _write(
        tmp_path,
        "syllabus.md",
        """
        # D. AI 技术经济学

        # D1. ★ Some Course

        [Paper — Teece](https://doi.org/10.1016/0048-7333)
        """,
    )
    report = parse_syllabus(path)
    src = report.sources[0]
    assert len(src.links) == 1
    assert src.links[0].kind == "inline"
    assert src.links[0].url == "https://doi.org/10.1016/0048-7333"
    assert src.type == "paper"  # inferred from doi.org host


def test_estimated_minutes_from_hour_range_and_single_hour(tmp_path):
    path = _write(
        tmp_path,
        "syllabus.md",
        """
        # A. 数学 refresh

        # A1. ★ Linear Algebra：4–6h

        body
        """,
    )
    report = parse_syllabus(path)
    # (4+6)/2 * 60 = 300 minutes
    assert report.sources[0].estimated_minutes == 300


def test_scope_note_extracted_and_unconfirmed(tmp_path):
    path = _write(
        tmp_path,
        "syllabus.md",
        """
        # B. LLM 技术

        # B1. ★ Stanford CS336

        不完整刷，只看：

        L2 resource accounting：FLOPs / memory / arithmetic intensity

        跳过或快速扫 tokenizer、PyTorch basics。
        """,
    )
    report = parse_syllabus(path)
    src = report.sources[0]
    assert src.scope_note is not None
    assert "只看" in src.scope_note
    assert src.scope_confirmed is False
    assert any("scope_note candidate" in w for w in report.warnings)


def test_r_marker_becomes_reference_mode(tmp_path):
    path = _write(
        tmp_path,
        "syllabus.md",
        """
        # E. 投资 / 决策

        # E5. R：Mauboussin / Consilient Observer

        不是 syllabus。按问题找相关文章。
        """,
    )
    report = parse_syllabus(path)
    src = report.sources[0]
    assert src.title == "Mauboussin / Consilient Observer"
    assert src.resource_mode == "reference"
    assert any("resource_mode='reference'" in w for w in report.warnings)


def test_h_module_becomes_sensor_source(tmp_path):
    path = _write(
        tmp_path,
        "syllabus.md",
        """
        # H. 长期信息输入

        保持的 sensor 大概就是 FT / Reuters / SemiAnalysis 等长期信息源。
        """,
    )
    report = parse_syllabus(path)
    # Module H has no H1/H2 sub-sections -- importer synthesizes one
    # source from the module body so the content is not dropped.
    assert len(report.sources) == 1
    src = report.sources[0]
    assert src.synthesized_from_module is True
    assert src.resource_mode == "sensor"
    assert any("resource_mode='sensor'" in w for w in report.warnings)
    assert any("synthesized one source" in w for w in report.warnings)


def test_g_module_becomes_external_paced(tmp_path):
    path = _write(
        tmp_path,
        "syllabus.md",
        """
        # G. Algorithms / OI

        # G3. ★ USACO Guide

        这是你和孩子共享的 OI 主路线图。孩子走到哪里，你跟到哪里。
        """,
    )
    report = parse_syllabus(path)
    src = report.sources[0]
    assert src.pace_mode == "external_paced"
    assert any("pace_mode='external_paced'" in w for w in report.warnings)


def test_bold_named_outputs_become_learning_outputs(tmp_path):
    path = _write(
        tmp_path,
        "syllabus.md",
        """
        # A. 数学 refresh

        # A5. 数学 refresh 的真正毕业作业

        自己做一个 **LLM Economics Notebook**：包含 parameter memory 等计算。

        # B. LLM 技术

        # B9. 收尾

        同时维护一份 **2026 LLM capability production function memo**。
        """,
    )
    report = parse_syllabus(path)
    titles = {o.title for o in report.learning_outputs}
    assert "LLM Economics Notebook" in titles
    assert "2026 LLM capability production function memo" in titles
    assert len(report.learning_outputs) == 2


def test_duplicate_candidate_within_single_file(tmp_path):
    path = _write(
        tmp_path,
        "syllabus.md",
        """
        # D. Strategy

        # D1. ★ Teece 1986

        first mention.

        # D2. ★ Teece 1986

        second mention, same clean title.
        """,
    )
    report = parse_syllabus(path)
    assert len(report.duplicate_candidates) == 1
    assert report.duplicate_candidates[0].clean_title == "Teece 1986"
    assert len(report.duplicate_candidates[0].occurrences) == 2


def test_unlabeled_h2_becomes_low_confidence_source_not_dropped(tmp_path):
    # Regression fixture for a real bug found by smoke-testing the parser
    # against the actual 投资知识补充syllabus2.md: several real H2 entries
    # there carry no numeric/letter/circled-digit label at all (e.g.
    # "## ★ Tania Babina 2026 review", "## Kogut & Kulatilaka --
    # Capabilities as Real Options"). Before this fixture existed, such
    # headings fell into 'unresolved', and because unresolved headings
    # still act as body-slice boundaries, every line of the real paper
    # review underneath them was silently discarded -- not even captured
    # by the module-synthesis fallback. Since both real syllabus files use
    # H2 exclusively for source-level items (module headings are always
    # H1), an unlabeled H2 must still become a (low-confidence, flagged)
    # source so its body text survives.
    path = _write(
        tmp_path,
        "syllabus.md",
        """
        # H. 一个新模块

        ## Kogut & Kulatilaka — Capabilities as Real Options

        这是一篇关于 real options 的论文，body 文本不能被丢弃。
        """,
    )
    report = parse_syllabus(path)
    assert report.unresolved == []
    assert len(report.sources) == 1
    src = report.sources[0]
    assert src.title == "Kogut & Kulatilaka — Capabilities as Real Options"
    assert src.synthesized_from_module is False  # a real H2, not a module-body fallback
    assert any(
        "no recognized numeric/letter/circled-digit label" in w for w in report.warnings
    )


# ---------------------------------------------------------------------------
# import_syllabus: write side, via repositories, idempotency, dedup
# ---------------------------------------------------------------------------


@pytest.fixture
def conn(tmp_path):
    return init_db(tmp_path / "test.db")


def test_import_creates_modules_sources_and_outputs(conn, tmp_path):
    path = _write(
        tmp_path,
        "syllabus.md",
        """
        # A. 数学 refresh

        # A1. ★ Linear Algebra

        [3Blue1Brown](https://youtube.com/watch?v=abc)

        # A5. 毕业作业

        自己做一个 **LLM Economics Notebook**。
        """,
    )
    report = import_syllabus(conn, path)
    assert report.modules_created == 1
    assert report.sources_created == 2
    assert report.learning_outputs_created == 1

    sources = SourceRepository(conn)
    persisted = sources.list_all()
    assert len(persisted) == 2
    assert all(s.status == "PROPOSED" for s in persisted)
    assert all(s.source_file == "syllabus.md" for s in persisted)


def test_import_is_idempotent_on_unchanged_file(conn, tmp_path):
    path = _write(
        tmp_path,
        "syllabus.md",
        """
        # A. 数学 refresh

        # A1. ★ Linear Algebra

        body text
        """,
    )
    first = import_syllabus(conn, path)
    assert first.sources_created == 1

    second = import_syllabus(conn, path)
    assert second.sources_created == 0
    assert second.sources_updated == 0

    sources = SourceRepository(conn)
    assert len(sources.list_all()) == 1  # not duplicated


def test_reimport_after_content_change_updates_proposed_source(conn, tmp_path):
    path = _write(
        tmp_path,
        "syllabus.md",
        """
        # A. 数学 refresh

        # A1. ★ Linear Algebra

        original body
        """,
    )
    import_syllabus(conn, path)

    _write(
        tmp_path,
        "syllabus.md",
        """
        # A. 数学 refresh

        # A1. ★ Linear Algebra

        edited body with new content
        """,
    )
    second = import_syllabus(conn, path)
    assert second.sources_updated == 1
    assert second.sources_created == 0

    sources = SourceRepository(conn)
    persisted = sources.list_all()
    assert len(persisted) == 1


def test_reimport_does_not_touch_queued_source(conn, tmp_path):
    path = _write(
        tmp_path,
        "syllabus.md",
        """
        # A. 数学 refresh

        # A1. ★ Linear Algebra

        original body
        """,
    )
    import_syllabus(conn, path)
    sources = SourceRepository(conn)
    only = sources.list_all()[0]
    sources.set_status(only.id, "QUEUED")  # simulate user approval

    _write(
        tmp_path,
        "syllabus.md",
        """
        # A. 数学 refresh

        # A1. ★ Linear Algebra

        edited body -- source is already QUEUED, must not be silently changed
        """,
    )
    second = import_syllabus(conn, path)
    assert second.sources_updated == 0
    assert second.sources_skipped_locked == 1

    unchanged = sources.get(only.id)
    assert unchanged.status == "QUEUED"


def test_duplicate_candidate_across_files_not_double_inserted(conn, tmp_path):
    file1 = _write(
        tmp_path,
        "投资技术学习清单.md",
        """
        # F. 创业 / Strategy

        # F1. ★ Teece 1986

        Profiting from Technological Innovation.
        """,
    )
    file2 = _write(
        tmp_path,
        "投资知识补充syllabus2.md",
        """
        # 三、Strategy 补充

        # ② Teece 1986

        已经在 syllabus 中，继续保留。
        """,
    )
    report1 = import_syllabus(conn, file1)
    assert report1.sources_created == 1

    report2 = import_syllabus(conn, file2)
    # Same clean title "Teece 1986" at a different (file, line) location
    # -> recorded as a duplicate candidate, not inserted as a second row.
    assert report2.sources_created == 0
    assert report2.sources_skipped_duplicate == 1
    assert len(report2.duplicate_candidates) == 1
    assert report2.duplicate_candidates[0].clean_title == "Teece 1986"

    sources = SourceRepository(conn)
    all_sources = [s for s in sources.list_all() if s.title == "Teece 1986"]
    assert len(all_sources) == 1  # not duplicated across the two files


def test_slug_collision_between_distinct_titles_does_not_crash(conn, tmp_path):
    # Regression fixture for a real bug found by smoke-testing the writer
    # against the actual two syllabi: "Codex：我认为长期价值反而最大" and
    # "让 Codex 做哪些工作？" are two different real headings, but
    # _slugify() strips all CJK text and both collapse to the ASCII slug
    # "codex". sources.slug has a UNIQUE constraint, so inserting the
    # second one used to raise sqlite3.IntegrityError. These titles are
    # NOT a content duplicate (different headings, different bodies) --
    # the fix leaves the second source's slug unset (slug is nullable by
    # design) and records a warning, rather than crashing or inventing a
    # disambiguating suffix.
    path = _write(
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
    report = import_syllabus(conn, path)
    assert report.sources_created == 2  # both are real, distinct sources
    assert any("collides" in w for w in report.warnings)

    sources = SourceRepository(conn)
    persisted = sources.list_all()
    assert len(persisted) == 2
    slugs = [s.slug for s in persisted]
    assert slugs.count("codex") == 1  # only one kept the slug
    assert None in slugs  # the other's slug was left unset, not duplicated


def test_original_markdown_file_never_modified(conn, tmp_path):
    path = _write(
        tmp_path,
        "syllabus.md",
        """
        # A. 数学 refresh

        # A1. ★ Linear Algebra

        body
        """,
    )
    before = path.read_text(encoding="utf-8")
    import_syllabus(conn, path)
    import_syllabus(conn, path)
    after = path.read_text(encoding="utf-8")
    assert before == after


def test_learning_output_not_duplicated_on_reimport(conn, tmp_path):
    path = _write(
        tmp_path,
        "syllabus.md",
        """
        # A. 数学 refresh

        # A5. 毕业作业

        自己做一个 **LLM Economics Notebook**。
        """,
    )
    import_syllabus(conn, path)
    second = import_syllabus(conn, path)
    assert second.learning_outputs_created == 0

    outputs = LearningOutputRepository(conn)
    module_id = SourceRepository(conn).list_all()[0].module_id
    all_outputs = outputs.list_by_module(module_id)
    assert len(all_outputs) == 1
