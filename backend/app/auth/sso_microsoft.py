# ============================================================================
# SSO Microsoft — stub listo para activar
#
# CÓMO ACTIVAR:
# 1. Registrar una app en Azure AD (portal.azure.com → Azure Active Directory
#    → App registrations → New registration).
# 2. Agregar los siguientes secrets en GCP Secret Manager:
#       MS_CLIENT_ID     → Application (client) ID del registro de Azure
#       MS_TENANT_ID     → Directory (tenant) ID
#       MS_CLIENT_SECRET → Client secret generado en "Certificates & secrets"
# 3. En backend/app/main.py, descomentar las líneas:
#       from .auth.sso_microsoft import MicrosoftSSOMiddleware
#       app.add_middleware(MicrosoftSSOMiddleware)
# 4. En el frontend, redirigir al endpoint /auth/login cuando el API devuelva 401.
# ============================================================================

# import os
# from starlette.middleware.base import BaseHTTPMiddleware
# from starlette.requests import Request
# from starlette.responses import RedirectResponse, JSONResponse
# import msal
#
# MS_CLIENT_ID     = os.environ.get("MS_CLIENT_ID", "")
# MS_TENANT_ID     = os.environ.get("MS_TENANT_ID", "")
# MS_CLIENT_SECRET = os.environ.get("MS_CLIENT_SECRET", "")
# MS_AUTHORITY     = f"https://login.microsoftonline.com/{MS_TENANT_ID}"
# MS_SCOPES        = ["User.Read"]
# MS_REDIRECT_URI  = os.environ.get("MS_REDIRECT_URI", "https://TU-DOMINIO/auth/callback")
#
# _msal_app = msal.ConfidentialClientApplication(
#     MS_CLIENT_ID,
#     authority=MS_AUTHORITY,
#     client_credential=MS_CLIENT_SECRET,
# )
#
# _PUBLIC_PATHS = {"/api/docs", "/auth/login", "/auth/callback", "/healthz"}
#
#
# class MicrosoftSSOMiddleware(BaseHTTPMiddleware):
#     async def dispatch(self, request: Request, call_next):
#         if request.url.path in _PUBLIC_PATHS or request.url.path.startswith("/assets"):
#             return await call_next(request)
#
#         token = request.session.get("access_token")
#         if not token:
#             return RedirectResponse(url="/auth/login")
#
#         # Validar token con MSAL (simple: checar que existe en sesión)
#         # Para producción, validar con graph.microsoft.com/v1.0/me
#         return await call_next(request)
#
#
# def get_login_url() -> str:
#     return _msal_app.get_authorization_request_url(
#         scopes=MS_SCOPES,
#         redirect_uri=MS_REDIRECT_URI,
#     )
#
#
# def get_token_from_code(code: str) -> dict:
#     return _msal_app.acquire_token_by_authorization_code(
#         code=code,
#         scopes=MS_SCOPES,
#         redirect_uri=MS_REDIRECT_URI,
#     )
