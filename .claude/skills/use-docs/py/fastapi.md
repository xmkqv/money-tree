# [fastapi][fastapi:docs]

0.141.1 · starlette 1.7.0 · pydantic 2 · Python 3.10+

```py
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, TypedDict

import httpx
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
    Security,
    status,
)
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
```

[`FastAPI(lifespan=...)`][fastapi:lifespan] → app; the yielded dict becomes per-request `request.state`.

```py
class State(TypedDict):
    client: httpx.AsyncClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[State]:
    async with httpx.AsyncClient() as client:
        yield {"client": client}  # teardown runs after in-flight requests finish


app = FastAPI(title="Service", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


class AppRequest(Request[State]):
    pass  # a bare Request[State] parameter fails FastAPI's field check; subclass it


def get_client(request: AppRequest) -> httpx.AsyncClient:
    return request.state["client"]  # typed; attribute access is untyped


ClientDep = Annotated[httpx.AsyncClient, Depends(get_client)]
```

[`APIRouter(dependencies=[...])`][fastapi:bigger-applications] → router; `include_router(router, prefix=, dependencies=)` applies dependencies to every included route.

```py
async def require_member(request: Request) -> str:
    member = request.session.get("member")  # needs SessionMiddleware installed
    if not isinstance(member, str):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Login required", headers={"Cache-Control": "no-store"})
    return member


protected = APIRouter(prefix="/api", dependencies=[Depends(require_member)])
public = APIRouter()  # routes outside the guard stay on a separate router

app.include_router(protected)
app.include_router(public)
```

[`Depends(dep, use_cache=, scope=)` / `Security(dep, scopes=)`][fastapi:dependencies] → resolved once per request per callable; security schemes are dependency callables.

```py
csrf_scheme = APIKeyHeader(name="X-CSRF-Token", auto_error=False)


async def check_csrf(request: Request, token: Annotated[str | None, Security(csrf_scheme)]) -> None:
    expected = request.session.get("csrf")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and (not token or token != expected):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF token is invalid")


async def open_session(request: Request):
    resource = await acquire(request)
    try:
        yield resource
    finally:
        await release(resource)  # scope="function" (default) closes before the response is sent


Session = Annotated[object, Depends(open_session, scope="request")]  # scope="request" closes after send
mutating = APIRouter(dependencies=[Depends(check_csrf)])
```

[`Query(...)`][fastapi:query-validation] → parameter metadata; constraints, `alias`, `pattern`, or a whole pydantic model of query fields.

```py
class Filter(BaseModel):
    model_config = {"extra": "forbid"}  # unknown query keys → 422
    limit: int = Field(100, gt=0, le=1000)
    order: str = Field("asc", pattern=r"^(asc|desc)$")


@public.get("/items")
async def list_items(
    symbol: Annotated[str, Query(min_length=1, max_length=12, alias="sym")],
    page: Annotated[Filter, Query()],
    tags: Annotated[list[str], Query()] = [],
) -> dict[str, object]: ...
```

[`response_model` / return annotation][fastapi:response-model] → the return value is validated and filtered through the model; returning a `Response` skips it.

```py
class ItemIn(BaseModel):
    name: str
    secret: str


class ItemOut(BaseModel):
    name: str


@public.post("/items", status_code=status.HTTP_201_CREATED, response_model=ItemOut)
async def create_item(body: ItemIn) -> ItemIn:  # response_model wins; `secret` is dropped
    return body


@public.get("/raw", response_model=None)  # None disables inference from `-> JSONResponse | dict`
async def raw() -> JSONResponse | dict[str, int]:
    return JSONResponse({"n": 1}, headers={"Cache-Control": "no-store"})
```

[`HTTPException` and `@app.exception_handler`][fastapi:handling-errors] → handlers resolve by exception MRO; `HTTPException` renders `{"detail": ...}` with its `headers`.

```py
class Unavailable(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after


@app.exception_handler(Unavailable)
async def unavailable(_: Request, error: Unavailable) -> JSONResponse:
    return JSONResponse({"detail": "Busy"}, status.HTTP_503_SERVICE_UNAVAILABLE, {"Retry-After": str(error.retry_after)})


@app.exception_handler(ExceptionGroup)  # matches the exact class chain; `except*` splitting is manual
async def grouped(request: Request, group: ExceptionGroup) -> JSONResponse:
    busy, rest = group.split(Unavailable)
    if rest is not None:
        raise group  # re-raised errors reach the outermost handler → 500
    return await unavailable(request, busy.exceptions[0])
```

