import json, base64, re, os, logging
from io import BytesIO
from anthropic import Anthropic, BadRequestError, APIError
from decimal import Decimal, ROUND_HALF_UP
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError, FileNotDecryptedError

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL1 = "claude-opus-4-5"
MODEL2 = "claude-sonnet-4-5"
_MAX_PDF_BYTES = 32 * 1024 * 1024

logger = logging.getLogger(__name__)


def _pdf_to_base64(pdf_bytes: bytes) -> str:
    return base64.b64encode(pdf_bytes).decode("utf-8")


def _normalizar_pdf(pdf_bytes: bytes, etiqueta: str) -> bytes:
    """Valida y reescribe el PDF para que Anthropic lo acepte.

    Caso real (fojas.cl / mandatos con firma electrónica):
    - El archivo empieza con basura HTML (`<br>-->...`) y el `%PDF` va más adelante.
    - El PDF viene cifrado con contraseña de usuario vacía.
    Anthropic exige que el archivo empiece en `%PDF` y rechaza cifrados:
    400 'The PDF specified was not valid'.
    """
    if not pdf_bytes:
        raise RuntimeError(f"El archivo {etiqueta} está vacío.")
    if len(pdf_bytes) > _MAX_PDF_BYTES:
        raise RuntimeError(
            f"El archivo {etiqueta} pesa {len(pdf_bytes) // (1024 * 1024)} MB. "
            "El máximo aceptado es 32 MB."
        )

    start = pdf_bytes.find(b"%PDF")
    if start == -1:
        raise RuntimeError(
            f"El archivo {etiqueta} no es un PDF válido. "
            "Verifica que sea el documento original y no una imagen, captura o Word."
        )
    if start > 0:
        logger.info("PDF %s: se recortaron %s bytes de basura antes de %%PDF", etiqueta, start)
    raw = pdf_bytes[start:]

    try:
        reader = PdfReader(BytesIO(raw), strict=False)
    except (PdfReadError, Exception) as e:
        logger.warning("No se pudo abrir %s con pypdf (%s); se envía recortado.", etiqueta, e)
        return raw

    estaba_cifrado = bool(reader.is_encrypted)
    if estaba_cifrado:
        unlocked = False
        for pwd in ("", " "):
            try:
                if reader.decrypt(pwd):
                    unlocked = True
                    break
            except (FileNotDecryptedError, Exception):
                continue
        if not unlocked:
            raise RuntimeError(
                f"El PDF {etiqueta} está protegido con contraseña. "
                "Ábrelo, quítale la protección (Archivo → Imprimir → Guardar como PDF) e inténtalo de nuevo."
            )

    if not reader.pages:
        raise RuntimeError(f"El PDF {etiqueta} no tiene páginas.")

    try:
        writer = PdfWriter()
        writer.append(reader)
        buf = BytesIO()
        writer.write(buf)
        normalized = buf.getvalue()
    except Exception as e:
        if estaba_cifrado:
            raise RuntimeError(
                f"El PDF {etiqueta} está cifrado y no se pudo reescribir para el extractor. "
                "Ábrelo y guárdalo como PDF nuevo (Imprimir → Guardar como PDF)."
            ) from e
        logger.warning("No se pudo reescribir %s (%s); se envía recortado.", etiqueta, e)
        return raw

    if not normalized.startswith(b"%PDF") or len(normalized) < 100:
        if estaba_cifrado:
            raise RuntimeError(
                f"El PDF {etiqueta} quedó ilegible al quitar la protección. "
                "Guárdalo como PDF nuevo e inténtalo de nuevo."
            )
        return raw

    logger.info(
        "PDF %s normalizado: %s bytes → %s bytes, %s páginas, cifrado=%s",
        etiqueta, len(pdf_bytes), len(normalized), len(reader.pages), estaba_cifrado,
    )
    return normalized


