"""Pre-commit hook: run mypy or pylint for each affected service using its own venv."""

import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Run mypy or pylint for each service that has staged changes.

    Receives the tool name as the first argument and file paths from pre-commit
    as the remaining arguments. Groups files by their service root under
    services/<name>/, then runs the tool once per affected service using that
    service's own venv via uv run --directory.

    Returns
    -------
    int
        0 if all checks pass across all services, non-zero if any check fails.
    """
    if len(sys.argv) < 2:
        print("Usage: lint_service.py <mypy|pylint> [files...]")
        return 1

    tool = sys.argv[1]
    files = [Path(f) for f in sys.argv[2:]]

    service_roots: set[Path] = set()
    for f in files:
        root = _service_root(f)
        if root and root.exists():
            service_roots.add(root)

    if not service_roots:
        return 0

    exit_code = 0
    for service_root in sorted(service_roots):
        if not _venv_ready(service_root):
            _print_venv_missing_help(service_root)
            return 1

        cmd = _build_command(tool, service_root)
        if cmd is None:
            print(f"Unknown tool: {tool}")
            return 1

        print(f"[{tool}] {service_root}")
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            exit_code = result.returncode

    return exit_code


def _service_root(file_path: Path) -> Path | None:
    """Return the service root directory for a file under services/<name>/, or None.

    Parameters
    ----------
    file_path : Path
        Absolute or relative path to a Python file.

    Returns
    -------
    Path | None
        The path services/<name>/ if the file lives under a service, else None.
    """
    parts = list(file_path.parts)
    if "services" not in parts:
        return None
    services_idx = parts.index("services")
    if len(parts) <= services_idx + 1:
        return None
    return Path(*parts[: services_idx + 2])


def _venv_ready(service_root: Path) -> bool:
    """Return True if the service has a synced virtualenv.

    Parameters
    ----------
    service_root : Path
        The service directory to check.

    Returns
    -------
    bool
        True when services/<name>/.venv exists.
    """
    return (service_root / ".venv").exists()


def _print_venv_missing_help(service_root: Path) -> None:
    """Print a clear remediation message when a service venv is missing.

    Parameters
    ----------
    service_root : Path
        The service directory whose venv is missing.
    """
    print(f"[error] Virtualenv not found for service: {service_root}")
    print("        The service venv is required to run lint/type checks.")
    print("        Fix it with one of:")
    print("          make init                                          # syncs all services")
    print(f"          cd {service_root} && uv sync --group dev          # this service only")


def _build_command(tool: str, service_root: Path) -> list[str] | None:
    """Build the uv run command for the given tool and service root.

    Parameters
    ----------
    tool : str
        One of "mypy" or "pylint".
    service_root : Path
        The service directory to run the tool from.

    Returns
    -------
    list[str] | None
        The command to run, or None if the tool name is unrecognised.
    """
    base = ["uv", "run", "--directory", str(service_root)]
    if tool == "mypy":
        return [*base, "mypy", "src/"]
    if tool == "pylint":
        return [*base, "pylint", "-j", "0", "--fail-under=10", "src/", "tests/"]
    return None


if __name__ == "__main__":
    sys.exit(main())
