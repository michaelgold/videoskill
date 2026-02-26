import typer

from course_step_extractor.models import Step

app = typer.Typer(help="Course step extraction CLI", no_args_is_help=True)


@app.command("version")
def version() -> None:
    typer.echo("0.1.0")


@app.command("sample")
def sample() -> None:
    """Emit a sample markdown step."""
    step = Step(title="Open video", description="Load the video file and transcript.")
    typer.echo(f"## {step.title}\n\n- {step.description}")
