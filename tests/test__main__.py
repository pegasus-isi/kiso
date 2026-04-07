"""CLI integration tests for kiso.__main__."""

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from kiso.__main__ import kiso
from kiso.errors import KisoError


def test_kiso_help() -> None:
    runner = CliRunner()
    result = runner.invoke(kiso, ["--help"])
    assert result.exit_code == 0


def test_check_help() -> None:
    runner = CliRunner()
    result = runner.invoke(kiso, ["check", "--help"])
    assert result.exit_code == 0


def test_check_valid_config(resource_path_root: Path) -> None:
    config = resource_path_root / "check" / "test-1.yml"
    runner = CliRunner()
    with patch("kiso.task.en.check"):
        result = runner.invoke(kiso, ["check", str(config)])
    assert result.exit_code == 0, result.output


def test_check_invalid_config(resource_path_root: Path) -> None:
    config = resource_path_root / "check" / "test-invalid.yml"
    runner = CliRunner()
    result = runner.invoke(kiso, ["check", str(config)])
    assert result.exit_code != 0


def test_check_nonexistent_file() -> None:
    runner = CliRunner()
    result = runner.invoke(kiso, ["check", "nonexistent.yml"])
    assert result.exit_code != 0


def test_up_help() -> None:
    runner = CliRunner()
    result = runner.invoke(kiso, ["up", "--help"])
    assert result.exit_code == 0


def test_run_help() -> None:
    runner = CliRunner()
    result = runner.invoke(kiso, ["run", "--help"])
    assert result.exit_code == 0


def test_down_help() -> None:
    runner = CliRunner()
    result = runner.invoke(kiso, ["down", "--help"])
    assert result.exit_code == 0


def test_check_debug_flag() -> None:
    runner = CliRunner()
    result = runner.invoke(kiso, ["--debug", "check", "--help"])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# up / run / down — success and error paths
# ---------------------------------------------------------------------------


def test_up_success_path(resource_path_root: Path) -> None:
    config = resource_path_root / "check" / "test-1.yml"
    runner = CliRunner()
    with patch("kiso.task.up"):
        result = runner.invoke(kiso, ["up", str(config)])
    assert "Success" in result.output


def test_up_error_path(resource_path_root: Path) -> None:
    config = resource_path_root / "check" / "test-1.yml"
    runner = CliRunner()
    with patch("kiso.task.up", side_effect=RuntimeError("boom")):
        result = runner.invoke(kiso, ["up", str(config)])
    assert "Error" in result.output


def test_run_success_path(resource_path_root: Path) -> None:
    config = resource_path_root / "check" / "test-1.yml"
    runner = CliRunner()
    with patch("kiso.task.run"):
        result = runner.invoke(kiso, ["run", str(config)])
    assert "Success" in result.output


def test_run_error_path(resource_path_root: Path) -> None:
    config = resource_path_root / "check" / "test-1.yml"
    runner = CliRunner()
    with patch("kiso.task.run", side_effect=RuntimeError("boom")):
        result = runner.invoke(kiso, ["run", str(config)])
    assert "Error" in result.output


def test_down_success_path(resource_path_root: Path) -> None:
    config = resource_path_root / "check" / "test-1.yml"
    runner = CliRunner()
    with patch("kiso.task.down"):
        result = runner.invoke(kiso, ["down", str(config)])
    assert "Success" in result.output


def test_down_error_path(resource_path_root: Path) -> None:
    config = resource_path_root / "check" / "test-1.yml"
    runner = CliRunner()
    with patch("kiso.task.down", side_effect=RuntimeError("boom")):
        result = runner.invoke(kiso, ["down", str(config)])
    assert "Error" in result.output


# ---------------------------------------------------------------------------
# ssh
# ---------------------------------------------------------------------------


def test_ssh_help() -> None:
    runner = CliRunner()
    result = runner.invoke(kiso, ["ssh", "--help"])
    assert result.exit_code == 0


def test_ssh_kiso_error_is_caught() -> None:
    runner = CliRunner()
    with patch("kiso.task.ssh", side_effect=KisoError("node not found")):
        result = runner.invoke(kiso, ["ssh", "worker1"])
    assert result.exit_code != 0
    assert "Error" in result.output


def test_ssh_generic_exception_is_caught() -> None:
    runner = CliRunner()
    with patch("kiso.task.ssh", side_effect=RuntimeError("boom")):
        result = runner.invoke(kiso, ["ssh", "worker1"])
    assert result.exit_code != 0
    assert "Error" in result.output
