# ============================================================================
# SSO Microsoft (Entra ID) — implementación lista para producción
#
# Variables de entorno requeridas:
#   MS_CLIENT_ID     → Application (client) ID del registro en Azure/Entra ID
#   MS_TENANT_ID     → Directory (tenant) ID
#   MS_CLIENT_SECRET → Client secret (valor) generado en "Certificates & secrets"
#   MS_REDIRECT_URI  → https://TU-DOMINIO/auth/callback (debe coincidir con Azure)
#   SESSION_SECRET   → clave aleatoria para firmar la cookie de sesión
#
# El SSO se activa solo si MS_CLIENT_ID, MS_TENANT_ID y MS_CLIENT_SECRET están
# definidos. Si faltan, sso_configured() devuelve False y main.py no monta el
# middleware (útil para desarrollo local sin credenciales).
# ============================================================================

import os

import msal
from fastapi import APIRouter, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse

# Se aceptan tanto los nombres MS_* como los AZURE_*_SSO usados en Cloud Run.
MS_CLIENT_ID = os.environ.get("MS_CLIENT_ID") or os.environ.get(
    "AZURE_CLIENT_ID_SSO", ""
)
MS_TENANT_ID = os.environ.get("MS_TENANT_ID") or os.environ.get(
    "AZURE_TENANT_ID_SSO", ""
)
MS_CLIENT_SECRET = os.environ.get("MS_CLIENT_SECRET") or os.environ.get(
    "AZURE_CLIENT_SECRET_SSO", ""
)
MS_AUTHORITY = f"https://login.microsoftonline.com/{MS_TENANT_ID}"
MS_SCOPES = ["User.Read"]
MS_REDIRECT_URI = os.environ.get(
    "MS_REDIRECT_URI", "http://localhost:8000/auth/callback"
)

# Rutas accesibles sin autenticación.
_PUBLIC_PATHS = {
    "/api/docs",
    "/api/openapi.json",
    "/auth/login",
    "/auth/callback",
    "/auth/logout",
    "/healthz",
}


def sso_configured() -> bool:
    """True solo si las tres credenciales esenciales están presentes."""
    return bool(MS_CLIENT_ID and MS_TENANT_ID and MS_CLIENT_SECRET)


def _build_msal_app() -> "msal.ConfidentialClientApplication":
    return msal.ConfidentialClientApplication(
        MS_CLIENT_ID,
        authority=MS_AUTHORITY,
        client_credential=MS_CLIENT_SECRET,
    )


class MicrosoftSSOMiddleware(BaseHTTPMiddleware):
    """Exige una sesión autenticada para todas las rutas no públicas."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if (
            path in _PUBLIC_PATHS
            or path.startswith("/assets")
            or path.startswith("/auth/")
        ):
            return await call_next(request)

        if not request.session.get("user"):
            # Para llamadas del API devolvemos 401 (el frontend redirige al login);
            # para navegación normal redirigimos directamente a Microsoft.
            if path.startswith("/api/"):
                from starlette.responses import JSONResponse

                return JSONResponse(
                    {"detail": "No autenticado"}, status_code=401
                )
            return RedirectResponse(url="/auth/login")

        return await call_next(request)


# ── Rutas de autenticación ──────────────────────────────────────────────────
auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.get("/login")
async def login(request: Request):
    if not sso_configured():
        raise HTTPException(status_code=503, detail="SSO no configurado")
    flow = _build_msal_app().initiate_auth_code_flow(
        scopes=MS_SCOPES,
        redirect_uri=MS_REDIRECT_URI,
    )
    # Guardamos el flow para validarlo en el callback (protege contra CSRF).
    request.session["auth_flow"] = flow
    return RedirectResponse(url=flow["auth_uri"])


@auth_router.get("/callback")
async def callback(request: Request):
    flow = request.session.get("auth_flow")
    if not flow:
        return RedirectResponse(url="/auth/login")

    result = _build_msal_app().acquire_token_by_auth_code_flow(
        flow,
        dict(request.query_params),
    )

    if "error" in result:
        raise HTTPException(
            status_code=401,
            detail=result.get("error_description", result["error"]),
        )

    claims = result.get("id_token_claims", {})
    request.session["user"] = {
        "name": claims.get("name"),
        "email": claims.get("preferred_username"),
        "oid": claims.get("oid"),
    }
    request.session.pop("auth_flow", None)
    return RedirectResponse(url="/")


@auth_router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    logout_url = (
        f"{MS_AUTHORITY}/oauth2/v2.0/logout"
        f"?post_logout_redirect_uri={MS_REDIRECT_URI.rsplit('/auth/', 1)[0]}/"
    )
    return RedirectResponse(url=logout_url)


@auth_router.get("/me")
async def me(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")
    return user
