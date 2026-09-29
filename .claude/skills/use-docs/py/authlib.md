# [authlib][authlib:docs]

1.8.0 · httpx2 native (httpx fallback deprecated) · Python 3.10+ syntax · [web clients][authlib:web] · [changes][authlib:changelog]

## register a provider with PKCE

[`OAuth.register(name, **kwargs)`][authlib:web] → the remote app; `client_kwargs` reach `AsyncOAuth2Client`.

```py
from authlib.integrations.starlette_client import OAuth, OAuthError
from starlette.middleware.sessions import SessionMiddleware

oauth = OAuth()
oauth.register(
    "provider",
    client_id="…",
    client_secret="…",
    authorize_url="https://idp.example/authorize",
    access_token_url="https://idp.example/token",
    api_base_url="https://idp.example/",
    client_kwargs={
        "scope": "openid email",
        "code_challenge_method": "S256",
        "token_endpoint_auth_method": "client_secret_post",
        "timeout": 10.0,
    },
)
app.add_middleware(SessionMiddleware, secret_key="…")
```

## discovery instead of endpoints

`register(..., server_metadata_url=…)` loads endpoints, issuer and JWKS lazily on first use.

```py
oauth.register(
    "oidc",
    client_id="…",
    client_secret="…",
    server_metadata_url="https://idp.example/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile", "code_challenge_method": "S256"},
)
```

## login and callback routes

`await app.authorize_redirect(request, redirect_uri)` → `RedirectResponse`; state, PKCE verifier and nonce are stored in `request.session`.

```py
@router.get("/login")
async def login(request: Request):
    return await oauth.oidc.authorize_redirect(request, str(request.url_for("callback")))


@router.get("/callback")
async def callback(request: Request):
    try:
        token = await oauth.oidc.authorize_access_token(request)
    except OAuthError as error:
        raise HTTPException(401, error.description or error.error)
    return dict(token["userinfo"])
```

## call the provider with the token

`await app.get(path, token=token)` sends the bearer header and resolves `api_base_url`.

```py
response = await oauth.provider.get("me", token=token)
response.raise_for_status()
identity = response.json()

info = await oauth.oidc.userinfo(token=token)        # UserInfo dict from userinfo_endpoint
claims = await oauth.oidc.parse_id_token(token, nonce=nonce)
```

## standalone async client

`AsyncOAuth2Client(client_id, client_secret, token_endpoint_auth_method=None, scope=None, redirect_uri=None, token=None, update_token=None, leeway=60, **httpx2_kwargs)` subclasses `httpx2.AsyncClient`.

```py
from authlib.common.security import generate_token
from authlib.integrations.httpx_client import AsyncOAuth2Client

verifier = generate_token(64)
async with AsyncOAuth2Client(
    "id", "secret", scope="openid", redirect_uri=callback, code_challenge_method="S256"
) as client:
    url, state = client.create_authorization_url(AUTHORIZE_URL, code_verifier=verifier)
    ...
    token = await client.fetch_token(TOKEN_URL, code=code, code_verifier=verifier)
    response = await client.get(ME_URL)    # token attached automatically
```

## token endpoint client authentication

`token_endpoint_auth_method` ∈ `client_secret_basic` (default with a secret), `client_secret_post`, `none` (default without a secret).

```py
client = AsyncOAuth2Client("id", "secret", token_endpoint_auth_method="client_secret_post")
public = AsyncOAuth2Client("id", token_endpoint_auth_method="none", code_challenge_method="S256")
```

## refresh and persist tokens

`update_token` is awaited with `(token, refresh_token=None, access_token=None)`; `leeway` refreshes early.

```py
async def update_token(token, refresh_token=None, access_token=None):
    await store.save(refresh_token or access_token, dict(token))


client = AsyncOAuth2Client(
    "id", "secret", token=saved_token, update_token=update_token, leeway=120
)
response = await client.get(API_URL)   # ensure_active_token refreshes under a lock

# the Starlette registry accepts the same hook once for every app
oauth = OAuth(update_token=update_token)
```

## state and PKCE storage

`OAuth(cache=…)` moves state data from the session cookie into a cache; the session keeps a marker.

```py
oauth = OAuth(cache=redis_cache)   # object with async get, set(key, value, expires), delete
rv = await oauth.oidc.create_authorization_url(redirect_uri)
# rv = {"url", "state", "code_verifier"?, "nonce"?}
await oauth.oidc.save_authorize_data(request, redirect_uri=redirect_uri, **rv)
```

## compliance hooks

`client.register_compliance_hook(hook_type, hook)` adapts nonstandard provider responses.

```py
def fix_token_response(response):
    data = response.json()
    data.setdefault("token_type", "Bearer")
    response._content = json.dumps(data).encode()
    return response


client.register_compliance_hook("access_token_response", fix_token_response)
oauth.register("provider", ..., compliance_fix=lambda session: session.register_compliance_hook(
    "access_token_response", fix_token_response
))
```

## refs

[authlib:docs]: https://docs.authlib.org/en/latest/

[authlib:web]: https://docs.authlib.org/en/stable/oauth2/client/web/index.html
    Authlib supports Proof Key for Code Exchange (PKCE) as defined in RFC7636.
    authorize_redirect returns a 302; id_token failures raise joserfc JoseError
    without id_token_signing_alg_values_supported in metadata, RS256 is assumed

[authlib:fastapi]: https://docs.authlib.org/en/stable/oauth2/client/web/fastapi.html

[authlib:changelog]: https://github.com/authlib/authlib/blob/main/docs/changelog.rst
    The httpx module is deprecated; please use httpx2 instead.
