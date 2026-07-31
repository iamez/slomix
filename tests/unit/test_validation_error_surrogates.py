"""A lone surrogate in a request body must yield 422, not 500.

`{"message": "\\ud800"}` is valid JSON, and a browser's `JSON.stringify()`
emits exactly that for a JS string holding an unpaired surrogate. Pydantic v2
rejects it (`string_unicode`), and FastAPI's stock validation handler echoes
the offending value back in `detail` — at which point `JSONResponse.render()`
calls `.encode("utf-8")`, which cannot encode a surrogate. The 422 handler
itself then raises UnicodeEncodeError and the request 500s.

That makes any public endpoint accepting a string body trivially forceable
into a 500 (Codex review on #578 reported the symptom at /api/client-error).
The fix is app-wide because the defect is in rendering attacker input, not in
any single route.
"""

import httpx
import pytest
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from website.backend.security_utils import strip_surrogates


class _Payload(BaseModel):
    message: str = Field(..., max_length=2000)


def _app() -> FastAPI:
    app = FastAPI()

    @app.exception_handler(RequestValidationError)
    async def _handler(request, exc):  # noqa: ANN001
        return JSONResponse(
            status_code=422,
            content={"detail": strip_surrogates(jsonable_encoder(exc.errors()))},
        )

    @app.post("/echo", status_code=204)
    async def _echo(payload: _Payload):  # noqa: ANN001
        return None

    return app


@pytest.mark.asyncio
async def test_lone_surrogate_yields_422_not_500():
    transport = httpx.ASGITransport(app=_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/echo",
            content='{"message": "\\ud800 boom"}',
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 422, (
        "without the handler this is 500: the stock 422 renderer cannot "
        "encode the surrogate it echoes back"
    )
    response.content.decode("utf-8")


@pytest.mark.asyncio
async def test_ordinary_validation_errors_still_report_the_value():
    """The guard must not blunt normal 422s."""
    transport = httpx.ASGITransport(app=_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/echo", json={"message": 12345})

    assert response.status_code == 422
    assert "detail" in response.json()


def test_strip_surrogates_preserves_ordinary_unicode():
    assert strip_surrogates("\U0001f600 ok") == "\U0001f600 ok"
    assert strip_surrogates({"a": ["\U0001f600"]}) == {"a": ["\U0001f600"]}
    assert "\ud800" not in strip_surrogates("\ud800 x")
