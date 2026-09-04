from typer.testing import CliRunner

from learning_os.cli import app


runner = CliRunner()


def test_curriculum_show_defaults_to_current_week():
    result = runner.invoke(
        app,
        ["curriculum", "show", "--date", "2026-09-04"],
    )

    assert result.exit_code == 0, result.output
    assert "week=1/16" in result.output
    assert "AI stack" in result.output
    assert "AI Profit Pool Map v1" in result.output


def test_curriculum_show_can_select_a_future_week():
    result = runner.invoke(app, ["curriculum", "show", "--week", "8"])

    assert result.exit_code == 0, result.output
    assert "week=8/16" in result.output
    assert "price" in result.output.lower()
    assert "Price-implied thesis" in result.output


def test_curriculum_show_rejects_bad_date_cleanly():
    result = runner.invoke(app, ["curriculum", "show", "--date", "not-a-date"])

    assert result.exit_code != 0
    assert "YYYY-MM-DD" in result.output
