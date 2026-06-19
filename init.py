"""One-shot project initialiser — run once after cloning, then deletes itself."""

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
PYTHON_VERSIONS = ["3.12", "3.11", "3.10"]
_EXCLUDE = {".git", ".venv", "__pycache__"}


def main() -> None:
    """Run the interactive project initialisation wizard.

    Collects answers across five categories (identity, service, quality,
    workflow, CI/CD), applies them to all template files, creates the first
    service from _service-template/, wires up git, then deletes itself.

    Raises
    ------
    SystemExit
        If the user aborts at the confirmation prompt.
    """
    print("\nAgentic Python Project Initialiser")
    print("=" * 38)
    print("Defaults shown in [brackets] — press Enter to accept.\n")

    # ── Project identity ──────────────────────────────────────────────────
    print("Project identity")
    project_name = _ask("Project name (kebab-case)", "my-project")
    description = _ask("One-line description", "A Python project")
    print(f"  Available Python versions: {', '.join(PYTHON_VERSIONS)}")
    python_version = _ask("Python version", "3.12")
    while python_version not in PYTHON_VERSIONS:
        print(f"  Please choose from: {', '.join(PYTHON_VERSIONS)}")
        python_version = _ask("Python version", "3.12")

    # ── First service ─────────────────────────────────────────────────────
    print("\nFirst service")
    service_name = _ask("Service name (kebab-case)", "api")
    service_module = service_name.replace("-", "_")

    # ── Code quality ──────────────────────────────────────────────────────
    print("\nCode quality  (press Enter to accept defaults)")
    strict_mypy = _ask_bool("Strict mypy?", default=True)
    pylint_score = _ask("Min pylint score (9.5 = trying hard, 10 = strict)", "9.5")
    line_length = _ask("Line length", "119")
    max_args = _ask("Max function args", "5")
    docstring_style = _ask("Docstring style (numpy/google/skip)", "numpy").lower()
    while docstring_style not in ("numpy", "google", "skip"):
        print("  Please choose: numpy, google, or skip")
        docstring_style = _ask("Docstring style (numpy/google/skip)", "numpy").lower()

    # ── Workflow ──────────────────────────────────────────────────────────
    print("\nWorkflow")
    enforce_tdd = _ask_bool("Enforce TDD? (pre-commit blocks commit if test file missing)", default=True)
    use_ddd = _ask_bool("Use DDD design docs + solution docs?", default=True)
    protect_main = _ask_bool("Protect main branch? (blocks direct commits to main)", default=True)

    # ── CI/CD ─────────────────────────────────────────────────────────────
    print("\nCI/CD")
    use_github_actions = _ask_bool("Add GitHub Actions?", default=True)

    # ── Confirm ───────────────────────────────────────────────────────────
    print("\n── Summary ──────────────────────────────────────────────")
    print(f"  project      : {project_name}")
    print(f"  description  : {description}")
    print(f"  python       : {python_version}")
    print(f"  service      : {service_name}  (module: {service_module})")
    print(f"  strict mypy  : {strict_mypy}")
    print(f"  pylint score : {pylint_score}   line length: {line_length}   max args: {max_args}")
    print(f"  docstrings   : {docstring_style}")
    print(f"  enforce TDD  : {enforce_tdd}")
    print(f"  DDD docs     : {use_ddd}")
    print(f"  protect main : {protect_main}")
    print(f"  GitHub CI    : {use_github_actions}")

    if not _ask_bool("\nLooks good? Proceed?", default=True):
        print("Aborted. Re-run `python init.py` to start over.")
        sys.exit(0)

    # ── Apply ─────────────────────────────────────────────────────────────
    print("\nInitialising...\n")

    _replace_in_tree(ROOT, {
        "{{project-name}}": project_name,
        "{{project-description}}": description,
        "{{python-version}}": python_version,
        "{{service-name}}": service_name,
        "{{service-module}}": service_module,
    })
    _set_python_version(ROOT, python_version)
    _apply_quality_settings(ROOT, python_version, pylint_score, line_length, max_args, strict_mypy)
    _create_service(ROOT, service_name, service_module)

    if not enforce_tdd:
        _remove_tdd_hook(ROOT)
    if not use_ddd:
        _remove_ddd(ROOT)
    if not use_github_actions:
        _remove_ci(ROOT)
    if not protect_main:
        _remove_branch_protection(ROOT)
    if docstring_style == "google":
        _set_docstring_convention(ROOT, "google")
    elif docstring_style == "skip":
        _remove_docstring_enforcement(ROOT)
    _clean_template_meta(ROOT)

    _reset_readme(ROOT, project_name, description, service_name)
    _git_init_commit(ROOT, project_name)
    Path(__file__).unlink()

    print(f"\n  {project_name} is ready.")
    print("\n  Next steps:")
    print(f"    cd services/{service_name} && uv sync --group dev")
    print("    make precommit-install")
    print("    direnv allow .")


