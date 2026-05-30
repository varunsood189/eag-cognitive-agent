"""final_answer_from must not treat artifact previews as answers."""

from history_utils import final_answer_from, is_substantive_answer


def test_artifact_preview_not_substantive() -> None:
    assert not is_substantive_answer("[artifact art:abc, 100 bytes] preview: Skip to main")


def test_final_answer_skips_bad_last_answer() -> None:
    history = [
        {"kind": "answer", "text": "ReAct uses interleaved thoughts; CoT uses chain prompts."},
        {"kind": "answer", "text": "[artifact art:x, 50 bytes] preview: html junk"},
    ]
    assert "ReAct uses interleaved" in final_answer_from(history)
