"""Load and navigate the active, project-led core curriculum.

The curriculum is orchestration metadata, not a second content database:
weekly plans describe the question, selective learning, project, decision
reps, and output. Sources/concepts/items remain in the existing content and
SQLite pipelines. This keeps a curriculum week from being mistaken for a
mastered concept or from silently entering the review queue.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml


class CurriculumFormatError(ValueError):
    """Raised when a curriculum manifest is incomplete or inconsistent."""


@dataclass(frozen=True)
class CurriculumLearning:
    ref: str
    title: str
    scope: str
    url: Optional[str] = None


@dataclass(frozen=True)
class CurriculumWeek:
    week: int
    question: str
    learning: tuple[CurriculumLearning, ...]
    project: str
    decision_reps: str
    output: str


@dataclass(frozen=True)
class CurriculumProject:
    slug: str
    name: str
    scope: str
    final_goal: str


@dataclass(frozen=True)
class Curriculum:
    slug: str
    name: str
    version: str
    start_date: date
    timezone: str
    duration_weeks: int
    weekly_hours: str
    north_star: tuple[str, ...]
    operating_principle: str
    weekly: tuple[CurriculumWeek, ...]
    longitudinal_projects: tuple[CurriculumProject, ...]
    minimum_reading: dict[str, tuple[str, ...]]
    graduation_outputs: tuple[str, ...]
    after_curriculum: dict[str, Any]

    def today(self) -> date:
        """Return today's date in the manifest's declared timezone."""
        try:
            return datetime.now(ZoneInfo(self.timezone)).date()
        except ZoneInfoNotFoundError as exc:
            raise CurriculumFormatError(
                f"curriculum.timezone is not available: {self.timezone}"
            ) from exc

    def week_for_date(self, on_date: date) -> int:
        """Return 0 before start, 1..N during the curriculum, N+1 after."""
        delta = (on_date - self.start_date).days
        if delta < 0:
            return 0
        return min(delta // 7 + 1, self.duration_weeks + 1)

    def get_week(self, week_number: int) -> CurriculumWeek:
        if not 1 <= week_number <= self.duration_weeks:
            raise KeyError(f"week {week_number} is outside 1..{self.duration_weeks}")
        return self.weekly[week_number - 1]


def _required(mapping: dict[str, Any], key: str, context: str) -> Any:
    value = mapping.get(key)
    if value is None or value == "":
        raise CurriculumFormatError(f"{context} is missing required field '{key}'")
    return value


def _as_string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CurriculumFormatError(f"{context} must be a non-empty string")
    return value.strip()


def load_curriculum(path: str | Path) -> Curriculum:
    """Parse and validate one YAML manifest without touching SQLite."""
    path = Path(path)
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
    except FileNotFoundError:
        raise
    except yaml.YAMLError as exc:
        raise CurriculumFormatError(f"invalid YAML: {exc}") from exc

    if not isinstance(raw, dict) or not isinstance(raw.get("curriculum"), dict):
        raise CurriculumFormatError("root must contain a 'curriculum' mapping")
    data = raw["curriculum"]
    context = "curriculum"

    try:
        start_date = date.fromisoformat(_as_string(_required(data, "start_date", context), "curriculum.start_date"))
    except ValueError as exc:
        raise CurriculumFormatError("curriculum.start_date must be YYYY-MM-DD") from exc

    duration = _required(data, "duration_weeks", context)
    if not isinstance(duration, int) or duration <= 0:
        raise CurriculumFormatError("curriculum.duration_weeks must be a positive integer")

    weeks_raw = _required(data, "weekly", context)
    if not isinstance(weeks_raw, list) or len(weeks_raw) != duration:
        raise CurriculumFormatError(
            f"curriculum.weekly must contain exactly {duration} entries"
        )
    weeks: list[CurriculumWeek] = []
    for expected_week, item in enumerate(weeks_raw, start=1):
        if not isinstance(item, dict):
            raise CurriculumFormatError(f"curriculum.weekly[{expected_week}] must be a mapping")
        actual_week = _required(item, "week", f"curriculum.weekly[{expected_week}]")
        if actual_week != expected_week:
            raise CurriculumFormatError(
                f"curriculum.weekly must be ordered and numbered 1..{duration}; "
                f"expected {expected_week}, got {actual_week}"
            )
        learning_raw = _required(item, "learning", f"week {expected_week}")
        if not isinstance(learning_raw, list) or not learning_raw:
            raise CurriculumFormatError(f"week {expected_week}.learning must be non-empty")
        learning: list[CurriculumLearning] = []
        for index, source in enumerate(learning_raw, start=1):
            if not isinstance(source, dict):
                raise CurriculumFormatError(f"week {expected_week}.learning[{index}] must be a mapping")
            source_context = f"week {expected_week}.learning[{index}]"
            learning.append(
                CurriculumLearning(
                    ref=_as_string(_required(source, "ref", source_context), f"{source_context}.ref"),
                    title=_as_string(_required(source, "title", source_context), f"{source_context}.title"),
                    scope=_as_string(_required(source, "scope", source_context), f"{source_context}.scope"),
                    url=source.get("url"),
                )
            )
        weeks.append(
            CurriculumWeek(
                week=expected_week,
                question=_as_string(_required(item, "question", f"week {expected_week}"), f"week {expected_week}.question"),
                learning=tuple(learning),
                project=_as_string(_required(item, "project", f"week {expected_week}"), f"week {expected_week}.project"),
                decision_reps=_as_string(_required(item, "decision_reps", f"week {expected_week}"), f"week {expected_week}.decision_reps"),
                output=_as_string(_required(item, "output", f"week {expected_week}"), f"week {expected_week}.output"),
            )
        )

    projects_raw = _required(data, "longitudinal_projects", context)
    if not isinstance(projects_raw, list) or not projects_raw:
        raise CurriculumFormatError("curriculum.longitudinal_projects must be non-empty")
    projects = tuple(
        CurriculumProject(
            slug=_as_string(_required(project, "slug", "longitudinal project"), "project.slug"),
            name=_as_string(_required(project, "name", "longitudinal project"), "project.name"),
            scope=_as_string(_required(project, "scope", "longitudinal project"), "project.scope"),
            final_goal=_as_string(_required(project, "final_goal", "longitudinal project"), "project.final_goal"),
        )
        for project in projects_raw
    )

    reading_raw = data.get("minimum_reading", {})
    if not isinstance(reading_raw, dict):
        raise CurriculumFormatError("curriculum.minimum_reading must be a mapping")
    reading = {
        str(kind): tuple(_as_string(entry, f"minimum_reading.{kind}") for entry in entries)
        for kind, entries in reading_raw.items()
        if isinstance(entries, list)
    }
    if set(reading) != set(reading_raw):
        raise CurriculumFormatError("every minimum_reading category must be a list")

    outputs_raw = _required(data, "graduation_outputs", context)
    if not isinstance(outputs_raw, list) or not outputs_raw:
        raise CurriculumFormatError("curriculum.graduation_outputs must be non-empty")

    return Curriculum(
        slug=_as_string(_required(data, "slug", context), "curriculum.slug"),
        name=_as_string(_required(data, "name", context), "curriculum.name"),
        version=_as_string(_required(data, "version", context), "curriculum.version"),
        start_date=start_date,
        timezone=_as_string(_required(data, "timezone", context), "curriculum.timezone"),
        duration_weeks=duration,
        weekly_hours=_as_string(_required(data, "weekly_hours", context), "curriculum.weekly_hours"),
        north_star=tuple(_as_string(value, "curriculum.north_star") for value in _required(data, "north_star", context)),
        operating_principle=_as_string(_required(data, "operating_principle", context), "curriculum.operating_principle"),
        weekly=tuple(weeks),
        longitudinal_projects=projects,
        minimum_reading=reading,
        graduation_outputs=tuple(_as_string(value, "curriculum.graduation_outputs") for value in outputs_raw),
        after_curriculum=data.get("after_curriculum", {}),
    )


def current_week(path: str | Path, on_date: Optional[date] = None) -> tuple[Curriculum, int]:
    curriculum = load_curriculum(path)
    return curriculum, curriculum.week_for_date(on_date or curriculum.today())
