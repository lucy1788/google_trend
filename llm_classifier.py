import os
from typing import Optional

from openai import OpenAI
from pydantic import BaseModel

_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.2")

_SYSTEM = (
    "You are a financial analyst assistant. "
    "For each trending search term, determine if it is likely related to a specific "
    "US-listed stock (S&P 500 preferred). If so, return the best matching ticker symbol. "
    "If the term is not finance-related or cannot be tied to a specific stock, return null for ticker. "
    "Be conservative: only return a ticker when you are confident."
)


class Classification(BaseModel):
    term: str
    ticker: Optional[str]
    reason: str


class ClassificationResponse(BaseModel):
    classifications: list[Classification]


def classify_terms(terms: list[str]) -> list[dict]:
    """
    Classify unmatched trending terms via an OpenAI GPT model.
    Returns [{term, ticker, reason}]; ticker is None if not finance-related.
    Makes a single batched API call for all terms.
    """
    if not terms:
        return []

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    terms_list = "\n".join(f"- {t}" for t in terms)

    response = client.responses.parse(
        model=_MODEL,
        input=[
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": f"Classify these trending search terms:\n{terms_list}",
            }
        ],
        text_format=ClassificationResponse,
    )

    parsed = response.output_parsed
    return [classification.model_dump() for classification in parsed.classifications]