def _error_pdf_invalido(etiqueta: str, exc: Exception) -> RuntimeError:
    return RuntimeError(
        f"El PDF {etiqueta} no pudo ser leído por el extractor. "
        "Suele pasar si el archivo está dañado, protegido o no es un PDF real. "
        "Prueba abrirlo y 'imprimir a PDF' (Guardar como PDF) e inténtalo de nuevo. "
        f"Detalle: {exc}"
    )


def _crear_cliente() -> Anthropic:
    if not API_KEY:
        raise RuntimeError("Falta ANTHROPIC_API_KEY en el entorno.")
    return Anthropic(api_key=API_KEY)


def extract_json_mandato_from_pdf(pdf_bytes: bytes) -> dict:
    encoded_pdf = _pdf_to_base64(_normalizar_pdf(pdf_bytes, "del mandato"))
    client = _crear_cliente()

    system_prompt = (
        "Eres un extractor de datos legal. Devuelve SOLO JSON minificado (una línea), con las claves exactas:\n"
        '["comision_macal","tipo_comision","condicion_premio","paga_premio","tramos_premio","fecha_firma_mandato","mandante",'
        '"representante_legal","paga_publicidad","monto_publicidad_pesos"]. '
        "Reglas:\n"
        "- comision_macal: porcentaje o monto en pesos que cobra Macal por la venta. "
        "CRÍTICO: el porcentaje es SIEMPRE un número entre 0 y 100, NO entre 0 y 1. "
        "Ejemplos: 'dos coma cero por ciento' = 2.0, 'dos punto cinco por ciento' = 2.5, '15%' = 15.0. "
        "NUNCA devuelvas 0.02 ni 0.2 cuando el texto dice '2%' o 'dos por ciento'. "
        "IMPORTANTE: si el documento menciona que la comisión está en una tabla anexa o protocolizada, "
        "busca esa tabla en el mismo PDF (puede estar al final o como página separada) y extrae el porcentaje base o general. "
        "Si la tabla tiene múltiples filas por tipo de propiedad, extrae el porcentaje que aplica a departamentos o el valor más frecuente. "
        "Si absolutamente no existe en el documento, usa null.\n"
        "- El tipo_comision puede ser en porcentaje o pesos, este campo debe incluir las palabras 'Pesos' o 'Porcentaje' según corresponda.\n"
        "- Determinar si las condiciones pactadas incluyen pago de premio (true/false). Esta condición se encuentra únicamente en la sección PREMIO.\n"
        "- 'tramos_premio': array con TODOS los tramos de premio definidos en el mandato. Si paga_premio es false, devuelve []. "
        "Cada elemento del array tiene EXACTAMENTE estas claves: "
        "{\"tipo_propiedad\": string o null, \"base_uf\": número decimal, \"base_pesos\": número entero o null, \"porcentaje\": número decimal, \"condicion\": string}. "
        "Reglas de tramos_premio:\n"
        "  * tipo_propiedad: categoría de propiedad a la que aplica el tramo (ej: 'departamento', 'estacionamiento', 'casa', 'bodega'). "
        "    Si aplica a todos los tipos, usar null.\n"
        "  * base_uf: umbral mínimo en UF que debe alcanzar la adjudicación para que aplique este tramo. "
        "    Usar SOLO si el umbral está expresado explícitamente en UF en el mandato. Si no está en UF, usar 0.0.\n"
        "  * base_pesos: umbral mínimo en PESOS CHILENOS. Usar si el umbral está expresado en pesos (ej: '$6.000.000'). "
        "    Si el umbral ya está en UF (campo base_uf), usar null aquí. Si el tramo aplica desde 0 sin umbral, usar null.\n"
        "  * porcentaje: porcentaje del diferencial (monto adjudicado - umbral base) que se paga como premio. Número decimal (ej: 2.5).\n"
        "  * condicion: texto literal del mandato que describe la condición de este tramo.\n"
        "  IMPORTANTE: si el mandato define distintos umbrales para el mismo tipo de propiedad, "
        "  crea UN tramo por cada umbral. NO simplifiques ni promedies.\n"
        "- 'condicion_premio': texto completo y literal de la sección PREMIO del mandato, sin omitir nada.\n"
        "- representante_legal: En caso que no se mencione ningun representante legal, usa null.\n"
        "- Formato de fecha: dd-mm-yyyy. Si no existe, usa null.\n"
        "- Los montos en pesos deben ser enteros sin separadores (ej: 6000000). Si no aplica o no es determinable, usa null.\n"
        "- Debes determinar si la publicidad la paga el mandante o la mandataria. En caso que la publicidad la pague el mandante paga_publicidad debe ser true, si la paga la mandataria paga_publicidad es false. Si no existe clausula de publicidad, paga_publicidad es false.\n"
        "- monto_publicidad_pesos debe ser 0 si paga_publicidad es false.\n"
        "- No inventes datos. Si falta información, usa null.\n"
        "Responde ÚNICAMENTE con el JSON solicitado, sin texto adicional."
    )

    try:
        response = client.messages.create(
            model=MODEL1,
            max_tokens=1500,
            temperature=0,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extrae los campos requeridos del siguiente PDF con el mandato notarial escaneado. Devuelve solo JSON."},
                    {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": encoded_pdf}}
                ]
            }]
        )
    except BadRequestError as e:
        raise _error_pdf_invalido("del mandato", e) from e
    except APIError as e:
        raise RuntimeError(f"Error del servicio de extracción (mandato): {e}") from e

    content_blocks = response.content
    if not content_blocks or content_blocks[0].type != "text":
        raise RuntimeError("Respuesta inesperada del modelo.")

    raw_original = content_blocks[0].text
    raw_json = _limpiar_json(raw_original)

    if not raw_json:
        raise RuntimeError(
            f"El modelo devolvió una respuesta vacía para el mandato.\n"
            f"Respuesta original: {repr(raw_original[:200])}"
        )

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"No se pudo parsear la respuesta del mandato como JSON: {e}\n"
            f"Respuesta recibida: {repr(raw_json[:300])}"
        ) from e

    def to_int_or_null(v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return int(v)
        s = str(v).strip().replace(".", "").replace(",", "")
        return int(s) if s.isdigit() else None

    com_raw = _float_or_none(data.get("comision_macal"))
    if com_raw is not None and 0 < com_raw < 1:
        com_raw = round(com_raw * 100, 4)
    data["comision_macal"] = com_raw
    data["monto_publicidad_pesos"] = to_int_or_null(data.get("monto_publicidad_pesos"))

    tramos_raw = data.get("tramos_premio")
    if not isinstance(tramos_raw, list):
        tramos_raw = []

    def _to_int_pesos(v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return int(v)
        s = str(v).strip().replace("$", "").replace(".", "").replace(",", "").replace(" ", "")
        return int(s) if re.fullmatch(r"\d+", s) else None

    def _corregir_porcentaje(v):
        f = _float_or_none(v) or 0.0
        if 0 < f < 1:
            f = round(f * 100, 4)
        return f

    data["tramos_premio"] = [
        {
            "tipo_propiedad": t.get("tipo_propiedad"),
            "base_uf": _float_or_none(t.get("base_uf")) or 0.0,
            "base_pesos": _to_int_pesos(t.get("base_pesos")),
            "porcentaje": _corregir_porcentaje(t.get("porcentaje")),
            "condicion": str(t.get("condicion") or ""),
        }
        for t in tramos_raw if isinstance(t, dict)
    ]

    if isinstance(data.get("paga_publicidad"), str):
        data["paga_publicidad"] = data["paga_publicidad"].strip().lower() in ("true", "sí", "si", "yes")

    return data


# ========== Utiles ==========
def _limpiar_json(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    if raw.startswith("{"):
        return raw
    inicio = raw.find("{")
    fin = raw.rfind("}")
    if inicio != -1 and fin != -1 and fin > inicio:
        return raw[inicio:fin + 1]
    return raw


def construir_mensaje_liquidacion(encoded_pdf: str):
    system_prompt = (
        "Eres un extractor de datos contables. Devuelve SOLO JSON minificado (una línea) "
        "con EXACTAMENTE estas claves en español:\n"
        '["cliente_vendedor","numero_lote","propiedad","comuna","tipo_propiedad","valor_adjudicacion_pesos","valor_adjudicacion_uf",'
        '"precio_proyectado_uf","fecha_subasta","uf_dia_subasta","abonos_comprador_pesos"].\n'
        "El documento puede venir en DOS formatos distintos (identifica cuál es por su título):\n"
        "  (A) título 'Liquidación de Pago', con columnas 'CARGO' (pesos) y 'CARGO UF'.\n"
        "  (B) título 'SALDO - PRECIO', con una tabla de columnas FECHA | VALOR UF | CARGO UF | ABONO UF | ABONO, "
        "      y una fila final 'ABONADO AL <fecha>' con el total pagado a la fecha.\n"
        "Instrucciones por campo:\n"
        "- cliente_vendedor: en formato (A) es el título principal que aparece justo ARRIBA de la frase 'Liquidación de Pago'. "
        "  En formato (B) es el valor de la fila/etiqueta 'MANDANTE'. "
        "  No es el adjudicatario/comprador; es el vendedor/mandante de la propiedad.\n"
        "- numero_lote: aparece junto a la palabra 'Lote' (NO junto a 'N° REMATE', que es un código alfanumérico distinto). Devuelvelo como entero sin separadores.\n"
        "- propiedad: es el texto que aparece en la fila/etiqueta 'Propiedad' (o 'PROPIEDAD'). Devuelve exactamente el texto de esa fila/etiqueta sin agregar nada. Si no existe, usa null.\n"
        "- comuna: es el texto que aparece en la fila/etiqueta 'Comuna' (o 'COMUNA'). Devuelve exactamente el texto de esa fila/etiqueta sin agregar nada. Si no existe, usa null.\n"
        "- tipo_propiedad: clasifica la propiedad según el campo 'Propiedad' o cualquier descripción del documento. "
        "  Devuelve EXACTAMENTE una de estas palabras (en minúsculas): 'departamento', 'estacionamiento', 'bodega', 'casa', 'terreno', 'local', 'oficina', 'otro'. "
        "  Si no es posible determinarlo, devuelve null.\n"
        "- valor_adjudicacion_pesos: SOLO en formato (A), la PRIMERA línea (primer ítem) de la columna 'CARGO' (en pesos). "
        "  En formato (B) esta columna en pesos NO EXISTE para la fila 'Precio de adjudicación' (solo existe 'CARGO UF'): en ese caso devuelve SIEMPRE null, "
        "  el valor en pesos se calculará después a partir de la UF. "
        "  CRÍTICO: NUNCA uses el valor de la fila 'ABONADO AL' ni de 'ABONO' (que son el total pagado por el comprador, un concepto distinto) como valor_adjudicacion_pesos, "
        "  aunque sean el número en pesos más prominente del documento.\n"
        "- valor_adjudicacion_uf: la PRIMERA línea (primer ítem, fila 'Precio de adjudicación') de la columna 'CARGO UF'. Devuelve número con punto decimal (ej: 800.0).\n"
        "- precio_proyectado_uf: precio proyectado o mínimo de la propiedad en UF. Puede aparecer como 'Precio proyectado', 'Mínimo', 'Base', 'Proyectado' o similar. Devuelve número con punto decimal. Si no existe, devuelve null.\n"
        "- fecha_subasta: la fecha que aparece en la fila/etiqueta 'Remate efectuado en' o 'REMATE EFECTUADO EL', devuelve la fecha en formato dd-mm-yyyy.\n"
        "- uf_dia_subasta: el valor de la columna 'VALOR UF' de la MISMA fila que 'Precio de adjudicación' (primera fila de la tabla). "
        "CRÍTICO: este valor es el precio en PESOS CHILENOS de 1 UF, típicamente entre 30.000 y 50.000 pesos. "
        "El documento usa formato chileno donde el punto es separador de miles y la coma es el decimal. "
        "Ejemplo: '$40.307,26' en el PDF = 40307.26 en el JSON (NO 40.30726). "
        "Devuelve SIEMPRE un número mayor a 1000.\n"
        "- abonos_comprador_pesos: en formato (A), valor de la fila 'ABONADO EN PESOS'. "
        "  En formato (B), valor en pesos (última columna) de la fila 'ABONADO AL <fecha>' (el total pagado a la fecha del documento). "
        "  Devuelve entero sin separadores.\n"
        "Reglas generales:\n"
        "- Si un dato no existe o no es claramente identificable, devuelve null.\n"
        "- No incluyas texto adicional, comentarios, ni campos extra. SOLO el JSON minificado pedido."
    )
    return [
        {"type": "text", "text": "Lee el PDF adjunto ('Liquidación de Pago') con tablas y títulos. Extrae únicamente los campos indicados, respetando las reglas y retornando SOLO JSON minificado en una línea."},
        {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": encoded_pdf}}
    ], system_prompt


def parse_int_or_null(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip().replace("$", "").replace("CLP", "").replace("UF", "")
    s = s.replace(".", "").replace(",", "")
    return int(s) if re.fullmatch(r"\d+", s) else None


def parse_float_or_null(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("UF", "").replace("$", "")
    s = s.replace(".", "").replace(" ", "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None


def extraer_json_liquidacion(pdf_bytes: bytes) -> dict:
    client = _crear_cliente()
    encoded = _pdf_to_base64(_normalizar_pdf(pdf_bytes, "de saldo de precio"))
    content, system_prompt = construir_mensaje_liquidacion(encoded)

    try:
        resp = client.messages.create(
            model=MODEL2,
            max_tokens=800,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": content}],
        )
    except BadRequestError as e:
        raise _error_pdf_invalido("de saldo de precio", e) from e
    except APIError as e:
        raise RuntimeError(f"Error del servicio de extracción (saldo de precio): {e}") from e

    if not resp.content or resp.content[0].type != "text":
        raise RuntimeError("Respuesta inesperada del modelo de Anthropic.")
    raw_original = resp.content[0].text
    raw = _limpiar_json(raw_original)

    if not raw:
        raise RuntimeError(
            f"El modelo devolvió una respuesta vacía para la liquidación.\n"
            f"Respuesta original: {repr(raw_original[:200])}"
        )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"No se pudo parsear la respuesta del modelo como JSON: {e}\n"
            f"Respuesta recibida: {repr(raw[:300])}"
        ) from e

    data["valor_adjudicacion_pesos"] = parse_int_or_null(data.get("valor_adjudicacion_pesos"))
    data["abonos_comprador_pesos"] = parse_int_or_null(data.get("abonos_comprador_pesos"))
    data["valor_adjudicacion_uf"] = parse_float_or_null(data.get("valor_adjudicacion_uf"))
    data["precio_proyectado_uf"] = parse_float_or_null(data.get("precio_proyectado_uf"))

    uf_raw = parse_float_or_null(data.get("uf_dia_subasta"))
    if uf_raw is not None and 0 < uf_raw < 1000:
        uf_raw = round(uf_raw * 1000, 2)
    data["uf_dia_subasta"] = uf_raw

    _tipos_validos = {"departamento", "estacionamiento", "bodega", "casa", "terreno", "local", "oficina", "otro"}
    tp = (data.get("tipo_propiedad") or "").strip().lower()
    data["tipo_propiedad"] = tp if tp in _tipos_validos else None

    return data


# ========== Main ==========
def _round0(x): return int(Decimal(str(x)).quantize(0, rounding=ROUND_HALF_UP))


def _int_or_none(v):
    try:
        if v is None:
            return None
        return int(str(v).replace(".", "").replace(",", "").strip())
    except Exception:
        return None


def _float_or_none(v):
    try:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().replace(" ", "")
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            s = s.replace(",", ".")
        return float(s)
    except Exception:
        return None


def _apply_iva(amount, iva_rate, apply):
    return 0 if (not apply or amount is None) else _round0(amount * iva_rate)


def liquidar_pago(
    liq: dict,
    man: dict,
    *,
    iva_rate=0.19,
    iva_comision=True,
    iva_premio=True,
    iva_publicidad=True,
    base_comision="adjudicacion_pesos",
):
    alertas = []

    cliente_vendedor = liq.get("cliente_vendedor")
    valor_adjudicacion_pesos_raw = liq.get("valor_adjudicacion_pesos")
    valor_adjudicacion_uf_raw = liq.get("valor_adjudicacion_uf")
    uf_dia_subasta_raw = liq.get("uf_dia_subasta")
    abonos_raw = liq.get("abonos_comprador_pesos")

    tipo_comision = (man.get("tipo_comision") or "").strip()
    comision_macal_raw = man.get("comision_macal")
    paga_premio = bool(man.get("paga_premio"))
    tramos_premio = man.get("tramos_premio") or []
    condicion_premio = man.get("condicion_premio")
    tipo_propiedad_liq = (liq.get("tipo_propiedad") or "").strip().lower()
    precio_proyectado_uf = liq.get("precio_proyectado_uf")

    paga_publicidad = bool(man.get("paga_publicidad"))
    monto_publicidad_raw = man.get("monto_publicidad_pesos")

    vale_vista_var = man.get("vale_vista_var")
    costo_vale_vista = _int_or_none(man.get("costo_vale_vista"))
    monto_vale_vista = _int_or_none(man.get("monto_vale_vista"))
    instrucciones_var = man.get("instrucciones_var")
    costo_instrucciones = _int_or_none(man.get("costo_instrucciones"))
    descuenta_gastos = man.get("descuenta_gastos")
    antecedentes_var = man.get("antecedentes_var")
    costo_antecedentes = _int_or_none(man.get("costo_antecedentes"))

    adj_pesos = _int_or_none(valor_adjudicacion_pesos_raw)
    adj_uf = valor_adjudicacion_uf_raw
    uf_valor = uf_dia_subasta_raw
    abonos = _int_or_none(abonos_raw)

    com_val = _float_or_none(comision_macal_raw)
    publicidad = _int_or_none(monto_publicidad_raw) if paga_publicidad else 0

    adj_uf_en_pesos = _round0(adj_uf * uf_valor) if (adj_uf is not None and uf_valor is not None) else None

    # El valor en pesos extraído directamente de la liquidación (adj_pesos) es un campo
    # ambiguo: en el formato "SALDO - PRECIO" no siempre existe una columna en pesos para
    # la adjudicación, y la IA puede confundirlo con el total abonado por el comprador
    # (que suele ser un valor muy cercano, ya que el saldo de precio termina en 0).
    # Por eso, cuando es posible calcular adj_uf_en_pesos (UF adjudicada × valor UF del
    # día), este se usa SIEMPRE como fuente de verdad, y el valor extraído solo sirve
    # como chequeo cruzado para alertar si discrepa.
    if adj_pesos and adj_uf_en_pesos:
        diff_pct = abs(adj_pesos - adj_uf_en_pesos) / adj_pesos
        if abonos is not None and abs(adj_pesos - abonos) / adj_pesos < 0.02:
            alertas.append(
                f"valor_adjudicacion_pesos extraído (${adj_pesos:,}) coincide casi exactamente con "
                f"abonos_comprador_pesos (${abonos:,}); probablemente la extracción confundió el total "
                f"abonado con el valor de adjudicación. Se usó valor_adjudicacion_uf × uf_dia_subasta "
                f"(${adj_uf_en_pesos:,}) como base — verificar manualmente."
            )
        elif diff_pct > 0.005:
            alertas.append(
                f"Diferencia de {diff_pct:.1%} entre valor_adjudicacion_pesos extraído (${adj_pesos:,}) "
                f"y el cálculo UF×valor UF (${adj_uf_en_pesos:,}). Se usó el cálculo UF×valor UF como base "
                "— verificar manualmente."
            )
        adj_pesos = adj_uf_en_pesos
    elif adj_pesos is None and adj_uf_en_pesos is not None:
        adj_pesos = adj_uf_en_pesos
        alertas.append(
            "valor_adjudicacion_pesos no estaba en la liquidación; "
            "se usó valor_adjudicacion_uf × uf_dia_subasta como base."
        )

    base_com = adj_pesos if base_comision == "adjudicacion_pesos" else adj_uf_en_pesos

    if tipo_comision == "Porcentaje" and base_com is not None and com_val is not None:
        comision = _round0(base_com * (com_val / 100))
    elif tipo_comision == "Pesos":
        comision = int(com_val)
    else:
        comision = None
        alertas.append("tipo_comision no reconocido o datos insuficientes.")

    iva_com = _apply_iva(comision, iva_rate, iva_comision)

    premio = 0
    tramo_aplicado = None
    if paga_premio and tramos_premio:
        if adj_uf is not None and uf_valor is not None:

            def _base_uf_efectiva(t):
                base_uf = t.get("base_uf") or 0.0
                base_ps = t.get("base_pesos")
                if base_uf == 0.0 and base_ps and base_ps > 0 and uf_valor > 0:
                    return base_ps / uf_valor
                return base_uf

            candidatos = [
                t for t in tramos_premio
                if t.get("tipo_propiedad") is None
                or (tipo_propiedad_liq and t["tipo_propiedad"].lower() == tipo_propiedad_liq)
            ]
            if not candidatos:
                candidatos = tramos_premio

            candidatos_alcanzados = [t for t in candidatos if adj_uf >= _base_uf_efectiva(t)]
            if candidatos_alcanzados:
                max_base = max(_base_uf_efectiva(t) for t in candidatos_alcanzados)
                empate = [t for t in candidatos_alcanzados if _base_uf_efectiva(t) == max_base]

                if len(empate) == 1:
                    tramo_aplicado = empate[0]
                else:
                    cumple = None
                    if precio_proyectado_uf is not None and adj_uf is not None:
                        cumple = adj_uf >= precio_proyectado_uf
                    if cumple is True:
                        pref = [t for t in empate if any(w in t.get("condicion", "").lower() for w in ("proyectado", "cumple", "supera"))]
                        tramo_aplicado = pref[0] if pref else empate[-1]
                    elif cumple is False:
                        pref = [t for t in empate if not any(w in t.get("condicion", "").lower() for w in ("proyectado", "cumple", "supera"))]
                        tramo_aplicado = pref[0] if pref else empate[0]
                    else:
                        tramo_aplicado = min(empate, key=lambda t: t.get("porcentaje", 0.0))
                        alertas.append(
                            f"Hay {len(empate)} tramos con la misma base para '{tipo_propiedad_liq}' "
                            "y no se encontró precio proyectado. Se aplicó el porcentaje menor. Verificar manualmente."
                        )

                base_uf_tramo = _base_uf_efectiva(tramo_aplicado)
                pct_tramo = tramo_aplicado["porcentaje"]
                diferencial_uf = max(0.0, adj_uf - base_uf_tramo)
                diferencial_clp = _round0(diferencial_uf * uf_valor)
                premio = _round0(diferencial_clp * (pct_tramo / 100.0))
                tramo_aplicado = dict(tramo_aplicado)
                tramo_aplicado["base_uf_efectiva"] = base_uf_tramo
            else:
                alertas.append(
                    f"Adjudicación ({adj_uf} UF) no alcanza ningún umbral de premio "
                    f"para tipo '{tipo_propiedad_liq or 'no determinado'}'."
                )
        else:
            alertas.append("No se pudo calcular premio: faltan adj_uf o uf_valor.")
    elif paga_premio and not tramos_premio:
        alertas.append("paga_premio=True pero no se extrajeron tramos_premio del mandato.")

    iva_pre = _apply_iva(premio, iva_rate, iva_premio)
    iva_pub = _apply_iva(publicidad, iva_rate, iva_publicidad)

    gastos_calculados = {
        "comision": comision or 0,
        "iva_comision": iva_com or 0,
        "premio": premio or 0,
        "iva_premio": iva_pre or 0,
        "publicidad": publicidad or 0,
        "iva_publicidad": iva_pub or 0,
        "costo_vale_vista": costo_vale_vista or 0,
        "costo_instrucciones": costo_instrucciones or 0,
        "costo_antecedentes": costo_antecedentes or 0,
    }
    total_gastos_calculados = sum(gastos_calculados.values())

    if descuenta_gastos == "No":
        deducciones = 0
    elif descuenta_gastos == "Sí":
        deducciones = total_gastos_calculados
    else:
        alertas.append("Debe seleccionar si se descuentan o no los gastos de la liquidación")
        deducciones = total_gastos_calculados

    if vale_vista_var == "No":
        teorico_vendedor = (abonos - deducciones) if (abonos is not None and adj_pesos is not None) else None
    elif vale_vista_var == "Sí":
        if not monto_vale_vista or monto_vale_vista <= 0:
            alertas.append("Forma de pago 'Incluye Vale Vista' sin 'monto_vale_vista' válido.")
        teorico_vendedor = (abonos - monto_vale_vista - deducciones) if (abonos is not None and adj_pesos is not None) else None
    else:
        alertas.append("Debe seleccionar si la forma de pago incluye Vale Vista")
        teorico_vendedor = (abonos - deducciones) if (abonos is not None and adj_pesos is not None) else None

    if abonos is not None and teorico_vendedor is not None:
        saldo_por_pagar = max(0, min(abonos, teorico_vendedor))
    else:
        saldo_por_pagar = None
        alertas.append("No se pudo calcular saldo por pagar: faltan abonos o liquidación teórica.")

    return {
        "identificacion": {
            "cliente_vendedor": cliente_vendedor,
            "mandante": man.get("mandante"),
            "representante_legal": man.get("representante_legal"),
            "fecha_subasta": liq.get("fecha_subasta"),
            "numero_lote": liq.get("numero_lote"),
            "propiedad": liq.get("propiedad"),
            "comuna": liq.get("comuna"),
            "fecha_firma_mandato": man.get("fecha_firma_mandato"),
        },
        "insumos": {
            "adjudicacion_pesos": adj_pesos,
            "adjudicacion_uf": adj_uf,
            "uf_dia_subasta": uf_valor,
            "adjudicacion_uf_en_pesos": adj_uf_en_pesos,
            "precio_proyectado_uf": precio_proyectado_uf,
            "abonos_comprador_pesos": abonos,
        },
        "parametros": {
            "tipo_comision": tipo_comision,
            "base_comision_usada": base_comision,
            "paga_premio": paga_premio,
            "tramos_premio": tramos_premio,
            "tramo_aplicado": tramo_aplicado,
            "tipo_propiedad": tipo_propiedad_liq or None,
            "condicion_premio": condicion_premio,
            "paga_publicidad": paga_publicidad,
            "monto_publicidad_pesos": publicidad,
            "iva_rate": iva_rate,
            "iva_comision": iva_comision,
            "iva_premio": iva_premio,
            "iva_publicidad": iva_publicidad,
        },
        "calculo": {
            "comision": comision,
            "comision_macal": comision_macal_raw,
            "iva_comision": iva_com,
            "premio": premio,
            "iva_premio": iva_pre,
            "publicidad": publicidad,
            "iva_publicidad": iva_pub,
            "vale_vista_var": vale_vista_var,
            "costo_vale_vista": costo_vale_vista,
            "monto_vale_vista": monto_vale_vista,
            "instrucciones_var": instrucciones_var,
            "costo_instrucciones": costo_instrucciones,
            "descuenta_gastos": descuenta_gastos,
            "antecedentes_var": antecedentes_var,
            "costo_antecedentes": costo_antecedentes,
            "deducciones_totales": deducciones,
            "total_gastos": total_gastos_calculados,
            "liquidacion_vendedor_teorica": teorico_vendedor,
            "saldo_por_pagar_al_vendedor": saldo_por_pagar,
        },
        "alertas": alertas,
    }