[`Response` parameter][fastapi:response-cookies] → a temporary response whose headers, cookies and status merge into the final response.

```py
@public.post("/session", status_code=status.HTTP_204_NO_CONTENT)
async def start(response: Response, request: Request) -> None:
    response.set_cookie("theme", "dark", max_age=3600, httponly=True, secure=True, samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Cookie"
    request.session["member"] = "id"  # the session cookie is written by its own middleware


@public.post("/logout", status_code=204)
async def stop(request: Request) -> Response:
    request.session.clear()
    response = Response(status_code=204)  # returning a Response ignores the injected one
    response.delete_cookie("theme", path="/")
    return response
```

[`BackgroundTasks`][fastapi:background-tasks] → runs after the response is sent; a task added in a dependency shares the same collection.

```py
def audit(message: str) -> None:  # sync callables run in a threadpool
    ...


async def notify(client: httpx.AsyncClient, url: str) -> None:
    await client.post(url)


@mutating.post("/orders", status_code=status.HTTP_202_ACCEPTED)
async def place(tasks: BackgroundTasks, client: ClientDep) -> dict[str, str]:
    tasks.add_task(audit, "placed")
    tasks.add_task(notify, client, "https://example.test/hook")
    return {"status": "accepted"}
```

[`TestClient`][fastapi:testing] → synchronous httpx client; `with` runs lifespan; `dependency_overrides` swaps dependencies.

```py
def test_protected() -> None:
    app.dependency_overrides[require_member] = lambda: "tester"
    try:
        with TestClient(app, raise_server_exceptions=False) as client:  # `with` runs lifespan
            reply = client.get("/api/items", params={"sym": "ABC", "limit": 5})
            assert reply.status_code == 200
            assert client.post("/orders", headers={"X-CSRF-Token": "bad"}).status_code == 403
    finally:
        app.dependency_overrides.clear()
```

[`EventSourceResponse`][fastapi:sse] → an async generator path operation streams server-sent events; yielded models and dicts become JSON `data`.

```py
from fastapi.sse import EventSourceResponse, ServerSentEvent


class Tick(BaseModel):
    price: float


@public.get("/ticks", response_class=EventSourceResponse)
async def ticks() -> AsyncIterator[Tick | ServerSentEvent]:
    yield Tick(price=1.0)
    yield ServerSentEvent(data={"price": 2.0}, event="tick", id="2", retry=3000)


app.frontend("/", directory="dist", fallback="auto")  # static build served after every route misses
```

## refs

[fastapi:docs]: https://fastapi.tiangolo.com/

[fastapi:lifespan]: https://fastapi.tiangolo.com/advanced/events/

[fastapi:bigger-applications]: https://fastapi.tiangolo.com/tutorial/bigger-applications/
    Cannot include the same APIRouter instance into itself.
    A path prefix must not end with '/', as the routes will start with '/'

[fastapi:dependencies]: https://fastapi.tiangolo.com/tutorial/dependencies/
    Don't call it directly, FastAPI will call it for you

[fastapi:query-validation]: https://fastapi.tiangolo.com/tutorial/query-params-str-validations/

[fastapi:response-model]: https://fastapi.tiangolo.com/tutorial/response-model/
    **Deprecated**: `ORJSONResponse` is deprecated.

[fastapi:handling-errors]: https://fastapi.tiangolo.com/tutorial/handling-errors/

[fastapi:response-cookies]: https://fastapi.tiangolo.com/advanced/response-cookies/

[fastapi:background-tasks]: https://fastapi.tiangolo.com/tutorial/background-tasks/

[fastapi:testing]: https://fastapi.tiangolo.com/tutorial/testing/

[fastapi:sse]: https://fastapi.tiangolo.com/tutorial/server-sent-events/

[fastapi:strict-content-type]: https://fastapi.tiangolo.com/advanced/strict-content-type/
    Enable strict checking for request Content-Type headers.
