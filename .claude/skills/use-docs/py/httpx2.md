# [httpx2][httpx2:docs]

[2.13.1][httpx2:release] · [changelog][httpx2:changelog] · [transports][httpx2:transports] · [event hooks][httpx2:event-hooks] · [timeouts][httpx2:timeouts]

## client construction

```py
import httpx2

# AsyncClient(*, auth=None, params=None, headers=None, cookies=None, verify=True,
#   http1=True, http2=False, proxy=None, mounts=None, timeout=Timeout(5.0),
#   follow_redirects=False, limits=Limits(100, 20), max_redirects=20,
#   event_hooks=None, base_url="", transport=None, trust_env=True) -> AsyncClient
# every parameter is keyword-only; Client takes the same set
client = httpx2.AsyncClient(
    base_url="https://api.example.com/v1",  # stored with a trailing slash
    headers={"Authorization": "Bearer …"},
    timeout=httpx2.Timeout(10.0, connect=2.0),  # default for read, write, pool
    limits=httpx2.Limits(max_connections=20, max_keepalive_connections=10, keepalive_expiry=30.0),
    follow_redirects=True,
)
# Timeout(timeout=UNSET, *, connect, read, write, pool); omit the default → set all four
strict = httpx2.Timeout(connect=2.0, read=30.0, write=5.0, pool=5.0)
```

## async lifecycle

```py
# one client per upstream, shared between tasks; a closed client cannot reopen
async with httpx2.AsyncClient(base_url="https://api.example.com") as client:
    first, second = await asyncio.gather(
        client.get("/items", params={"page": 1}),
        client.get("/items", params={"page": 2}),
    )

# manual lifetime; aclose() is idempotent and closes the transport and mounts
client = httpx2.AsyncClient()
try:
    ...
finally:
    await client.aclose()
```

## request, status, decode

```py
# Response.raise_for_status() -> Response; raises HTTPStatusError unless 2xx
# Response.json(**kwargs) -> Any; Response.content -> bytes
response = await client.get("/items", params={"q": "x", "limit": 50}, timeout=30.0)
data = response.raise_for_status().json()
if response.is_success:  # 2xx; response.is_error is 4xx or 5xx
    ...
```

## transport wrapper

[Wrapping][httpx2:transports] the default transport adds cross-cutting behavior; the client sets `response.request` afterwards.

```py
class Throttled(httpx2.AsyncBaseTransport):
    def __init__(self, inner: httpx2.AsyncBaseTransport | None = None, attempts: int = 3) -> None:
        self._inner = inner or httpx2.AsyncHTTPTransport(retries=2)  # retries connect failures only
        self._attempts = attempts

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        for attempt in range(self._attempts):
            response = await self._inner.handle_async_request(request)
            if response.status_code != 429 or attempt + 1 == self._attempts:
                return response  # stream stays open for the client to read and close
            await response.aclose()  # release the connection before sleeping
            await asyncio.sleep(float(response.headers.get("Retry-After", 1)))
        raise AssertionError("unreachable")

    async def aclose(self) -> None:
        await self._inner.aclose()

client = httpx2.AsyncClient(transport=Throttled())
# mounts route by URL pattern: {"all://": t1, "https://api.example.com": t2, "http://": None}
```

## errors

```py
# HTTPError
#   RequestError: TransportError (TimeoutException: Connect|Read|Write|Pool,
#                 NetworkError: Connect|Read|Write|Close, ProtocolError, ProxyError,
#                 UnsupportedProtocol, SSEError), DecodingError, TooManyRedirects
#   HTTPStatusError                       .request, .response
# InvalidURL, CookieConflict, StreamError (Consumed, Closed, ResponseNotRead, RequestNotRead)
try:
    payload = (await client.get("/items")).raise_for_status().json()
except httpx2.HTTPStatusError as error:
    status = error.response.status_code
    retry_after = error.response.headers.get("Retry-After")
except httpx2.TimeoutException:
    ...  # subclass of TransportError
except httpx2.RequestError as error:
    url = error.request.url  # never reached the server, or the body failed to arrive
```

## event hooks

Hooks are lists of callables; on an async client they are coroutine functions.

```py
async def stamp(request: httpx2.Request) -> None:  # after preparation, before sending
    request.headers["X-Request-Id"] = uuid4().hex

async def audit(response: httpx2.Response) -> None:  # before redirects and the caller
    await response.aread()  # required to touch response.content here
    log.info("%s %s %s", response.request.method, response.url, response.status_code)

async def fail(response: httpx2.Response) -> None:
    response.raise_for_status()

client = httpx2.AsyncClient(event_hooks={"request": [stamp], "response": [audit, fail]})
client.event_hooks["response"].append(audit)  # mutable after construction
```

## streaming and server-sent events

```py
# AsyncClient.stream(method, url, *, …) -> AsyncGenerator[Response]  (async context manager)
async with client.stream("GET", "/export", params={"format": "csv"}) as response:
    response.raise_for_status()
    async for line in response.aiter_lines():  # also aiter_bytes(), aiter_text(), aiter_raw()
        ...

# AsyncClient.sse(url, *, method="GET", max_event_size=1 MiB, …) -> AsyncGenerator[EventSource]
async with client.sse("/events", timeout=httpx2.Timeout(5.0, read=None)) as source:
    async for event in source:  # ServerSentEvent(event, data, id, retry); .json()
        ...  # a non-text/event-stream response raises SSEError
```

## mock transport

```py
# MockTransport(handler: Callable[[Request], Response | Awaitable[Response]])
def handler(request: httpx2.Request) -> httpx2.Response:
    if request.url.path == "/items":
        return httpx2.Response(200, json={"items": []})
    return httpx2.Response(404)

client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler), base_url="https://test")
# ASGITransport(app=asgi_app) and WSGITransport(app=wsgi_app) call an app in process
```

## migration from httpx

```py
import httpx2

httpx2.alias_httpx()  # first statement of the entrypoint, before anything imports httpx

# import httpx → httpx2; import httpcore → httpcore2; same classes, one process
# verify=True uses the OS trust store (truststore); SSL_CERT_FILE and SSL_CERT_DIR win
# verify=<path> and cert=… warn; pass verify=ssl.create_default_context(cafile=…)
# new: client.sse(), client.websocket() (httpx2[ws]), client.query() (HTTP QUERY)
# extras: http2, socks, brotli, zstd, cli, ws
```

## refs

[httpx2:docs]: https://pydantic.dev/docs/httpx2/

[httpx2:release]: https://pypi.org/project/httpx2/2.13.1/

[httpx2:changelog]: https://github.com/pydantic/httpx2/blob/main/src/httpx2/CHANGELOG.md

[httpx2:transports]: https://pydantic.dev/docs/httpx2/advanced/transports/
    It is not in the scope of HTTPX to trigger ASGI lifespan events of your app.

[httpx2:event-hooks]: https://pydantic.dev/docs/httpx2/advanced/event-hooks/
    Event hooks must always be set as a list of callables

[httpx2:timeouts]: https://pydantic.dev/docs/httpx2/advanced/timeouts/
    Timeout(None, connect=5.0)  # 5s timeout on connect, no other timeouts.

[httpx2:client]: https://github.com/pydantic/httpx2/blob/main/src/httpx2/_client.py
    It can be shared between tasks.

[httpx2:exceptions]: https://pydantic.dev/docs/httpx2/api/exceptions

[httpx2:alias]: https://github.com/pydantic/httpx2/blob/main/src/httpx2/_alias.py
    Libraries should never call this.
    Must be called before anything imports `httpx` or `httpcore`.
