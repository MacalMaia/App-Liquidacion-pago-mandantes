import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from .routes.liquidacion import router as liquidacion_router

# ── SSO Microsoft (comentado hasta activar) ────────────────────────────────
# from .auth.sso_microsoft import MicrosoftSSOMiddleware
# app.add_middleware(MicrosoftSSOMiddleware)
# ──────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Liquidador de Pago a Mandantes — Macal",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restringir en producción con SSO activo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(liquidacion_router)

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