# ── Private helpers ────────────────────────────────────────────────────────


def _ask(prompt: str, default: str) -> str:
    """Prompt the user for input, returning the default if they press Enter.

    Parameters
    ----------
    prompt : str
        The question to display (without brackets or newline).
    default : str
        Value returned when the user submits an empty response.

    Returns
    -------
    str
        The user's trimmed input, or `default` if input was empty.
    """
    response = input(f"  {prompt} [{default}]: ").strip()
    return response or default


def _ask_bool(prompt: str, default: bool = True) -> bool:
    """Prompt the user for a yes/no answer.

    Parameters
    ----------
    prompt : str
        The question to display.
    default : bool, optional
        Value returned when the user presses Enter, by default True.

    Returns
    -------
    bool
        True if the user answered yes (or accepted a True default),
        False otherwise.
    """
    hint = "Y/n" if default else "y/N"
    response = input(f"  {prompt} [{hint}]: ").strip().lower()
    if not response:
        return default
    return response in ("y", "yes", "1")


def _replace_in_file(path: Path, replacements: dict[str, str]) -> None:
    """Replace all placeholder strings inside a single file in-place.

    Parameters
    ----------
    path : Path
        File to update.
    replacements : dict[str, str]
        Mapping of ``{{placeholder}}`` strings to their resolved values.
    """
    try:
        text = path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")
    except (UnicodeDecodeError, PermissionError):
        pass


def _replace_in_tree(root: Path, replacements: dict[str, str]) -> None:
    """Walk the project tree and apply placeholder replacements to every file.

    Parameters
    ----------
    root : Path
        Root directory to walk.
    replacements : dict[str, str]
        Mapping of ``{{placeholder}}`` strings to their resolved values.
    """
    for path in root.rglob("*"):
        if any(ex in path.parts for ex in _EXCLUDE):
            continue
        if path.is_file():
            _replace_in_file(path, replacements)


def _set_python_version(root: Path, version: str) -> None:
    """Overwrite every .python-version file in the tree with the chosen version.

    Parameters
    ----------
    root : Path
        Root directory to search.
    version : str
        Python version string, e.g. ``"3.12"``.
    """
    for pv in root.rglob(".python-version"):
        if ".venv" not in pv.parts:
            pv.write_text(version + "\n", encoding="utf-8")


def _apply_quality_settings(
    root: Path,
    python_version: str,
    pylint_score: str,
    line_length: str,
    max_args: str,
    strict_mypy: bool,
) -> None:
    """Patch the root pyproject.toml with the user's chosen quality thresholds.

    Parameters
    ----------
    root : Path
        Project root containing pyproject.toml.
    python_version : str
        Python version string, e.g. ``"3.12"``.
    pylint_score : str
        Minimum pylint score, e.g. ``"10"``.
    line_length : str
        Maximum line length for ruff, e.g. ``"119"``.
    max_args : str
        Maximum number of function arguments for pylint, e.g. ``"5"``.
    strict_mypy : bool
        Whether to enable mypy strict mode.
    """
    ptp = root / "pyproject.toml"
    if not ptp.exists():
        return
    text = ptp.read_text(encoding="utf-8")
    py_compact = "py" + python_version.replace(".", "")
    text = re.sub(r'target-version\s*=\s*"py\d+"', f'target-version = "{py_compact}"', text)
    text = re.sub(r'python_version\s*=\s*"[\d.]+"', f'python_version = "{python_version}"', text)
    text = re.sub(r"fail-under\s*=\s*[\d.]+", f"fail-under = {pylint_score}", text)
    text = re.sub(r"line-length\s*=\s*\d+", f"line-length = {line_length}", text)
    text = re.sub(r"max-args\s*=\s*\d+", f"max-args = {max_args}", text)
    strict_val = "true" if strict_mypy else "false"
    text = re.sub(r"strict\s*=\s*(true|false)", f"strict = {strict_val}", text)
    ptp.write_text(text, encoding="utf-8")


