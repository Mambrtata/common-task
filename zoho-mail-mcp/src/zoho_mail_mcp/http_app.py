"""HTTP transport – konektor ako sieťová služba pre viacero klientov.

Použitie: server beží na jednom stroji (napr. domácom serveri v ZeroTier sieti)
a Claude Code na firemných počítačoch sa naň pripája cez `--transport http`.
Prístup chráni zdieľaný bearer token; bez neho sa server odmietne spustiť.
"""

from __future__ import annotations

import hmac
import logging

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from .attachments import resolve_inside
from .config import download_dir_from_env
from .errors import ConfigError, ZohoMailMCPError
from .signing import verify as verify_signature

logger = logging.getLogger(__name__)

# Kratší token nemá zmysel – je to jediné, čo delí sieť od firemnej pošty.
MIN_TOKEN_LENGTH = 24

MCP_PATH = "/mcp"
HEALTH_PATH = "/health"
FILES_PREFIX = "/files"


class BearerTokenMiddleware:
    """Prepustí len požiadavky so správnou hlavičkou Authorization: Bearer."""

    def __init__(
        self,
        app: ASGIApp,
        token: str,
        exempt_paths: frozenset[str] = frozenset(),
        signed_prefix: str | None = None,
    ) -> None:
        self._app = app
        self._token = token
        self._exempt_paths = exempt_paths
        self._signed_prefix = signed_prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") in self._exempt_paths:
            await self._app(scope, receive, send)
            return

        if not self._authorized(scope) and not self._has_valid_signature(scope):
            client = scope.get("client")
            logger.warning(
                "Odmietnutá požiadavka bez platného tokenu z %s",
                client[0] if client else "neznámej adresy",
            )
            response = JSONResponse(
                {"error": "unauthorized", "detail": "Chýba alebo nesedí bearer token."},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return

        await self._app(scope, receive, send)

    def _has_valid_signature(self, scope: Scope) -> bool:
        """Podpísaný odkaz na konkrétny súbor platí namiesto hlavičky."""
        path = scope.get("path", "")
        if not self._signed_prefix or not path.startswith(self._signed_prefix + "/"):
            return False
        name = path[len(self._signed_prefix) + 1:]
        query = scope.get("query_string", b"").decode("latin-1")
        return verify_signature(name, query, self._token)

    def _authorized(self, scope: Scope) -> bool:
        for raw_name, raw_value in scope.get("headers", []):
            if raw_name.lower() != b"authorization":
                continue
            value = raw_value.decode("latin-1").strip()
            scheme, _, token = value.partition(" ")
            if scheme.lower() != "bearer":
                return False
            # Porovnávame bajty, nie reťazce: compare_digest na reťazcoch
            # vyhodí TypeError, keď v hlavičke pristane čokoľvek mimo ASCII,
            # a z odmietnutej požiadavky by sa stala chyba servera.
            return hmac.compare_digest(
                token.strip().encode("utf-8"), self._token.encode("utf-8")
            )
        return False


def default_allowed_hosts(host: str, port: int) -> list[str]:
    """Hostitelia, ktorých server uzná v hlavičke Host.

    Ochrana proti DNS rebindingu porovnáva Host s týmto zoznamom. Preto sa
    oplatí viazať sa priamo na ZeroTier adresu – potom to vyjde samo. Pri
    0.0.0.0 sa adresa odvodiť nedá a treba ZOHO_MCP_ALLOWED_HOSTS.
    """
    hosts = ["localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*"]
    if host not in ("0.0.0.0", "::", ""):
        hosts.extend([host, f"{host}:*", f"{host}:{port}"])
    return hosts


def build_app(
    server: MCPServer,
    *,
    token: str,
    host: str,
    port: int,
    allowed_hosts: list[str] | None = None,
) -> Starlette:
    """Postaví ASGI aplikáciu: /mcp za tokenom, /health voľne dostupné."""
    if not token or len(token) < MIN_TOKEN_LENGTH:
        raise ConfigError(
            "ZOHO_MCP_AUTH_TOKEN musí mať aspoň "
            f"{MIN_TOKEN_LENGTH} znakov. Vygeneruj ho príkazom: "
            "python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )

    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts or default_allowed_hosts(host, port),
        allowed_origins=[],
    )

    # stateless_http: každá požiadavka stojí sama o sebe, takže reštart servera
    # nezhodí klientom rozrobenú session a viacero klientov si nelezie do cesty.
    inner = server.streamable_http_app(
        streamable_http_path=MCP_PATH,
        stateless_http=True,
        transport_security=security,
        host=host,
    )

    async def health(_request):
        return JSONResponse({"status": "ok", "service": "zoho-mail-mcp"})

    downloads = download_dir_from_env()

    async def files(request):
        """Vydá stiahnutú prílohu. Za tokenom, len z priečinka s prílohami."""
        try:
            target = resolve_inside(downloads, request.path_params["name"])
        except ZohoMailMCPError:
            return JSONResponse({"error": "invalid_path"}, status_code=400)
        if not target.is_file():
            return JSONResponse({"error": "not_found"}, status_code=404)
        return FileResponse(target, filename=target.name)

    app = Starlette(
        routes=[
            Route(HEALTH_PATH, health, methods=["GET"]),
            Route(FILES_PREFIX + "/{name:path}", files, methods=["GET"]),
            Mount("/", app=inner),
        ],
        lifespan=lambda scope: inner.router.lifespan_context(scope),
    )
    return BearerTokenMiddleware(
        app,
        token,
        exempt_paths=frozenset({HEALTH_PATH}),
        signed_prefix=FILES_PREFIX,
    )


def serve_http(
    server: MCPServer,
    *,
    token: str,
    host: str,
    port: int,
    allowed_hosts: list[str] | None = None,
) -> None:
    """Spustí konektor ako HTTP službu."""
    import uvicorn

    app = build_app(
        server, token=token, host=host, port=port, allowed_hosts=allowed_hosts
    )
    if host in ("0.0.0.0", "::"):
        logger.warning(
            "Server počúva na všetkých rozhraniach. Ak má byť dostupný len "
            "cez ZeroTier, viaž ho radšej priamo na ZeroTier adresu."
        )
    uvicorn.run(app, host=host, port=port, log_level="info")
