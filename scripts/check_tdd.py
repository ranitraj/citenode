"""Pre-commit hook: verify every new src/ module has a matching test file."""

import sys
from pathlib import Path


def main() -> int:
    """Check that each staged src/ Python file has a corresponding test file.

    Reads file paths from sys.argv (supplied by pre-commit) and checks that
    for every module under src/ there is a matching tests/test_<module>.py.

    Returns
    -------
    int
        0 if all src/ files have matching test files, 1 otherwise.
    """
    files = [Path(f) for f in sys.argv[1:]]
    missing: list[tuple[Path, Path]] = []

    # Files that hold only data (constants, config) don't need test files.
    _no_test_required = {"constants.py", "config.py"}

    for f in files:
        if "src" not in f.parts or f.name == "__init__.py" or f.name in _no_test_required:
            continue
        src_idx = list(f.parts).index("src")
        service_root = Path(*f.parts[:src_idx])
        test_file = service_root / "tests" / f"test_{f.stem}.py"
        if not test_file.exists():
            missing.append((f, test_file))

    if missing:
        print("TDD enforcement: missing test file(s):")
        for src_f, test_f in missing:
            print(f"  {src_f}  →  {test_f}  (not found)")
        print("\nWrite the test first (RED), then commit the implementation.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
