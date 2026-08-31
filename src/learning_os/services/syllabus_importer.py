"""Syllabus Markdown importer (plan section 8 / M1 milestone).

Two-phase, matching the same split seed_loader.py already established for
YAML content (see that module's docstring, which explicitly earmarked this
split "for a future syllabus importer"):

- `parse_syllabus()` is a pure parser: reads one Markdown file and returns
  an in-memory `ImportReport` -- no DB access at all, so parsing is
  unit-testable against small fixture strings without a database, and the
  same report can be printed by the CLI before anything is persisted.
- `import_syllabus()` is the write side: turns the parsed report into
  `sources`/`modules`/`learning_outputs` rows via the existing repository
  layer (never raw SQL), enforcing plan 8.2's idempotency and "don't
  silently overwrite user state" rules, and annotates the report with what
  was actually created/updated/skipped so the CLI has one object to print.

Plan 8.1's governing principle -- "尽可能提取，不能猜测补全" ("extract as
much as reliably possible; never guess-fill a gap") -- shapes every
heuristic below: when a heading or a hint is ambiguous, this module always
prefers to leave it in `unresolved`/`warnings` over inventing a value, even
when a human reading the same document would probably guess correctly.
That is a deliberate asymmetry (under-extraction is recoverable by a human
edit later; a wrong guess silently treated as fact is not).

Heading classification (module vs. source vs. unresolved), plan 8.2 bullet
1 ("一级/二级 heading 作为候选 module 或 section"):
    Only H1/H2 headings are ever candidates; H3+ always folds into the
    raw body text of whichever H1/H2 section precedes it (papers listed
    under a "## B2. 七篇论文" section, for example, never become their own
    sources -- their links/text stay inside B2's raw context).

    A heading is classified as a MODULE when its text starts with a bare
    single Latin letter ("A." .. "H.") or a Chinese-numeral list marker
    ("一、" "二、" ... "二十、"). Both real syllabi use one of these two
    conventions for their top-level divisions.

    A heading is classified as a SOURCE (attributed to the most recently
    seen module in document order) when its text starts with a
    letter+digit label ("A1." "F1." "G3."), a circled-digit marker
    ("①".."⑳"), an "R："/"R:" reference marker, or -- only at H2 depth,
    to avoid catching meta H1s like "0. 整体地图" -- a bare arabic-digit
    list marker ("1." "2.").

    Anything else (e.g. "我最终会按什么顺序执行", "最后：什么应该明确删掉",
    "0. 整体地图" -- all real headings in 投资技术学习清单.md with no
    reliable label) is neither: it is recorded in `unresolved` with its
    raw text and line number so it is visible, never silently dropped,
    but it never becomes a module/source/concept row (plan 8.2's
    "只有明确命名的对象才候选为concept" principle applied conservatively
    to modules/sources too).

    One extra rule not in the plan's prose but required to cover the
    real file (M1 fixture requirement: "H/sensor source" must exist):
    投资技术学习清单.md's module H ("长期信息输入") has zero H1/H2 children
    of its own -- its content is a bare paragraph + bullet list directly
    under the module heading. When a module ends up with no attributed
    sources at all, this importer synthesizes exactly one source from
    the module heading's own body text (real text, not invented), so a
    module that is *itself* the only resource still produces a source
    row instead of disappearing entirely.

Concepts are deliberately never auto-created here (plan 8.2: "只有明确
命名的对象才候选为concept"). Bold-faced object names that look like named
deliverables (see learning-output detection below) are the one exception
plan 8.4 explicitly calls out as safe to persist directly; everything else
that might be a "concept" is left as free-text in `unresolved`/warnings
for a human to turn into a real `content/concepts/*.yaml` entry later via
the existing `learn seed` path -- this importer does not compete with
that workflow, it only feeds it more raw material to review.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from learning_os.repositories import (
    LearningOutputRepository,
    ModuleRepository,
    SourceRepository,
)

# ---------------------------------------------------------------------------
# Pure data model (parse_syllabus's return value)
# ---------------------------------------------------------------------------


@dataclass
class ParsedLink:
    text: str
    url: str
    line: int
    kind: str  # "inline" | "reference" | "definition"


@dataclass
class ParsedModule:
    title: str
    raw_heading: str
    source_file: str
    source_line: int
    order: int  # 0-based position among modules in this file, for a stable slug


@dataclass
class ParsedSource:
    title: str
    raw_heading: str
    source_file: str
    source_line: int
    module_order: int  # links back to ParsedModule.order
    type: str
    resource_mode: str
    pace_mode: str
    priority: Optional[str]
    scope_note: Optional[str]
    scope_confirmed: bool
    estimated_minutes: Optional[int]
    url_or_path: Optional[str]
    content_hash: str
    links: list[ParsedLink] = field(default_factory=list)
    synthesized_from_module: bool = False


@dataclass
class ParsedLearningOutput:
    title: str
    module_order: int
    source_file: str
    source_line: int
    raw_context: str


@dataclass
class DuplicateCandidate:
    clean_title: str
    occurrences: list[tuple[str, int, str]]  # (source_file, source_line, raw_heading)


@dataclass
class ImportReport:
    source_file: str
    modules: list[ParsedModule] = field(default_factory=list)
    sources: list[ParsedSource] = field(default_factory=list)
    learning_outputs: list[ParsedLearningOutput] = field(default_factory=list)
    duplicate_candidates: list[DuplicateCandidate] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Populated only after import_syllabus() persists this report -- absent
    # (empty) on a report returned by parse_syllabus() alone.
    modules_created: int = 0
    sources_created: int = 0
    sources_updated: int = 0
    sources_skipped_duplicate: int = 0
    sources_skipped_locked: int = 0
    learning_outputs_created: int = 0


# ---------------------------------------------------------------------------
# Heading classification
# ---------------------------------------------------------------------------

_MODULE_LETTER_RE = re.compile(r"^([A-H])\.\s+(.*)$")
_MODULE_CJK_NUM_RE = re.compile(r"^([一二三四五六七八九十百]+)、\s*(.*)$")

_SOURCE_LETTER_DIGIT_RE = re.compile(r"^([A-H])(\d+)\.\s*(.*)$")
_SOURCE_CIRCLED_DIGIT_RE = re.compile(r"^([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳])\s*(.*)$")
_SOURCE_ARABIC_DIGIT_RE = re.compile(r"^(\d+)\.\s*(.*)$")

# Applied to whatever remains *after* the label prefix above has been
# stripped, since in both real syllabus files a priority symbol and/or an
# "R："/"R:" reference marker always comes right after the numeric label
# ("E5. R：Mauboussin...", "G1. ★ Competitive Programmer's Handbook"), never
# before it.
_LEADING_PRIORITY_RE = re.compile(r"^([★◎])\s*")
_LEADING_R_MARKER_RE = re.compile(r"^R[：:]\s*")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def _strip_priority_and_r_marker(remainder: str) -> tuple[str, Optional[str], bool]:
    """Given the text remaining after a heading's structural label prefix
    (module/source marker) has been removed, strips an optional leading
    ★/◎ priority symbol and/or an optional leading "R："/"R:" reference
    marker (order-independent -- either can appear, in either order, per
    the two real syllabus files), returning (clean_title, priority,
    is_r_marker)."""
    priority: Optional[str] = None
    is_r_marker = False
    changed = True
    while changed:
        changed = False
        m = _LEADING_PRIORITY_RE.match(remainder)
        if m:
            priority = m.group(1)
            remainder = remainder[m.end():]
            changed = True
            continue
        m = _LEADING_R_MARKER_RE.match(remainder)
        if m:
            is_r_marker = True
            remainder = remainder[m.end():]
            changed = True
    return remainder.strip(), priority, is_r_marker


def _classify_heading(
    text: str, depth: int
) -> tuple[str, str, Optional[str], bool, str]:
    """Returns (kind, clean_title, priority, is_r_marker, label_kind).
    kind is 'module', 'source', or 'unresolved'. clean_title has the
    leading label marker, priority symbol, and R-marker stripped, but is
    otherwise verbatim -- this function never rewrites the substance of a
    heading, only strips the structural prefix plan 8.2 calls a
    "候选 hint". label_kind names which rule fired (used by the caller to
    log a warning for the lower-confidence 'source_unlabeled_h2' case --
    see that branch below)."""
    text = text.strip()

    m = _MODULE_LETTER_RE.match(text)
    if m:
        clean, priority, is_r = _strip_priority_and_r_marker(m.group(2))
        return "module", clean, priority, is_r, "module_letter"
    m = _MODULE_CJK_NUM_RE.match(text)
    if m:
        clean, priority, is_r = _strip_priority_and_r_marker(m.group(2))
        return "module", clean, priority, is_r, "module_cjk"

    m = _SOURCE_LETTER_DIGIT_RE.match(text)
    if m:
        clean, priority, is_r = _strip_priority_and_r_marker(m.group(3))
        return "source", clean, priority, is_r, "source_letter_digit"
    m = _SOURCE_CIRCLED_DIGIT_RE.match(text)
    if m:
        clean, priority, is_r = _strip_priority_and_r_marker(m.group(2))
        return "source", clean, priority, is_r, "source_circled_digit"
    if depth == 2:
        m = _SOURCE_ARABIC_DIGIT_RE.match(text)
        if m:
            clean, priority, is_r = _strip_priority_and_r_marker(m.group(2))
            return "source", clean, priority, is_r, "source_arabic_digit"

    # Bare "R：..." heading with no numeric/letter label at all (not
    # observed in either real syllabus file today, but plan 8.4 treats
    # "R、reference、按需查阅" as a standalone semantic hint, so a syllabus
    # that someday writes it without a label should still be caught).
    clean, priority, is_r = _strip_priority_and_r_marker(text)
    if is_r:
        return "source", clean, priority, is_r, "source_bare_r"

    # Unlabeled H2 fallback. Both real syllabus files use H2 exclusively
    # for source-level items -- module headings are always H1 -- so an H2
    # with no recognized digit/letter/circled-digit label is still a real
    # paper/entry heading, just one this parser cannot confidently type
    # (e.g. "## ★ Tania Babina 2026 review", "## Kogut & Kulatilaka --
    # Capabilities as Real Options", both real H2s in 投资知识补充syllabus2.md
    # with no structural label at all). Classifying these as 'unresolved'
    # would not just skip a hint -- since unresolved headings still act as
    # body-slice boundaries, it would silently discard every line of real
    # paper-review text underneath them, which is a stronger violation of
    # plan 8.1 than emitting a low-confidence source with a review warning.
    if depth == 2:
        return "source", clean, priority, is_r, "source_unlabeled_h2"

    return "unresolved", text, None, False, "unresolved"


# ---------------------------------------------------------------------------
# Link parsing (plan 8.2: inline link, reference-style link, definition block)
# ---------------------------------------------------------------------------

_INLINE_LINK_RE = re.compile(r"\[([^\]]+)\]\((\S+?)(?:\s+\"[^\"]*\")?\)")
_REFERENCE_LINK_RE = re.compile(r"\[([^\]]+)\]\[(\w+)\]")
_DEFINITION_BLOCK_RE = re.compile(r'^\[(\w+)\]:\s*(\S+)(?:\s+"[^"]*")?\s*$')


def _collect_link_definitions(lines: list[str]) -> dict[str, str]:
    """One pass over the whole document collecting every `[N]: URL` block
    (both real syllabus files put these at the very end, but the plan does
    not require that -- this scans every line, not just a trailing
    section)."""
    definitions: dict[str, str] = {}
    for line in lines:
        m = _DEFINITION_BLOCK_RE.match(line.strip())
        if m:
            definitions[m.group(1)] = m.group(2)
    return definitions


def _extract_links(
    body_lines: list[str], start_line: int, definitions: dict[str, str]
) -> tuple[list[ParsedLink], list[str]]:
    """Extracts every inline and reference-style link from a section's
    body, in document order, resolving reference-style links against the
    document-wide `definitions` map. Returns (links, warnings) -- a
    reference like `[Title][99]` with no matching `[99]: url` definition
    anywhere in the file produces a warning instead of a silently dropped
    or guessed URL (plan 8.1)."""
    links: list[ParsedLink] = []
    warnings: list[str] = []
    for offset, line in enumerate(body_lines):
        line_no = start_line + offset
        for m in _INLINE_LINK_RE.finditer(line):
            links.append(ParsedLink(text=m.group(1), url=m.group(2), line=line_no, kind="inline"))
        for m in _REFERENCE_LINK_RE.finditer(line):
            label, ref = m.group(1), m.group(2)
            url = definitions.get(ref)
            if url is None:
                warnings.append(
                    f"line {line_no}: reference-style link '[{label}][{ref}]' has no "
                    f"matching '[{ref}]: URL' definition anywhere in the file"
                )
                continue
            links.append(ParsedLink(text=label, url=url, line=line_no, kind="reference"))
    return links, warnings


# ---------------------------------------------------------------------------
# Section-level hint extraction (plan 8.2 / 8.4)
# ---------------------------------------------------------------------------

_TIME_RANGE_RE = re.compile(r"(\d+)\s*[–-]\s*(\d+)\s*h\b")
_TIME_SINGLE_H_RE = re.compile(r"(\d+)\s*h\b")
_TIME_MIN_RE = re.compile(r"(\d+)\s*(?:min|分钟)\b")

_SCOPE_TRIGGER_RE = re.compile(
    r"(不完整刷[，,]?\s*只看[：:]|只看[：:]|特别只看[：:]|跳过或快速扫|"
    r"只读[一二三四五六七八九十\d]+章|不完整刷。)"
)

_EXTERNAL_PACED_KEYWORDS = ("跟随孩子", "跟着孩子", "孩子进度", "孩子走到哪里", "孩子共享", "外部任务")

_TYPE_URL_HINTS = (
    ("video", ("youtube.com", "youtu.be", "bilibili.com")),
    ("paper", ("arxiv.org", "doi.org", "sciencedirect.com", "onlinelibrary.wiley.com",
               "nber.org", "jstor.org", "pubsonline.informs.org", "sagepub.com")),
    ("book", ("oreilly.com",)),
)


def _guess_estimated_minutes(text: str) -> Optional[int]:
    m = _TIME_RANGE_RE.search(text)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return round((lo + hi) / 2 * 60)
    m = _TIME_SINGLE_H_RE.search(text)
    if m:
        return int(m.group(1)) * 60
    m = _TIME_MIN_RE.search(text)
    if m:
        return int(m.group(1))
    return None


def _guess_scope_note(body: str) -> Optional[str]:
    m = _SCOPE_TRIGGER_RE.search(body)
    if not m:
        return None
    # Capture from the trigger phrase through the end of that paragraph
    # (next blank line or end of body), verbatim -- plan 8.1 forbids
    # summarizing/rewriting this text, only locating it.
    start = m.start()
    rest = body[start:]
    para_end = rest.find("\n\n")
    return (rest if para_end == -1 else rest[:para_end]).strip()


def _guess_type(title: str, links: list[ParsedLink]) -> tuple[str, bool]:
    """Returns (type, was_inferred_with_confidence). When nothing matches,
    falls back to 'unclassified' rather than guessing a specific type
    (plan 8.1: leave unresolved fields empty/flagged, don't invent)."""
    for link in links:
        for guessed_type, hosts in _TYPE_URL_HINTS:
            if any(host in link.url for host in hosts):
                return guessed_type, True
    lowered = title.lower()
    if "course" in lowered or "cs3" in lowered or "stanford" in lowered or "课程" in title:
        return "course", True
    if "paper" in lowered or "论文" in title:
        return "paper", True
    return "unclassified", False


def _guess_resource_mode(
    heading_text: str, module_title: str, is_r_marker: bool
) -> tuple[str, Optional[str]]:
    """Returns (resource_mode, warning-or-None). Plan 8.4: R/reference ->
    resource_mode=reference; H/信息流 -> resource_mode=sensor."""
    if is_r_marker:
        return "reference", (
            f"resource_mode='reference' inferred from 'R:' marker in heading "
            f"'{heading_text.strip()}' -- candidate hint only, confirm via "
            f"`learn import approve`"
        )
    if module_title.startswith("长期信息输入") or "信息流" in module_title:
        return "sensor", (
            f"resource_mode='sensor' inferred from module '{module_title}' "
            f"(信息流/frontier-refresh module) -- candidate hint only, confirm "
            f"via `learn import approve`"
        )
    return "consumable", None


def _guess_pace_mode(module_title: str, body: str, module_is_g_like: bool) -> tuple[str, Optional[str]]:
    if module_is_g_like:
        return "external_paced", (
            f"pace_mode='external_paced' inferred from module '{module_title}' "
            "(G/algorithms-optionality module, plan 8.4's '跟随孩子/外部任务' "
            "mapping) -- candidate hint only, confirm via `learn import approve`"
        )
    for kw in _EXTERNAL_PACED_KEYWORDS:
        if kw in body:
            return "external_paced", (
                f"pace_mode='external_paced' inferred from body text containing "
                f"'{kw}' -- candidate hint only, confirm via `learn import approve`"
            )
    return "self_paced", None


# ---------------------------------------------------------------------------
# Learning-output detection (plan 8.2/8.4: Notebook/memo/map/ledger)
# ---------------------------------------------------------------------------

_BOLD_OUTPUT_RE = re.compile(
    r"\*\*([^*]*\b(?:Notebook|notebook|memo|Memo|ledger|Ledger|map|Map)\b[^*]*)\*\*"
)


def _find_learning_output_candidates(
    body_lines: list[str], start_line: int
) -> list[tuple[str, int]]:
    """Scans a body of text for bold-faced spans naming a Notebook/memo/
    map/ledger deliverable (plan 8.4: these become learning_outputs, "作为
    partial/strong evidence target，不能自动标记完成"). Returns (title, line)
    pairs, deduplicated by exact title within this call -- cross-section/
    cross-file dedup happens later in import_syllabus() against already-
    persisted rows."""
    seen: dict[str, int] = {}
    for offset, line in enumerate(body_lines):
        for m in _BOLD_OUTPUT_RE.finditer(line):
            title = m.group(1).strip().strip("\u201c\u201d\"'")
            if title and title not in seen:
                seen[title] = start_line + offset
    return list(seen.items())


# ---------------------------------------------------------------------------
# Main parse
# ---------------------------------------------------------------------------

_G_MODULE_TITLE_HINTS = ("Algorithms", "OI", "算法")


def parse_syllabus(path: str | Path) -> ImportReport:
    """Pure parse: no DB access. Reads the file at `path` and returns an
    ImportReport describing every module/source/learning-output candidate
    found, plus unresolved headings and warnings. Safe to call repeatedly
    against an unmodified file and get byte-identical results (each
    ParsedSource's content_hash is deterministic from its own heading+body
    text, per plan 8.2's "用 file path + heading + content hash 实现幂等
    导入")."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    source_file = path.name

    report = ImportReport(source_file=source_file)
    definitions = _collect_link_definitions(lines)

    # Pass 1: locate every H1/H2 heading and classify it.
    headings: list[tuple[int, int, str, str, Optional[str], bool, str]] = []
    # (line_no, depth, kind, clean_title, priority, is_r_marker, label_kind)
    raw_headings: dict[int, str] = {}
    for idx, line in enumerate(lines, start=1):
        m = _HEADING_RE.match(line)
        if not m:
            continue
        depth = len(m.group(1))
        if depth > 2:
            continue
        raw_text = m.group(2).strip()
        kind, clean_title, priority, is_r_marker, label_kind = _classify_heading(raw_text, depth)
        headings.append((idx, depth, kind, clean_title, priority, is_r_marker, label_kind))
        raw_headings[idx] = raw_text
        if kind == "unresolved":
            report.unresolved.append(f"{source_file}:{idx}: unclassified heading '{raw_text}'")
        elif label_kind == "source_unlabeled_h2":
            report.warnings.append(
                f"{source_file}:{idx}: heading '{raw_text}' has no recognized "
                "numeric/letter/circled-digit label -- treated as a low-confidence "
                "source (H2 headings are never meta-only in either real syllabus "
                "file) so its body text is not silently dropped; verify via "
                "`learn import approve` before treating it as accurate"
            )

    # Pass 2: walk headings in order, tracking the current module, and
    # slice out each section's body (up to the next H1/H2 heading).
    heading_lines = [h[0] for h in headings] + [len(lines) + 1]
    current_module_order = -1
    module_has_source = set()
    modules_by_order: list[ParsedModule] = []

    def _body_slice(heading_idx: int, next_heading_line: int) -> list[str]:
        return lines[heading_idx:next_heading_line - 1]

    # (line_no, raw, clean_title, body, priority, is_r_marker)
    pending_sources: list[tuple[int, str, str, list[str], Optional[str], bool]] = []

    for i, (line_no, depth, kind, clean_title, priority, is_r_marker, _label_kind) in enumerate(headings):
        next_line = heading_lines[i + 1]
        body = _body_slice(line_no, next_line)
        raw = raw_headings[line_no]

        if kind == "module":
            module = ParsedModule(
                title=clean_title, raw_heading=raw, source_file=source_file,
                source_line=line_no, order=len(modules_by_order),
            )
            modules_by_order.append(module)
            report.modules.append(module)
            current_module_order = module.order
        elif kind == "source":
            if current_module_order == -1:
                report.warnings.append(
                    f"{source_file}:{line_no}: source '{clean_title}' appears before any "
                    "module heading -- skipped (cannot attribute to a module without "
                    "guessing one)"
                )
                continue
            pending_sources.append((line_no, raw, clean_title, body, priority, is_r_marker))
            module_has_source.add(current_module_order)

    # Pass 3: build ParsedSource rows, plus learning-output candidates
    # scanned over every section body (module and source bodies alike).
    all_bodies: list[tuple[int, str, list[str]]] = []  # (line_no, module_title, body)
    for line_no, _raw, _clean, body, _priority, _is_r in pending_sources:
        all_bodies.append((line_no, "", body))
    for module in modules_by_order:
        idx = next(i for i, h in enumerate(headings) if h[0] == module.source_line)
        next_line = heading_lines[idx + 1]
        all_bodies.append((module.source_line, module.title, _body_slice(module.source_line, next_line)))

    seen_output_titles: set[str] = set()
    for line_no, _module_title, body in all_bodies:
        for title, out_line in _find_learning_output_candidates(body, line_no + 1):
            if title in seen_output_titles:
                continue
            seen_output_titles.add(title)
            owning_module_order = current_module_order
            for m2 in modules_by_order:
                if m2.source_line <= out_line:
                    owning_module_order = m2.order
            report.learning_outputs.append(
                ParsedLearningOutput(
                    title=title, module_order=owning_module_order,
                    source_file=source_file, source_line=out_line,
                    raw_context=body[min(out_line - line_no - 1, len(body) - 1)].strip()
                    if body else title,
                )
            )

    def _make_source(
        line_no: int, raw: str, clean_title: str, body: list[str], module_order: int,
        synthesized: bool, priority: Optional[str] = None, is_r_marker: bool = False,
    ) -> ParsedSource:
        module_title = modules_by_order[module_order].title
        body_text = "\n".join(body)
        links, link_warnings = _extract_links(body, line_no + 1, definitions)
        report.warnings.extend(link_warnings)

        is_g_like = any(h in module_title for h in _G_MODULE_TITLE_HINTS)
        resource_mode, rm_warning = _guess_resource_mode(raw, module_title, is_r_marker)
        pace_mode, pm_warning = _guess_pace_mode(module_title, body_text, is_g_like)
        if rm_warning:
            report.warnings.append(f"{source_file}:{line_no}: {rm_warning}")
        if pm_warning:
            report.warnings.append(f"{source_file}:{line_no}: {pm_warning}")

        scope_note = _guess_scope_note(body_text)
        scope_confirmed = scope_note is None
        if scope_note is not None:
            report.warnings.append(
                f"{source_file}:{line_no}: scope_note candidate extracted for "
                f"'{clean_title}': {scope_note!r} -- scope_confirmed=False until "
                "explicitly confirmed via `learn import approve --confirm-scope`"
            )

        estimated_minutes = _guess_estimated_minutes(body_text) or _guess_estimated_minutes(raw)
        src_type, type_confident = _guess_type(clean_title, links)
        if not type_confident:
            report.warnings.append(
                f"{source_file}:{line_no}: could not infer a specific type for "
                f"'{clean_title}' from heading/link text -- defaulted to 'unclassified'"
            )
        if priority:
            report.warnings.append(
                f"{source_file}:{line_no}: priority hint '{priority}' extracted from "
                f"'{raw}' -- candidate only, does not auto-affect scheduling"
            )

        content_hash = hashlib.sha256((raw + "\n" + body_text).encode("utf-8")).hexdigest()
        return ParsedSource(
            title=clean_title, raw_heading=raw, source_file=source_file,
            source_line=line_no, module_order=module_order, type=src_type,

            resource_mode=resource_mode, pace_mode=pace_mode, priority=priority,
            scope_note=scope_note, scope_confirmed=scope_confirmed,
            estimated_minutes=estimated_minutes,
            url_or_path=links[0].url if links else None,
            content_hash=content_hash, links=links,
            synthesized_from_module=synthesized,
        )

    for line_no, raw, clean_title, body, priority, is_r_marker in pending_sources:
        module_order = -1
        for m2 in modules_by_order:
            if m2.source_line <= line_no:
                module_order = m2.order
        report.sources.append(
            _make_source(
                line_no, raw, clean_title, body, module_order, False,
                priority, is_r_marker,
            )
        )

    # Modules with zero attributed sources: synthesize one source from the
    # module's own body (see module docstring above -- covers module H in
    # 投资技术学习清单.md, the "H/sensor source" M1 fixture requirement).
    for module in modules_by_order:
        if module.order in module_has_source:
            continue
        idx = next(i for i, h in enumerate(headings) if h[0] == module.source_line)
        next_line = heading_lines[idx + 1]
        body = _body_slice(module.source_line, next_line)
        if not any(line.strip() for line in body):
            continue  # truly empty module (e.g. just a divider) -- nothing to extract
        report.warnings.append(
            f"{source_file}:{module.source_line}: module '{module.title}' has no "
            "labeled H1/H2 sub-sections -- synthesized one source from the module's "
            "own body text so its content is not silently dropped"
        )
        report.sources.append(
            _make_source(
                module.source_line, module.raw_heading, module.title, body,
                module.order, True,
            )
        )

    # Duplicate-candidate detection within this single parse (cross-file
    # dedup against already-persisted rows happens in import_syllabus()).
    by_clean_title: dict[str, list[ParsedSource]] = {}
    for src in report.sources:
        key = src.title.strip().casefold()
        by_clean_title.setdefault(key, []).append(src)
    for key, group in by_clean_title.items():
        if len(group) > 1:
            report.duplicate_candidates.append(
                DuplicateCandidate(
                    clean_title=group[0].title,
                    occurrences=[(s.source_file, s.source_line, s.raw_heading) for s in group],
                )
            )

    return report


# ---------------------------------------------------------------------------
# import_syllabus: write side, via repositories only
# ---------------------------------------------------------------------------

def _slugify(title: str) -> Optional[str]:
    ascii_part = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").lower()
    # Require a minimum of real ASCII content -- a title that is almost
    # entirely CJK text would otherwise collapse to an empty or
    # near-empty slug; sources.slug is nullable precisely for this case
    # (repositories.py: "not every source is meant to be addressed
    # directly"), so leaving it None here is correct, not a shortcut.
    if len(re.sub(r"-", "", ascii_part)) < 3:
        return None
    return ascii_part[:60]


def import_syllabus(conn: sqlite3.Connection, path: str | Path) -> ImportReport:
    """Parses `path` and persists every module/source/learning-output
    candidate as a PROPOSED draft (plan 8.3's `parse -> report -> persist
    draft` steps; the remaining `approve PROPOSED -> QUEUED` step is a
    separate, explicit CLI command -- see `learn import approve` -- never
    triggered automatically here).

    Idempotent by (source_file, source_line) + content_hash (plan 8.2):
    - a heading never seen before at this exact file+line becomes a new
      row (unless its clean title duplicates an already-persisted source
      from a *different* location -- see the Teece-1986-in-two-files case
      below, which is recorded as a duplicate candidate and NOT inserted
      as a second row);
    - a heading already imported as PROPOSED/VISIBLE is safe to re-parse:
      its metadata columns are refreshed if the content changed;
    - a heading already imported and since moved to QUEUED or beyond
      (i.e. a real consumable source the user has started acting on) is
      never silently overwritten -- a content change there only adds a
      warning, exactly as plan 8.2 specifies.
    """
    report = parse_syllabus(path)

    modules = ModuleRepository(conn)
    sources = SourceRepository(conn)
    outputs = LearningOutputRepository(conn)

    file_key = hashlib.sha1(report.source_file.encode("utf-8")).hexdigest()[:8]

    module_ids: dict[int, int] = {}
    for module in report.modules:
        slug = f"import-{file_key}-m{module.order:02d}"
        try:
            existing = modules.get_by_slug(slug)
            module_ids[module.order] = existing.id
            continue
        except KeyError:
            pass
        created = modules.create(
            slug=slug, name=module.title, phase=1,
            notes=(
                f"Imported from {module.source_file}:{module.source_line} "
                f"('{module.raw_heading}') by `learn import-syllabus` -- a separate "
                "object from any hand-seeded module covering similar ground, "
                "since the importer cannot reliably guess a merge (plan 8.1)."
            ),
        )
        module_ids[module.order] = created.id
        report.modules_created += 1

    existing_sources_by_title: dict[str, "list[tuple[str,int]]"] = {}
    used_slugs: set[str] = set()
    for existing in sources.list_all():
        existing_sources_by_title.setdefault(existing.title.strip().casefold(), []).append(
            (existing.source_file or "", existing.source_line or -1)
        )
        if existing.slug:
            used_slugs.add(existing.slug)

    for src in report.sources:
        key = src.title.strip().casefold()
        existing_locations = existing_sources_by_title.get(key, [])
        other_location_dup = [
            loc for loc in existing_locations
            if loc != (src.source_file, src.source_line)
        ]

        found = sources.find_by_location(src.source_file, src.source_line)
        if found is None:
            if other_location_dup:
                dup_file, dup_line = other_location_dup[0]
                report.duplicate_candidates.append(
                    DuplicateCandidate(
                        clean_title=src.title,
                        occurrences=[
                            (dup_file, dup_line, "(already persisted)"),
                            (src.source_file, src.source_line, src.raw_heading),
                        ],
                    )
                )
                report.sources_skipped_duplicate += 1
                continue
            # Two distinct titles can collapse to the same ASCII slug once
            # CJK text is stripped (real example: "Codex：我认为长期价值反而
            # 最大" and "让 Codex 做哪些工作？" both slugify to "codex" --
            # neither is a duplicate of the other, they are different real
            # headings). sources.slug has a UNIQUE constraint and is
            # nullable precisely for titles too CJK-heavy to slug reliably
            # (see _slugify's own docstring) -- a slug collision between
            # two *different* titles is the same kind of "not enough
            # reliable signal" case, so this drops to None here rather
            # than inventing a disambiguating suffix (plan 8.1: don't
            # guess-fill).
            slug = _slugify(src.title)
            if slug is not None and slug in used_slugs:
                report.warnings.append(
                    f"{src.source_file}:{src.source_line}: slug '{slug}' for "
                    f"'{src.title}' collides with an already-persisted source's "
                    "slug -- left unset (slug is optional; not a content duplicate)"
                )
                slug = None
            if slug is not None:
                used_slugs.add(slug)
            created = sources.create(
                module_id=module_ids[src.module_order], title=src.title, type=src.type,
                resource_mode=src.resource_mode, pace_mode=src.pace_mode,
                slug=slug, url_or_path=src.url_or_path,
                estimated_minutes=src.estimated_minutes, priority=src.priority,
                scope_note=src.scope_note, scope_confirmed=src.scope_confirmed,
                source_file=src.source_file, source_line=src.source_line,
                content_hash=src.content_hash,
            )
            existing_sources_by_title.setdefault(key, []).append(
                (src.source_file, src.source_line)
            )
            report.sources_created += 1
            continue

        if found.content_hash == src.content_hash:
            continue  # unchanged, nothing to do

        if found.status in ("PROPOSED", "VISIBLE"):
            sources.update_draft_fields(
                found.id, title=src.title, type=src.type,
                resource_mode=src.resource_mode, pace_mode=src.pace_mode,
                url_or_path=src.url_or_path, estimated_minutes=src.estimated_minutes,
                priority=src.priority, scope_note=src.scope_note,
                scope_confirmed=src.scope_confirmed, content_hash=src.content_hash,
            )
            report.sources_updated += 1
        else:
            report.warnings.append(
                f"{src.source_file}:{src.source_line}: source '{src.title}' content "
                f"changed since last import, but it is already {found.status} -- not "
                "auto-updated (plan 8.2: only PROPOSED/VISIBLE sources are re-parsed)"
            )
            report.sources_skipped_locked += 1

    for out in report.learning_outputs:
        module_id = module_ids[out.module_order]
        already = any(o.title == out.title for o in outputs.list_by_module(module_id))
        if already:
            continue
        outputs.create(
            module_id=module_id, title=out.title, kind="notebook_or_memo",
            source_file=out.source_file, source_line=out.source_line,
        )
        report.learning_outputs_created += 1

    return report
