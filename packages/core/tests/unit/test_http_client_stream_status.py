import httpx

from llm_spec.client.http_client import HTTPClient


def test_http_client_stream_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://example.test/v1/stream")
        return httpx.Response(
            502,
            headers={"content-type": "application/json"},
            json={
                "error": {
                    "message": "Upstream authentication failed.",
                    "type": "r9s_upstream_error",
                    "code": "upstream_auth_failed",
                }
            },
        )

    transport = httpx.MockTransport(handler)
    client = HTTPClient()
    client._sync_client = httpx.Client(transport=transport, timeout=1.0)

    try:
        for _ in client.stream(
            method="POST",
            url="https://example.test/v1/stream",
            headers={},
            json={"stream": True},
            timeout=1.0,
        ):
            raise AssertionError("should not yield bytes on HTTP error")
    except httpx.HTTPStatusError as e:
        assert e.response.status_code == 502
        assert "upstream_auth_failed" in e.response.text
        assert client.stream_status_code == 502


def test_http_client_stream_records_success_status_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, content=b"hello")

    transport = httpx.MockTransport(handler)
    client = HTTPClient()
    client._sync_client = httpx.Client(transport=transport, timeout=1.0)

    chunks = list(
        client.stream(
            method="POST",
            url="https://example.test/v1/stream",
            headers={},
            json={"stream": True},
            timeout=1.0,
        )
    )
    assert chunks == [b"hello"]
    assert client.stream_status_code == 201
