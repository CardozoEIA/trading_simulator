import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents.explain.verify import NO_DATA, NOTHING_VERIFIED, extract_trace, split_statements, verify_answer

DECISION = "Action: BUY | Reason: Combined score=0.412 crossed BUY threshold [RSI=28.41 indicates oversold conditions] | Executed: True"
INDICATORS = "SMA short: 4510.25, SMA long: 4488.9, RSI: 28.41, Bollinger bands: [4401.2, 4602.7], Momentum: 0.0523"
TRACE = [
    {"tool": "get_decision", "arguments": {"date": "2023-10-05"}, "result": DECISION},
    {"tool": "get_indicators", "arguments": {"date": "2023-10-05"}, "result": INDICATORS},
]
REQUEST = "Explain the trading decision made on 2023-10-05."


def verify(answer, trace=TRACE, reference=""):
    return verify_answer(answer, trace, REQUEST, reference)


# ---- the fabricated value is caught and removed ------------------------------------------------------------

def test_a_fabricated_number_is_removed_and_the_student_is_told():
    answer = (
        "On 2023-10-05 the strategy bought because the RSI was 28.41, which means oversold. "
        "The RSI had dropped from 61.7 the day before."
    )
    result = verify(answer)
    assert "28.41" in result.text
    assert "61.7" not in result.text
    assert result.verified is False
    assert result.removed == [{"statement": "The RSI had dropped from 61.7 the day before.", "problems": ["61.7"]}]
    assert "1 statement removed" in result.text


def test_a_fabricated_date_is_removed():
    result = verify("The RSI was 28.41. A similar signal happened on 2021-03-17.")
    assert "2021-03-17" not in result.text and "28.41" in result.text
    assert result.removed[0]["problems"] == ["2021-03-17"]


def test_a_written_out_fabricated_date_is_removed_too():
    result = verify("The RSI was 28.41. This repeated on March 17, 2021.")
    assert "March 17" not in result.text


def test_an_answer_whose_values_all_come_from_the_tools_is_kept_untouched():
    answer = ("The strategy bought on 2023-10-05. The RSI was 28.41 and the short SMA 4510.25 was above "
              "the long SMA 4488.9. The decision was executed.")
    result = verify(answer)
    assert result.verified is True and result.removed == []
    assert result.text == answer


# ---- what legitimately counts as backed -----------------------------------------------------------------

@pytest.mark.parametrize("sentence", [
    "Momentum was 5.23%, a clear rise.",            # the tool says 0.0523
    "The RSI of 28.41 is below the oversold limit of 30.",   # 30 is a setting of the strategy
    "The combined score of 0.412 crossed the 0.1 limit.",
])
def test_percentages_and_strategy_settings_are_accepted(sentence):
    reference = "Strategy RSI (RSI) parameters: period 14, oversold 30, overbought 70\nScore limits: BUY above 0.1, SELL below -0.1"
    assert verify(sentence, reference=reference).verified is True


def test_a_setting_is_not_accepted_without_the_strategy_definition():
    assert verify("The RSI of 28.41 is below the oversold limit of 30.").verified is False


def test_list_numbering_is_not_a_claim():
    answer = "1. The RSI was 28.41.\n2. The short SMA was 4510.25.\n- The decision was executed."
    assert verify(answer).verified is True


def test_rounding_is_tolerated():
    assert verify("The RSI was about 28.4 and the SMA 4510.3.").verified is True


# ---- never a promise -----------------------------------------------------------------------------------

def test_sentences_that_guarantee_results_are_removed():
    result = verify("The RSI was 28.41. This strategy will always make money.")
    assert "always" not in result.text
    assert result.removed[0]["problems"] == ["promises a future result"]


# ---- nothing left / no data ----------------------------------------------------------------------------

def test_when_everything_is_fabricated_the_data_is_shown_instead():
    result = verify("The RSI was 12.34 and the price 9999.")
    assert result.text.startswith(NOTHING_VERIFIED)
    assert DECISION in result.text and INDICATORS in result.text
    assert "12.34" not in result.text


def test_an_answer_with_numbers_but_no_tool_calls_is_not_trusted():
    result = verify("The RSI was 28.41.", trace=[])
    assert result.verified is False and result.text == NO_DATA
    assert result.tools_called == 0


def test_a_plain_statement_that_no_data_exists_is_kept():
    result = verify("No information is available for that date.", trace=[
        {"tool": "get_decision", "arguments": {}, "result": "No decision found for 2023-10-06."}])
    assert result.verified is True


def test_the_result_serialises_for_the_api():
    data = verify("The RSI was 28.41. It fell from 61.7.").as_dict()
    assert data["verified"] is False and data["tools_called"] == 2
    assert data["removed"][0]["problems"] == ["61.7"]


def test_statements_are_split_by_line_and_sentence():
    assert split_statements("One. Two!\n\n- Three 3.5 units. Four") == ["One.", "Two!", "- Three 3.5 units.", "Four"]


# ---- the trace ----------------------------------------------------------------------------------------

def test_the_trace_pairs_every_call_with_its_result_and_ignores_earlier_turns():
    messages = [
        HumanMessage(content="old question"),
        AIMessage(content="", tool_calls=[{"name": "get_price", "args": {"date": "2023-01-01"}, "id": "old"}]),
        ToolMessage(content="old price", tool_call_id="old", name="get_price"),
        HumanMessage(content=REQUEST),
        AIMessage(content="", tool_calls=[
            {"name": "get_decision", "args": {"date": "2023-10-05"}, "id": "a"},
            {"name": "get_indicators", "args": {"date": "2023-10-05"}, "id": "b"}]),
        ToolMessage(content=INDICATORS, tool_call_id="b", name="get_indicators"),
        ToolMessage(content=DECISION, tool_call_id="a", name="get_decision"),
        AIMessage(content="final"),
    ]
    assert extract_trace(messages) == TRACE
