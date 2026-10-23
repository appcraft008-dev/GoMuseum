"""失败类别(spec §3.1 error_kind):transient = 超时、429、5xx、连接错误,其余 internal。"""

import anthropic
import httpx
import openai
import pytest
import requests

from app.services.enrichment import lazy

_REQ = httpx.Request("POST", "https://api.example/v1/chat")


def _status(cls, code):
    return cls("x", response=httpx.Response(code, request=_REQ), body=None)


def _wrapped(inner):
    try:
        raise RuntimeError("pipeline") from inner
    except RuntimeError as e:
        return e


@pytest.mark.parametrize(
    "exc,kind",
    [
        (TimeoutError(), "transient"),
        (ConnectionError(), "transient"),
        (openai.APITimeoutError(request=_REQ), "transient"),
        (openai.APIConnectionError(request=_REQ), "transient"),
        (anthropic.APITimeoutError(request=_REQ), "transient"),
        (_status(openai.RateLimitError, 429), "transient"),
        (_status(openai.InternalServerError, 503), "transient"),
        (_status(openai.BadRequestError, 400), "internal"),
        (requests.exceptions.ReadTimeout(), "transient"),
        (ValueError("bad json"), "internal"),
        (_wrapped(TimeoutError()), "transient"),
    ],
)
def test_error_kind(exc, kind):
    assert lazy._error_kind(exc) == kind
