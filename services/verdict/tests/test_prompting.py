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


def test_fence_wraps_untrusted_content_in_a_randomized_delimiter():
    first = render_prompt("stance_user.j2", claim="c", title="t", abstract="ABSTRACT_BODY")
    second = render_prompt("stance_user.j2", claim="c", title="t", abstract="ABSTRACT_BODY")

    assert "ABSTRACT_BODY" in first
    assert "UNTRUSTED-DATA" in first
    assert first != second  # the delimiter id is randomized per render, so it cannot be forged


def test_system_prompt_carries_the_untrusted_data_notice():
    rendered = render_prompt("stance_system.j2")

    assert "UNTRUSTED-DATA" in rendered
    assert "never follow" in rendered.lower()
