from datetime import date

import pytest

from learning_os.services.curriculum_loader import CurriculumFormatError, load_curriculum


MANIFEST = "content/core_curriculum.yaml"


def test_core_curriculum_is_a_complete_ordered_16_week_manifest():
    curriculum = load_curriculum(MANIFEST)

    assert curriculum.slug == "core-tech-change-to-position"
    assert curriculum.duration_weeks == 16
    assert [week.week for week in curriculum.weekly] == list(range(1, 17))
    assert curriculum.north_star[-1] == "Position"
    assert len(curriculum.longitudinal_projects) == 3
    assert all(week.question and week.output for week in curriculum.weekly)


def test_current_week_uses_explicit_start_date_and_is_bounded():
    curriculum = load_curriculum(MANIFEST)

    assert curriculum.week_for_date(date(2026, 8, 30)) == 0
    assert curriculum.week_for_date(date(2026, 8, 31)) == 1
    assert curriculum.week_for_date(date(2026, 9, 4)) == 1
    assert curriculum.week_for_date(date(2026, 9, 7)) == 2
    assert curriculum.week_for_date(date(2026, 12, 20)) == 16
    assert curriculum.week_for_date(date(2026, 12, 21)) == 17


def test_loader_rejects_missing_week_without_guessing(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        "curriculum:\n"
        "  slug: bad\n"
        "  start_date: '2026-01-01'\n"
        "  duration_weeks: 1\n"
        "  weekly: []\n",
        encoding="utf-8",
    )

    with pytest.raises(CurriculumFormatError, match="weekly must contain exactly 1"):
        load_curriculum(path)
