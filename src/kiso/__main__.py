"""Summary.

_extended_summary_
"""

# ruff: noqa: ARG001

import os
import traceback
from pathlib import Path

import enoslib as en
import rich_click as click

from kiso import task, version

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}
EPILOG = f"Check out our docs at {version.__documentation__} for more details."
DEFAULT_EXPERIMENT_CONFIG = "experiment.yml"


@click.group(context_settings=CONTEXT_SETTINGS, epilog=EPILOG)
@click.pass_context
def kiso(ctx: click.Context) -> None:
    """🏇 Kiso: Edge to Cloud Workflows: Advancing Workflow Management in the Computing Continuum."""  # noqa: E501
    click.secho(
        rf""" _   __ _
| | / /(_)
| |/ /  _  ___   ___
|    \ | |/ __| / _ \
| |\  \| |\__ \| (_) |
\_| \_/|_||___/ \___/  {version.__version__}
""",
        fg="magenta",
    )

    en.init_logging()

    # TODO(mayani): Change the output en.config._set("ansible_stdout", "noop")
    # en.set_config(ansible_stdout="spinner")


@kiso.command(epilog=EPILOG)
@click.pass_context
@click.argument(
    "experiment-config",
    required=False,
    default=DEFAULT_EXPERIMENT_CONFIG,
    type=click.Path(file_okay=True, dir_okay=False, readable=True, exists=True),
)
def check(ctx: click.Context, experiment_config: os.PathLike) -> None:
    """Check the experiment configuration."""
    try:
        task.check(experiment_config=Path(experiment_config))
        click.secho("✨ Success", fg="green")
    except Exception as e:
        _error(ctx, e)


@kiso.command(epilog=EPILOG)
@click.pass_context
@click.option(
    "--output",
    "-o",
    type=click.Path(file_okay=False, dir_okay=True, exists=False),
    default="output",
    help="Environment to use for the experiment.",
)
@click.argument(
    "experiment-config",
    required=False,
    default=DEFAULT_EXPERIMENT_CONFIG,
    type=click.Path(file_okay=True, dir_okay=False, readable=True, exists=True),
)
def up(ctx: click.Context, output: str, experiment_config: os.PathLike) -> None:
    """Create the resources needed to run the experiment."""
    try:
        task.up(env=output, experiment_config=Path(experiment_config))
        click.secho("✨ Success", fg="green")
    except Exception as e:
        _error(ctx, e)


@kiso.command(epilog=EPILOG)
@click.pass_context
@click.option(
    "--output",
    "-o",
    type=click.Path(file_okay=False, dir_okay=True, exists=False),
    default="output",
    help="Environment to use for the experiment.",
)
@click.argument(
    "experiment-config",
    required=False,
    default=DEFAULT_EXPERIMENT_CONFIG,
    type=click.Path(file_okay=True, dir_okay=False, readable=True, exists=True),
)
def run(
    ctx: click.Context, output: os.PathLike, experiment_config: os.PathLike
) -> None:
    """Run the defined experiments."""
    try:
        task.run(env=output, experiment_config=Path(experiment_config))
        click.secho("✨ Success", fg="green")
    except Exception as e:
        _error(ctx, e)


@kiso.command(epilog=EPILOG)
@click.pass_context
@click.option(
    "--output",
    "-o",
    type=click.Path(file_okay=False, dir_okay=True, exists=False),
    default="output",
    help="Environment to use for the experiment.",
)
@click.argument(
    "experiment-config",
    required=False,
    default=DEFAULT_EXPERIMENT_CONFIG,
    type=click.Path(file_okay=True, dir_okay=False, readable=True, exists=True),
)
def down(
    ctx: click.Context, output: os.PathLike, experiment_config: os.PathLike
) -> None:
    """Destroy the resources provisioned for the experiments."""
    try:
        task.down(env=output, experiment_config=Path(experiment_config))
        click.secho("✨ Success", fg="green")
    except Exception as e:
        _error(ctx, e)


def _error(ctx: click.Context, e: Exception, ec: int = 1) -> None:
    """Handle errors."""
    click.secho("Error", fg="red")
    print(e)
    traceback.print_exc()
    ctx.exit(ec)


if __name__ == "__main__":
    kiso()
