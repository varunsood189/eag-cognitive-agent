"""Decision artifact excerpt stays within context budget."""

from decision import MAX_ATTACHED_CHARS, _excerpt_artifact


def test_excerpt_caps_large_page() -> None:
    text = "Claude Shannon was born April 30 1916. " + ("filler " * 20_000)
    text += " He died February 24 2001. Information theory contributions here."
    out = _excerpt_artifact(text)
    assert len(out) <= MAX_ATTACHED_CHARS + 200
    assert "1916" in out
    assert "2001" in out
