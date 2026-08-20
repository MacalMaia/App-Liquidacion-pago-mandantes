from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from fastapi.responses import Response
from typing import Optional

from ..services.pago_mandates import (
    extract_json_mandato_from_pdf,
    extraer_json_liquidacion,
    liquidar_pago,
)
from ..services.generar_pdf import generar_pdf_bytes

router = APIRouter(prefix="/api", tags=["liquidacion"])


@router.post("/liquidar")
async def liquidar(
    mandato: UploadFile = File(..., description="PDF del mandato notarial"),
    liquidacion: UploadFile = File(..., description="PDF de la liquidación de pago"),
    # Datos desde Legal
    vale_vista: str = Form("No"),
    costo_vale_vista: Optional[int] = Form(None),
    monto_vale_vista: Optional[int] = Form(None),
    instrucciones: str = Form("No"),
    costo_instrucciones: Optional[int] = Form(None),
    antecedentes: str = Form("No"),
    costo_antecedentes: Optional[int] = Form(None),
    descuenta_gastos: str = Form("Sí"),
):
    """
    Recibe el mandato y la liquidación en PDF, extrae los datos con Claude
    y devuelve el resultado de la liquidación como JSON.
    """
    try:
        mandato_bytes = await mandato.read()
        liquidacion_bytes = await liquidacion.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error leyendo archivos: {e}")

    try:
        man = extract_json_mandato_from_pdf(mandato_bytes)
        liq = extraer_json_liquidacion(liquidacion_bytes)
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"No se pudieron leer los PDFs: {e}",
        ) from e

    # Inyectar datos manuales
    man["vale_vista_var"] = vale_vista
    man["costo_vale_vista"] = costo_vale_vista if vale_vista == "Sí" else 0
    man["monto_vale_vista"] = monto_vale_vista if vale_vista == "Sí" else 0
    man["instrucciones_var"] = instrucciones
    man["costo_instrucciones"] = costo_instrucciones if instrucciones == "Sí" else 0
    man["antecedentes_var"] = antecedentes
    man["costo_antecedentes"] = costo_antecedentes if antecedentes == "Sí" else 0
    man["descuenta_gastos"] = descuenta_gastos

    try:
        resultado = liquidar_pago(liq, man)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en el cálculo: {e}")

    return resultado


@router.post("/pdf")
async def generar_pdf_endpoint(resultado: dict):
    """
    Recibe el resultado JSON de /api/liquidar y devuelve el PDF como bytes
    para descarga directa en el navegador.
    """
    try:
        pdf_bytes = generar_pdf_bytes(resultado)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando PDF: {e}")

    ident = resultado.get("identificacion", {})
    fecha = (ident.get("fecha_subasta") or "").replace("-", "")
    lote = ident.get("numero_lote") or ""
    filename = f"preliquidacion_{fecha}_lote{lote}.pdf" if (fecha or lote) else "preliquidacion.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
