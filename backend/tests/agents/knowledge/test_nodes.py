from app.agents.knowledge.nodes import _plain_question


def test_plain_question_removes_like_im_five():
    assert _plain_question("Explain RSI like I'm five") == "Explain RSI"


def test_plain_question_removes_spanish_style_request():
    assert _plain_question("Explica el RSI como si tuviera 5 años") == "Explica el RSI"


def test_plain_question_keeps_normal_question():
    assert (
        _plain_question("What does the Sharpe ratio measure?")
        == "What does the Sharpe ratio measure?"
    )


def test_plain_question_falls_back_to_original_if_only_style_request():
    assert _plain_question("like I'm five") == "like I'm five"