def _create_service(root: Path, service_name: str, service_module: str) -> None:
    """Create the first service directory from _service-template/.

    Copies _service-template/ to services/<service_name>/, removes the
    template directory, and renames the placeholder package directory to
    the real module name.

    Parameters
    ----------
    root : Path
        Project root.
    service_name : str
        Kebab-case service name, e.g. ``"wiki-agent"``.
    service_module : str
        Snake_case Python package name, e.g. ``"wiki_agent"``.
    """
    template = root / "_service-template"
    service_dir = root / "services" / service_name
    service_dir.parent.mkdir(exist_ok=True)
    shutil.copytree(template, service_dir)
    shutil.rmtree(template)
    placeholder_pkg = service_dir / "src" / "service_module"
    if placeholder_pkg.exists():
        placeholder_pkg.rename(service_dir / "src" / service_module)


def _strip_claude_md_section(root: Path, heading: str) -> None:
    """Strip a section (and its trailing separator) from CLAUDE.md.

    Matches from the exact heading line through to just before the next
    ``## `` heading (or end of file). Collapses runs of blank lines and
    adjacent ``---`` separators left behind by the removal.

    Parameters
    ----------
    root : Path
        Project root.
    heading : str
        Section heading line, e.g. ``"## Document Driven Design (DDD)"``.
    """
    claude_md = root / "CLAUDE.md"
    if not claude_md.exists():
        return
    text = claude_md.read_text(encoding="utf-8")
    pattern = re.escape(heading) + r".*?(?=\n## |\Z)"
    text = re.sub(pattern, "", text, count=1, flags=re.DOTALL)
    text = re.sub(r"\n---\n\s*\n---\n", "\n---\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    claude_md.write_text(text.rstrip() + "\n", encoding="utf-8")


def _remove_docs_sync(root: Path) -> None:
    """Remove the docs-sync agent and strip references to it from /review and the agents README.

    Called from :func:`_remove_ddd` because docs-sync only inspects the DDD
    directories that have just been deleted.

    Parameters
    ----------
    root : Path
        Project root.
    """
    docs_sync = root / ".claude" / "agents" / "docs-sync.md"
    if docs_sync.exists():
        docs_sync.unlink()

    review_cmd = root / ".claude" / "commands" / "review.md"
    if review_cmd.exists():
        text = review_cmd.read_text(encoding="utf-8")
        # The whole orchestrator-level preflight existed only to gate docs-sync
        text = re.sub(
            r"## Preflight — decide which agents to launch.*?(?=\n## )",
            "",
            text,
            flags=re.DOTALL,
        )
        # Table row + verdict bullet
        text = re.sub(r"\| `docs-sync` \|.*?\n", "", text)
        text = re.sub(r"- Docs-sync:.*?\n", "", text)
        # Frontmatter description references docs-sync by name + counts agents
        text = text.replace(
            "Run three parallel read-only review agents (DRY, simplicity, docs-sync)",
            "Run two parallel read-only review agents (DRY, simplicity)",
        )
        text = text.replace("Three specialist", "Two specialist")
        # Collapse blank-line runs left by the preflight removal
        text = re.sub(r"\n{3,}", "\n\n", text)
        review_cmd.write_text(text, encoding="utf-8")

    agents_readme = root / ".claude" / "agents" / "README.md"
    if agents_readme.exists():
        text = agents_readme.read_text(encoding="utf-8")
        text = re.sub(r"\| \[docs-sync\].*?\n", "", text)
        text = text.replace("three Haiku invocations", "two Haiku invocations")
        agents_readme.write_text(text, encoding="utf-8")

    # CLAUDE.md's "Code Review" section names docs-sync as one of three agents
    claude_md = root / "CLAUDE.md"
    if claude_md.exists():
        text = claude_md.read_text(encoding="utf-8")
        text = text.replace(
            "three parallel read-only agents (DRY, simplicity, docs-sync)",
            "two parallel read-only agents (DRY, simplicity)",
        )
        claude_md.write_text(text, encoding="utf-8")

    # README.md's AI guardrails Layer 3 lists docs-sync; "Useful commands" mentions it too
    readme = root / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        text = re.sub(r"- \*\*docs-sync\*\* — .*?\n", "", text)
        text = text.replace("Three agents run in parallel", "Two agents run in parallel")
        text = text.replace(
            "spawn DRY + simplicity + docs-sync agents",
            "spawn DRY + simplicity agents",
        )
        readme.write_text(text, encoding="utf-8")


def _remove_tdd_hook(root: Path) -> None:
    """Remove the enforce-tdd hook, its script, the TDD CLAUDE.md section, and ``.claude/TDD.md``.

    Parameters
    ----------
    root : Path
        Project root.
    """
    pre_commit = root / ".pre-commit-config.yaml"
    if pre_commit.exists():
        text = pre_commit.read_text(encoding="utf-8")
        text = re.sub(
            r"\n\s*- id: enforce-tdd.*?pass_filenames: true",
            "",
            text,
            flags=re.DOTALL,
        )
        pre_commit.write_text(text, encoding="utf-8")
    tdd_script = root / "scripts" / "check_tdd.py"
    if tdd_script.exists():
        tdd_script.unlink()
    _strip_claude_md_section(root, "## Development Workflow — TDD")
    tdd_md = root / ".claude" / "TDD.md"
    if tdd_md.exists():
        tdd_md.unlink()


def _remove_ddd(root: Path) -> None:
    """Remove all DDD artifacts: directories, docs-sync agent, CLAUDE.md sections, detail file.

    Specifically:
    - Deletes ``.claude/{designs,solutions,decisions}/``.
    - Calls :func:`_remove_docs_sync` because that agent only inspects the deleted dirs.
    - Strips the DDD / Solution Docs / ADR sections from CLAUDE.md.
    - Deletes ``.claude/DDD.md`` (referenced from the now-removed CLAUDE.md section).

    Parameters
    ----------
    root : Path
        Project root.
    """
    for d in [
        root / ".claude" / "designs",
        root / ".claude" / "solutions",
        root / ".claude" / "decisions",
    ]:
        if d.exists():
            shutil.rmtree(d)
    _remove_docs_sync(root)
    for heading in [
        "## Document Driven Design (DDD)",
        "## Solution Docs",
        "## Architecture Decision Records",
    ]:
        _strip_claude_md_section(root, heading)
    ddd_md = root / ".claude" / "DDD.md"
    if ddd_md.exists():
        ddd_md.unlink()


def _remove_ci(root: Path) -> None:
    """Delete the .github directory and all GitHub Actions workflows.

    Parameters
    ----------
    root : Path
        Project root.
    """
    gh = root / ".github"
    if gh.exists():
        shutil.rmtree(gh)


def _clean_template_meta(root: Path) -> None:
    """Remove GitHub issue and PR templates that reference template-specific surfaces.

    The shipped templates ask about ``init.py`` flow, CLAUDE.md conventions, and
    other template-meta scaffolding that an adopter's downstream project does
    not have. Always runs, regardless of opt-out choices.

    Parameters
    ----------
    root : Path
        Project root.
    """
    issue_dir = root / ".github" / "ISSUE_TEMPLATE"
    if issue_dir.exists():
        shutil.rmtree(issue_dir)
    pr_template = root / ".github" / "PULL_REQUEST_TEMPLATE.md"
    if pr_template.exists():
        pr_template.unlink()


def _remove_branch_protection(root: Path) -> None:
    """Strip the no-commit-to-branch hook from .pre-commit-config.yaml.

    Parameters
    ----------
    root : Path
        Project root.
    """
    pre_commit = root / ".pre-commit-config.yaml"
    if not pre_commit.exists():
        return
    lines = pre_commit.read_text(encoding="utf-8").splitlines()
    filtered = [ln for ln in lines if "no-commit-to-branch" not in ln and "--branch=main" not in ln]
    pre_commit.write_text("\n".join(filtered) + "\n", encoding="utf-8")


_NUMPY_DOCSTRING_BLOCK = '''### Function / method docstrings — NumPy style
Every public function and method must have a NumPy-style docstring with all applicable sections:

```python
def fetch_entry(title: str) -> WikiEntry:
    """Fetch a wiki entry by title.

    Parameters
    ----------
    title : str
        Exact title to retrieve.

    Returns
    -------
    WikiEntry
        The retrieved entry.

    Raises
    ------
    EntryNotFoundError
        If `title` does not exist.
    """
```

Rules:
- One-line summary, imperative mood ("Fetch", "Update", "Run").
- Include `Parameters` / `Returns` / `Raises` only when they apply (omit `Returns` for `None`-returners, etc.).
- Private helpers (`_prefixed`) follow the same rules as public functions.'''


_GOOGLE_DOCSTRING_BLOCK = '''### Function / method docstrings — Google style
Every public function and method must have a Google-style docstring with all applicable sections:

```python
def fetch_entry(title: str) -> WikiEntry:
    """Fetch a wiki entry by title.

    Args:
        title: Exact title to retrieve.

    Returns:
        The retrieved entry.

    Raises:
        EntryNotFoundError: If `title` does not exist.
    """
```

Rules:
- One-line summary, imperative mood ("Fetch", "Update", "Run").
- Include `Args` / `Returns` / `Raises` only when they apply (omit `Returns` for `None`-returners, etc.).
- Private helpers (`_prefixed`) follow the same rules as public functions.'''


def _set_docstring_convention(root: Path, convention: str) -> None:
    """Swap ruff's pydocstyle convention and the CLAUDE.md docstring example.

    Parameters
    ----------
    root : Path
        Project root.
    convention : str
        Target convention, currently only ``"google"`` is supported by the wizard
        (the default ``"numpy"`` is what the template ships with, so no swap is needed).
    """
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8")
        text = text.replace('convention = "numpy"', f'convention = "{convention}"')
        pyproject.write_text(text, encoding="utf-8")

    if convention == "google":
        claude_md = root / "CLAUDE.md"
        if claude_md.exists():
            text = claude_md.read_text(encoding="utf-8")
            text = text.replace(_NUMPY_DOCSTRING_BLOCK, _GOOGLE_DOCSTRING_BLOCK)
            claude_md.write_text(text, encoding="utf-8")


def _remove_docstring_enforcement(root: Path) -> None:
    """Disable ruff D rules and remove the docstring-style guidance from CLAUDE.md.

    Removes the ``D`` entry from ``select``, deletes the ``[tool.ruff.lint.pydocstyle]``
    and template-shipped ``[tool.ruff.lint.per-file-ignores]`` sections from
    ``pyproject.toml``, and strips the entire "Docstring & Comment Conventions"
    section from CLAUDE.md.

    Parameters
    ----------
    root : Path
        Project root.
    """
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8")
        # Drop "D" from the select list (it's always last in the template).
        text = re.sub(r',\s*"D"(?=\s*\])', "", text)
        # Drop the pydocstyle config block (single-line comment + section + value).
        text = re.sub(
            r"\n# Docstring style: .*?\n\[tool\.ruff\.lint\.pydocstyle\]\nconvention = \"[^\"]+\"\n",
            "",
            text,
        )
        # Drop the per-file-ignores block (D-specific, shipped by the template).
        text = re.sub(
            r"\n\[tool\.ruff\.lint\.per-file-ignores\]\n\"__init__\.py\".*?\n\"tests/\*\*\".*?\n",
            "",
            text,
        )
        text = re.sub(r"\n{3,}", "\n\n", text)
        pyproject.write_text(text, encoding="utf-8")

    _strip_claude_md_section(root, "## Docstring & Comment Conventions")


def _reset_readme(root: Path, project_name: str, description: str, service_name: str) -> None:
    """Overwrite README.md with a minimal project-specific file.

    The template's README describes the template itself and is not useful
    after initialisation. This replaces it with a project stub the user
    can extend.

    Parameters
    ----------
    root : Path
        Project root.
    project_name : str
        Kebab-case project name, used as the Markdown heading.
    description : str
        One-line project description.
    service_name : str
        Kebab-case service name, used in the setup steps.
    """
    content = (
        f"# {project_name}\n\n"
        f"{description}\n\n"
        "## Setup\n\n"
        "```bash\n"
        "make init\n"
        "direnv allow .\n"
        f"cd services/{service_name} && direnv allow .\n"
        "```\n"
    )
    (root / "README.md").write_text(content, encoding="utf-8")


def _git_init_commit(root: Path, project_name: str) -> None:
    """Initialise a git repo and create the first commit.

    Parameters
    ----------
    root : Path
        Project root to initialise.
    project_name : str
        Used in the commit message.

    Raises
    ------
    subprocess.CalledProcessError
        If any git command fails.
    """
    subprocess.run(["git", "init"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"chore: initialise {project_name} from agentic-python-template"],
        cwd=root,
        check=True,
    )


if __name__ == "__main__":
    main()
