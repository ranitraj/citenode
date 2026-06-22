"""Tests for the Jinja2 prompt loader."""

import pytest
from jinja2 import UndefinedError
from verdict.prompting import render_prompt


def test_render_prompt_interpolates_context_into_the_template():
    rendered = render_prompt("stance_user.j2", claim="CLAIM_X", title="TITLE_Y", abstract="ABSTRACT_Z")

    assert "CLAIM_X" in rendered
    assert "TITLE_Y" in rendered
    assert "ABSTRACT_Z" in rendered


def test_render_prompt_raises_on_a_missing_variable():
    with pytest.raises(UndefinedError):
        render_prompt("stance_user.j2", claim="CLAIM_X")
