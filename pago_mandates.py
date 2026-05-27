import json, base64, re, os
from pathlib import Path
from anthropic import Anthropic
from decimal import Decimal, ROUND_HALF_UP
from pprint import pprint

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configuración
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL1 = "claude-opus-4-1-20250805"
MODEL2 = "claude-sonnet-4-6"

client = Anthropic(api_key=API_KEY)

def cargar_pdf_base64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")
    
def extract_json_mandato_from_pdf(pdf_path: Path) -> dict:
    encoded_pdf = cargar_pdf_base64(pdf_path)

    system_prompt = (
        "Eres un extractor de datos legal. Devuelve SOLO JSON minificado (una línea), con las claves exactas:\n"
        '["comision_macal","tipo_comision","condicion_premio","paga_premio","tramos_premio","fecha_firma_mandato","mandante",'
        '"representante_legal","paga_publicidad","monto_publicidad_pesos"]. '
        "Reglas:\n"
        "- comision_macal: porcentaje o monto en pesos que cobra Macal por la venta. "
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
        "  * base_pesos: umbral mínimo en PESOS CHILENOS. Usar si el umbral está expresado en pesos (ej: '$6.000.000', '6 millones de pesos'). "
        "    Si el umbral ya está en UF (campo base_uf), usar null aquí. Si el tramo aplica desde 0 sin umbral, usar null.\n"
        "  * porcentaje: porcentaje del diferencial (monto adjudicado - umbral base) que se paga como premio. Número decimal (ej: 2.5).\n"
        "  * condicion: texto literal del mandato que describe la condición de este tramo, incluyendo si hay IVA, si depende de proyectado, etc.\n"
        "  IMPORTANTE: si el mandato define distintos umbrales para el mismo tipo de propiedad (ej: 1% hasta X, 2.5% sobre X, 15% sobre Y), "
        "  crea UN tramo por cada umbral. NO simplifiques ni promedies. Extrae cada tramo exactamente como está escrito.\n"
        "- 'condicion_premio': texto completo y literal de la sección PREMIO del mandato, sin omitir nada.\n"
        "- representante_legal: En caso que no se mencione ningun representante legal, usa null.\n"
        "- Formato de fecha: dd-mm-yyyy. Si no existe, usa null.\n"
        "- Los montos en pesos deben ser enteros sin separadores (ej: 6000000). Si no aplica o no es determinable, usa null.\n"
        "- Debes determinar si la publicidad la paga el mandante o la mandataria. En caso que la publicidad la pague el mandante paga_publicidad debe ser true, y en caso que la publicidad la pague la mandataria paga_publicidad debe ser false. Si no existe una clausula de publicidad, paga_publicidad es false.\n"
        "- Si el documento establece que el mandante paga publicidad, devuelve true y el monto fijado; si dice 'por lote' o similar, devuelve el monto unitario y la condición queda en el texto de premio, no agregues campos extras.\n"
        "- monto_publicidad_pesos debe ser 0 si paga_publicidad es false.\n"
        "- No inventes datos. Si falta información, usa null.\n"
        "Responde ÚNICAMENTE con el JSON solicitado, sin texto adicional."
    )

    user_instruction = "Extrae los campos requeridos del siguiente PDF con el mandato notarial escaneado. Devuelve solo JSON."

    response = client.messages.create(
        model=MODEL1,
        max_tokens=1500,
        temperature=0,
        system=system_prompt,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": user_instruction},
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": encoded_pdf
                    }
                }
            ]
        }]
    )

    content_blocks = response.content
    if not content_blocks or content_blocks[0].type != "text":
        raise RuntimeError("Respuesta inesperada del modelo.")

    raw_json = _limpiar_json(content_blocks[0].text)
    data = json.loads(raw_json)

    print(data)

    # Coerciones de tipo suaves
    def to_int_or_null(v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return int(v)
        s = str(v).strip().replace(".", "").replace(",", "")
        return int(s) if s.isdigit() else None

    data["comision_macal"] = _float_or_none(data.get("comision_macal"))
    data["monto_publicidad_pesos"] = to_int_or_null(data.get("monto_publicidad_pesos"))

    # Normalizar tramos_premio
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

    tramos_limpios = []
    for t in tramos_raw:
        if not isinstance(t, dict):
            continue
        tramos_limpios.append({
            "tipo_propiedad": t.get("tipo_propiedad"),
            "base_uf": _float_or_none(t.get("base_uf")) or 0.0,
            "base_pesos": _to_int_pesos(t.get("base_pesos")),
            "porcentaje": _float_or_none(t.get("porcentaje")) or 0.0,
            "condicion": str(t.get("condicion") or ""),
        })
    data["tramos_premio"] = tramos_limpios

    if isinstance(data.get("paga_publicidad"), str):
        data["paga_publicidad"] = data["paga_publicidad"].strip().lower() in ("true", "sí", "si", "yes")

    # #region agent log
    import time as _tm, json as _jm
    with open("/Users/jgonzalez/Downloads/App-Liquidación-pago-mandantes/.cursor/debug-a05699.log", "a") as _lf:
        _lf.write(_jm.dumps({"sessionId":"a05699","hypothesisId":"C","location":"pago_mandates.py:mandato_extraido","message":"mandato_json_completo","data":data,"timestamp":int(_tm.time()*1000)}) + "\n")
    # #endregion

    return data

# ========== Utiles ==========
def _limpiar_json(raw: str) -> str:
    """Elimina bloques markdown ```json ... ``` que algunos modelos agregan."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        # quitar primera y última línea si son fence de markdown
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    return raw

def construir_mensaje_liquidacion(encoded_pdf: str):
    """
    Pedimos a Claude devolver SOLO JSON minificado con las claves requeridas.
    Reglas explícitas para que use la primera fila/valor correcto en cada columna/etiqueta.
    """
    system_prompt = (
        "Eres un extractor de datos contables. Devuelve SOLO JSON minificado (una línea) "
        "con EXACTAMENTE estas claves en español:\n"
        '["cliente_vendedor","numero_lote","propiedad","comuna","tipo_propiedad","valor_adjudicacion_pesos","valor_adjudicacion_uf",'
        '"precio_proyectado_uf","fecha_subasta","uf_dia_subasta","abonos_comprador_pesos"].\n'
        "Instrucciones del documento 'Liquidación de Pago':\n"
        "- cliente_vendedor: texto del título principal que aparece justo ARRIBA de la frase 'Liquidación de Pago'. "
        "  No es el adjudicatario/comprador; es el vendedor/mandante de la propiedad.\n"
        "- numero_lote: aparece junto a la palabra 'Lote' en la parte superior del documento. Devuelvelo como entero sin separadores.\n"
        "- propiedad: es el texto que aparece en la fila/etiqueta 'Propiedad'. Devuelve exactamente el texto de esa fila/etiqueta sin agregar nada, solo el texto exacto. Si no existe, usa null.\n"
        "- comuna: es el texto que aparece en la fila/etiqueta 'Comuna'. Devuelve exactamente el texto de esa fila/etiqueta sin agregar nada, solo el texto exacto. Si no existe, usa null.\n"
        "- tipo_propiedad: clasifica la propiedad según el campo 'Propiedad' o cualquier descripción del documento. "
        "  Devuelve EXACTAMENTE una de estas palabras (en minúsculas): 'departamento', 'estacionamiento', 'bodega', 'casa', 'terreno', 'local', 'oficina', 'otro'. "
        "  Si no es posible determinarlo, devuelve null.\n"
        "- valor_adjudicacion_pesos: la PRIMERA línea (primer ítem) de la columna 'CARGO'. Devuelve como entero sin separadores (ej: 1234567). Si la columna está vacía o no existe, devuelve null.\n"
        "- valor_adjudicacion_uf: la PRIMERA línea (primer ítem) de la columna 'CARGO UF'. Devuelve número con punto decimal (ej: 123.45).\n"
        "- precio_proyectado_uf: precio proyectado o mínimo de la propiedad en UF. Puede aparecer como 'Precio proyectado', 'Mínimo', 'Base', 'Proyectado' o similar. Devuelve número con punto decimal. Si no existe, devuelve null.\n"
        "- fecha_subasta: la fecha que aparece en la fila/etiqueta 'Remate efectuado en', devuelve la fecha en formato dd-mm-yyyy.\n"
        "- uf_dia_subasta: la PRIMERA fila de la columna 'VALOR UF'. Devuelve número con punto decimal.\n"
        "- abonos_comprador_pesos: valor de la fila 'ABONADO EN PESOS'. Devuelve entero sin separadores.\n"
        "Reglas generales:\n"
        "- Si un dato no existe o no es claramente identificable, devuelve null.\n"
        "- No incluyas texto adicional, comentarios, ni campos extra. SOLO el JSON minificado pedido."
    )
    user_instruction = (
        "Lee el PDF adjunto ('Liquidación de Pago') con tablas y títulos. Extrae únicamente los campos indicados, "
        "respetando las reglas y retornando SOLO JSON minificado en una línea."
    )
    return [
        {"type": "text", "text": user_instruction},
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": encoded_pdf
            }
        }
    ], system_prompt

def parse_int_or_null(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip()
    s = s.replace("$", "").replace("CLP", "").replace("UF", "")
    s = s.replace(".", "").replace(",", "")  # quita separadores comunes
    return int(s) if re.fullmatch(r"\d+", s) else None

def parse_float_or_null(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("UF", "").replace("$", "")
    # normaliza decimal (coma->punto) y quita separadores de miles
    s = s.replace(".", "").replace(" ", "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return None

# ========== Extracción ==========
def extraer_json_liquidacion(pdf_path: Path) -> dict:
    if not API_KEY:
        raise RuntimeError("Falta ANTHROPIC_API_KEY en el entorno.")
    client = Anthropic(api_key=API_KEY)

    encoded = cargar_pdf_base64(pdf_path)
    content, system_prompt = construir_mensaje_liquidacion(encoded)

    resp = client.messages.create(
        model=MODEL2,
        max_tokens=800,
        temperature=0,
        system=system_prompt,
        messages=[{"role": "user", "content": content}],
    )

    if not resp.content or resp.content[0].type != "text":
        raise RuntimeError("Respuesta inesperada del modelo de Anthropic.")
    raw = _limpiar_json(resp.content[0].text)

    # Asegura JSON válido
    data = json.loads(raw)

    # Coerciones de tipo y normalizaciones
    data["valor_adjudicacion_pesos"] = parse_int_or_null(data.get("valor_adjudicacion_pesos"))
    data["abonos_comprador_pesos"] = parse_int_or_null(data.get("abonos_comprador_pesos"))
    data["valor_adjudicacion_uf"] = parse_float_or_null(data.get("valor_adjudicacion_uf"))
    data["uf_dia_subasta"] = parse_float_or_null(data.get("uf_dia_subasta"))
    data["precio_proyectado_uf"] = parse_float_or_null(data.get("precio_proyectado_uf"))
    # tipo_propiedad: normalizar a minúsculas, validar vocabulario
    _tipos_validos = {"departamento","estacionamiento","bodega","casa","terreno","local","oficina","otro"}
    tp = (data.get("tipo_propiedad") or "").strip().lower()
    data["tipo_propiedad"] = tp if tp in _tipos_validos else None

    print(data)

    return data

# ========== Main ==========
def _round0(x): return int(Decimal(str(x)).quantize(0, rounding=ROUND_HALF_UP))

def _int_or_none(v):
    try:
        if v is None: return None
        return int(str(v).replace(".", "").replace(",", "").strip())
    except: return None

def _float_or_none(v):
    try:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)

        s = str(v).strip().replace(" ", "")

        # Normaliza separadores
        if "," in s and "." in s:
            # caso raro: "1.234,56" (miles + decimales)
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            # caso: "1,5" → "1.5"
            s = s.replace(",", ".")
        # si solo hay "." queda como decimal válido

        return float(s)
    except:
        return None

def _apply_iva(amount, iva_rate, apply): return 0 if (not apply or amount is None) else _round0(amount * iva_rate)

def liquidar_pago(liq: dict, man: dict, *, iva_rate=0.19, iva_comision=True, iva_premio=True, iva_publicidad=True, base_comision="adjudicacion_pesos"):
    alertas = []

    # ===== 1) EXTRACCIÓN A VARIABLES =====
    cliente_vendedor = liq.get("cliente_vendedor")
    valor_adjudicacion_pesos_raw = liq.get("valor_adjudicacion_pesos")
    valor_adjudicacion_uf_raw   = liq.get("valor_adjudicacion_uf")
    uf_dia_subasta_raw          = liq.get("uf_dia_subasta")
    abonos_raw                  = liq.get("abonos_comprador_pesos")

    tipo_comision = (man.get("tipo_comision") or "").strip()
    comision_macal_raw = man.get("comision_macal")
    paga_premio = bool(man.get("paga_premio"))
    tramos_premio = man.get("tramos_premio") or []
    condicion_premio = man.get("condicion_premio")
    tipo_propiedad_liq = (liq.get("tipo_propiedad") or "").strip().lower()
    precio_proyectado_uf = liq.get("precio_proyectado_uf")  # extraído de la liquidación

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

    # ===== 2) NORMALIZACIÓN / TIPOS =====
    adj_pesos   = _int_or_none(valor_adjudicacion_pesos_raw)
    adj_uf      = valor_adjudicacion_uf_raw
    uf_valor    = uf_dia_subasta_raw
    abonos      = _int_or_none(abonos_raw)

    com_val    = _float_or_none(comision_macal_raw)
    publicidad = _int_or_none(monto_publicidad_raw) if paga_publicidad else 0

    adj_uf_en_pesos = _round0(adj_uf * uf_valor) if (adj_uf is not None and uf_valor is not None) else None
    # #region agent log
    import time as _t2, json as _json2
    with open("/Users/jgonzalez/Downloads/App-Liquidación-pago-mandantes/.cursor/debug-a05699.log", "a") as _lf2:
        _lf2.write(_json2.dumps({"sessionId":"a05699","hypothesisId":"B","location":"pago_mandates.py:normalizacion","message":"valores_adjudicacion","data":{"adj_pesos_raw":valor_adjudicacion_pesos_raw,"adj_pesos":adj_pesos,"adj_uf":adj_uf,"uf_valor":uf_valor,"adj_uf_en_pesos":adj_uf_en_pesos,"tramos_premio":tramos_premio,"paga_premio":paga_premio},"timestamp":int(_t2.time()*1000)}) + "\n")
    # #endregion
    if adj_pesos and adj_uf_en_pesos:
        if abs(adj_pesos - adj_uf_en_pesos) / adj_pesos > 0.01:
            alertas.append("Diferencia >1% entre adjudicación CLP y UF*valor UF.")

    if adj_pesos is None and adj_uf_en_pesos is not None:
        adj_pesos = adj_uf_en_pesos
        alertas.append(
            "valor_adjudicacion_pesos no estaba en la liquidación; "
            "se usó valor_adjudicacion_uf × uf_dia_subasta como base."
        )

    base_com = adj_pesos if base_comision == "adjudicacion_pesos" else adj_uf_en_pesos

    # ===== 3) CÁLCULOS =====
    # Comisión
    if tipo_comision == "Porcentaje" and base_com is not None and com_val is not None:
        comision = _round0(base_com * (com_val / 100))
    elif tipo_comision == "Pesos":
        comision = int(com_val)
    else:
        comision = None
        alertas.append("tipo_comision no reconocido o datos insuficientes.")

    iva_com = _apply_iva(comision, iva_rate, iva_comision)

    # Premio — selección del tramo correcto por tipo_propiedad y adj_uf
    premio = 0
    tramo_aplicado = None
    if paga_premio and tramos_premio:
        if adj_uf is not None and uf_valor is not None:

            def _base_uf_efectiva(t):
                """Devuelve el umbral en UF del tramo, convirtiendo base_pesos si es necesario."""
                base_uf = t.get("base_uf") or 0.0
                base_ps = t.get("base_pesos")
                if base_uf == 0.0 and base_ps and base_ps > 0 and uf_valor > 0:
                    return base_ps / uf_valor
                return base_uf

            # 1. Filtrar tramos que aplican a este tipo de propiedad
            #    Un tramo con tipo_propiedad=null aplica a todos.
            candidatos = [
                t for t in tramos_premio
                if t.get("tipo_propiedad") is None
                or (tipo_propiedad_liq and t["tipo_propiedad"].lower() == tipo_propiedad_liq)
            ]
            if not candidatos:
                # Si ningún tramo coincide por tipo, usar todos (mandato sin distinción de tipo)
                candidatos = tramos_premio

            # 2. Elegir el tramo de mayor base efectiva (UF o pesos→UF) que la adjudicación supera
            candidatos_alcanzados = [t for t in candidatos if adj_uf >= _base_uf_efectiva(t)]
            if candidatos_alcanzados:
                max_base = max(_base_uf_efectiva(t) for t in candidatos_alcanzados)
                empate = [t for t in candidatos_alcanzados if _base_uf_efectiva(t) == max_base]

                if len(empate) == 1:
                    tramo_aplicado = empate[0]
                else:
                    # Desempate por precio proyectado extraído de la liquidación
                    cumple = None
                    if precio_proyectado_uf is not None and adj_uf is not None:
                        cumple = adj_uf >= precio_proyectado_uf

                    if cumple is True:
                        pref = [t for t in empate if any(w in t.get("condicion","").lower() for w in ("proyectado","cumple","supera"))]
                        tramo_aplicado = pref[0] if pref else empate[-1]
                    elif cumple is False:
                        pref = [t for t in empate if not any(w in t.get("condicion","").lower() for w in ("proyectado","cumple","supera"))]
                        tramo_aplicado = pref[0] if pref else empate[0]
                    else:
                        # precio_proyectado_uf no disponible: tomar el de menor porcentaje y alertar
                        tramo_aplicado = min(empate, key=lambda t: t.get("porcentaje", 0.0))
                        alertas.append(
                            f"Hay {len(empate)} tramos con la misma base para '{tipo_propiedad_liq}' "
                            "y no se encontró precio proyectado en la liquidación. "
                            "Se aplicó el porcentaje menor. Verificar manualmente."
                        )

                base_uf_tramo = _base_uf_efectiva(tramo_aplicado)
                pct_tramo = tramo_aplicado["porcentaje"]
                diferencial_uf  = max(0.0, adj_uf - base_uf_tramo)
                diferencial_clp = _round0(diferencial_uf * uf_valor)
                premio = _round0(diferencial_clp * (pct_tramo / 100.0))
                # Guardar la base efectiva en UF para mostrarlo correctamente en el PDF
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

    # #region agent log
    import time as _t
    _log_path = "/Users/jgonzalez/Downloads/App-Liquidación-pago-mandantes/.cursor/debug-a05699.log"
    import json as _json
    with open(_log_path, "a") as _lf:
        _lf.write(_json.dumps({"sessionId":"a05699","hypothesisId":"A","location":"pago_mandates.py:premio","message":"calculo_premio_tramos","data":{"tipo_propiedad_liq":tipo_propiedad_liq,"adj_uf":adj_uf,"precio_proyectado_uf":precio_proyectado_uf,"tramos_premio":tramos_premio,"tramo_aplicado":tramo_aplicado,"premio":premio},"timestamp":int(_t.time()*1000)}) + "\n")
    # #endregion

    iva_pre = _apply_iva(premio, iva_rate, iva_premio)

    # Publicidad
    iva_pub = _apply_iva(publicidad, iva_rate, iva_publicidad)

    # Trazabilidad gastos calculados
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

    # ======== APLICACION DE DESCUENTO DE GASTOS SEGUN OPCION SELECCIONADA ========
    if descuenta_gastos == "No":
        # No se descuentan gastos en liquidación, quedan por cobrar a mandante
        deducciones = 0
    elif descuenta_gastos == "Sí":
        deducciones = total_gastos_calculados
    else:
        alertas.append("Debe seleccionar si se descuentan o no los gastos de la liquidación")
        deducciones = total_gastos_calculados

    # ======== PAGO AL MANDANTE COMPLETO O SEPARADO ==========
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

    # ===== 4) SALIDA ESTRUCTURADA =====
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