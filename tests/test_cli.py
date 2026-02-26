from typer.testing import CliRunner

from course_step_extractor.cli import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_sample_command_outputs_markdown() -> None:
    result = runner.invoke(app, ["sample"])
    assert result.exit_code == 0
    assert "## Open video" in result.stdout
