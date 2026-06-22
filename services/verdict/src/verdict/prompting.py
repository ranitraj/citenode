"""Render Jinja2 prompt templates kept separately under the prompts directory."""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_ENVIRONMENT = Environment(
    loader=FileSystemLoader(_PROMPTS_DIR),
    undefined=StrictUndefined,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_prompt(name: str, /, **context: Any) -> str:
    """Render a prompt template by file name with the given context.

    Parameters
    ----------
    name : str
        The template file name under the prompts directory, e.g. ``stance_user.j2``.
    **context : Any
        Template variables to interpolate; a missing variable raises rather than
        rendering empty.

    Returns
    -------
    str
        The rendered prompt text.
    """
    return _ENVIRONMENT.get_template(name).render(**context)
