from unittest.mock import MagicMock, patch

import pytest

from llm_classifier import classify_terms


def make_mock_response(classifications: list[dict]):
    response = MagicMock()
    response.output_parsed.classifications = [
        MagicMock(model_dump=lambda c=classification: c)
        for classification in classifications
    ]
    return response


@pytest.fixture(autouse=True)
def set_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


# --- empty input ---

def test_classify_terms_empty_returns_empty():
    result = classify_terms([])
    assert result == []


def test_classify_terms_empty_makes_no_api_call():
    with patch("llm_classifier.OpenAI") as mock_cls:
        classify_terms([])
        mock_cls.assert_not_called()


# --- happy path ---

def test_classify_terms_returns_classifications(monkeypatch):
    expected = [
        {"term": "Nvidia earnings", "ticker": "NVDA", "reason": "Nvidia is NVDA"},
        {"term": "weather forecast", "ticker": None, "reason": "Not finance-related"},
    ]
    with patch("llm_classifier.OpenAI") as mock_cls:
        mock_cls.return_value.responses.parse.return_value = make_mock_response(expected)
        result = classify_terms(["Nvidia earnings", "weather forecast"])
    assert result == expected


def test_classify_terms_single_batched_call(monkeypatch):
    with patch("llm_classifier.OpenAI") as mock_cls:
        mock_instance = mock_cls.return_value
        mock_instance.responses.parse.return_value = make_mock_response([])
        classify_terms(["term A", "term B", "term C"])
        assert mock_instance.responses.parse.call_count == 1


def test_classify_terms_uses_gpt_model():
    with patch("llm_classifier.OpenAI") as mock_cls:
        mock_instance = mock_cls.return_value
        mock_instance.responses.parse.return_value = make_mock_response([])
        classify_terms(["some term"])
        call_kwargs = mock_instance.responses.parse.call_args[1]
        assert call_kwargs["model"].startswith("gpt-")


def test_classify_terms_uses_structured_output_model():
    with patch("llm_classifier.OpenAI") as mock_cls:
        mock_instance = mock_cls.return_value
        mock_instance.responses.parse.return_value = make_mock_response([])
        classify_terms(["some term"])
        call_kwargs = mock_instance.responses.parse.call_args[1]
        assert call_kwargs["text_format"].__name__ == "ClassificationResponse"


def test_classify_terms_includes_all_terms_in_prompt():
    terms = ["Apple earnings", "Tesla recall", "NFL draft"]
    with patch("llm_classifier.OpenAI") as mock_cls:
        mock_instance = mock_cls.return_value
        mock_instance.responses.parse.return_value = make_mock_response([])
        classify_terms(terms)
        call_kwargs = mock_instance.responses.parse.call_args[1]
        user_content = call_kwargs["input"][1]["content"]
        for term in terms:
            assert term in user_content


# --- edge cases ---

def test_classify_terms_reads_api_key_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "my-secret-key")
    with patch("llm_classifier.OpenAI") as mock_cls:
        mock_cls.return_value.responses.parse.return_value = make_mock_response([])
        classify_terms(["term"])
        mock_cls.assert_called_once_with(api_key="my-secret-key")


def test_classify_terms_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(KeyError):
        classify_terms(["some term"])
