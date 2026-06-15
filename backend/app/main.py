import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from .routes.liquidacion import router as liquidacion_router
from .auth.sso_microsoft import (
    MicrosoftSSOMiddleware,
    auth_router,
    sso_configured,
)

app = FastAPI(
    title="Liquidador de Pago a Mandantes — Macal",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url=None,
)

# Con SSO activo y cookies de sesión, el origen debe ser explícito (no "*").
_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── SSO Microsoft ───────────────────────────────────────────────────────────
# Se activa solo si MS_CLIENT_ID / MS_TENANT_ID / MS_CLIENT_SECRET están
# definidos. El orden importa: SessionMiddleware se agrega después para que
# request.session esté disponible dentro del MicrosoftSSOMiddleware.
if sso_configured():
    app.add_middleware(MicrosoftSSOMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=os.environ.get("SESSION_SECRET", os.urandom(32).hex()),
        https_only=True,
        same_site="lax",
    )
    app.include_router(auth_router)
# ──────────────────────────────────────────────────────────────────────────

app.include_router(liquidacion_router)


@app.get("/healthz", include_in_schema=False)
async def healthz():
    return {"status": "ok"}

# Servir el frontend React buildado (generado por `npm run build` en /frontend)
_STATIC = Path(__file__).parent.parent.parent / "frontend" / "dist"
if _STATIC.exists():
    app.mount("/assets", StaticFiles(directory=str(_STATIC / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """Devuelve index.html para cualquier ruta que no sea /api — necesario para React Router."""
        index = _STATIC / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"detail": "Frontend no buildado. Ejecuta: cd frontend && npm run build"}
