import io
from pathlib import Path
from datetime import datetime

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, HRFlowable
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

# Paths relative to this file — fonts y logo están en backend/app/
_HERE = Path(__file__).parent.parent

pdfmetrics.registerFont(TTFont("Montserrat", str(_HERE / "fonts" / "Montserrat-Regular.ttf")))
pdfmetrics.registerFont(TTFont("Montserrat-Bold", str(_HERE / "fonts" / "Montserrat-Bold.ttf")))
registerFontFamily("Montserrat", normal="Montserrat", bold="Montserrat-Bold")

# Brand palette
ORANGE = colors.HexColor("#FF6600")
ORANGE_LIGHT = colors.HexColor("#FFEFE5")
PURPLE = colors.HexColor("#554FF1")
PURPLE_LIGHT = colors.HexColor("#EEEDFE")
GRAY_DARK = colors.HexColor("#1A1A1A")
GRAY_MID = colors.HexColor("#666666")
GRAY_LIGHT = colors.HexColor("#E6E6E6")
WHITE = colors.white


def _fmt_clp(v) -> str:
    if v is None:
        return "$0"
    return f"${int(v):,}".replace(",", ".")


def generar_pdf_bytes(resultado: dict) -> bytes:
    """Genera el PDF y devuelve los bytes. No escribe a disco."""
    buf = io.BytesIO()
    _build(resultado, buf)
    return buf.getvalue()


def generar_pdf(resultado: dict, output_path: str = "liquidacion_mandante.pdf"):
    """Genera el PDF y lo escribe en output_path (compatibilidad con main.py Tkinter)."""
    with open(output_path, "wb") as f:
        f.write(generar_pdf_bytes(resultado))


def _build(resultado: dict, dest):
    doc = SimpleDocTemplate(
        dest,
        pagesize=letter,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    S = {
        "normal": ParagraphStyle("n", fontName="Montserrat", fontSize=9, textColor=GRAY_DARK, leading=13),
        "small": ParagraphStyle("sm", fontName="Montserrat", fontSize=7.5, textColor=GRAY_DARK, leading=11),
        "small_gray": ParagraphStyle("smg", fontName="Montserrat", fontSize=7, textColor=GRAY_MID, leading=10),
        "bold": ParagraphStyle("b", fontName="Montserrat-Bold", fontSize=9, textColor=GRAY_DARK, leading=13),
        "title": ParagraphStyle("t", fontName="Montserrat-Bold", fontSize=14, textColor=GRAY_DARK, leading=18),
        "section": ParagraphStyle("sec", fontName="Montserrat-Bold", fontSize=8, textColor=ORANGE, leading=12, spaceAfter=2),
        "th_white": ParagraphStyle("thw", fontName="Montserrat-Bold", fontSize=8, textColor=WHITE, alignment=1, leading=11),
        "cell": ParagraphStyle("cell", fontName="Montserrat", fontSize=8, textColor=GRAY_DARK, alignment=1, leading=11),
        "cell_bold": ParagraphStyle("cellb", fontName="Montserrat-Bold", fontSize=8, textColor=GRAY_DARK, alignment=1, leading=11),
        "right": ParagraphStyle("right", fontName="Montserrat", fontSize=8, textColor=GRAY_DARK, alignment=2, leading=11),
        "right_bold": ParagraphStyle("rightb", fontName="Montserrat-Bold", fontSize=8, textColor=GRAY_DARK, alignment=2, leading=11),
        "date": ParagraphStyle("date", fontName="Montserrat", fontSize=8, textColor=GRAY_MID, alignment=2, leading=11),
        "total_label": ParagraphStyle("tl", fontName="Montserrat-Bold", fontSize=9, textColor=ORANGE, leading=13),
        "total_value": ParagraphStyle("tv", fontName="Montserrat-Bold", fontSize=11, textColor=ORANGE, alignment=2, leading=15),
    }

    calculo = resultado.get("calculo", {})
    ident = resultado.get("identificacion", {})
    insum = resultado.get("insumos", {})
    param = resultado.get("parametros", {})

    meses = {1:"enero",2:"febrero",3:"marzo",4:"abril",5:"mayo",6:"junio",
             7:"julio",8:"agosto",9:"septiembre",10:"octubre",11:"noviembre",12:"diciembre"}
    hoy = datetime.now()
    fecha_hoy = f"Santiago, {hoy.day} de {meses[hoy.month]} de {hoy.year}"

    elements = []

    # ── Header: logo + fecha ──────────────────────────────────────────────────
    logo_path = str(_HERE / "logo" / "logo_macal_horizontal.png")
    logo = Image(logo_path)
    ratio = logo.imageHeight / float(logo.imageWidth)
    logo.drawWidth = 6 * cm
    logo.drawHeight = logo.drawWidth * ratio

    header_table = Table(
        [[logo, Paragraph(fecha_hoy, S["date"])]],
        colWidths=[9 * cm, 9 * cm],
    )
    header_table.setStyle([
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ])
    elements.append(header_table)
    elements.append(HRFlowable(width="100%", thickness=2, color=ORANGE, spaceAfter=10))

    # ── Título ────────────────────────────────────────────────────────────────
    elements.append(Paragraph("Liquidación de Pago", S["title"]))
    elements.append(Spacer(1, 6))

    rep_legal = ident.get("representante_legal")
    mandante = ident.get("mandante", "")
    destinatario = f"<b>Señor/a</b> {rep_legal}, {mandante}" if rep_legal else f"Señor/a {mandante}"
    elements.append(Paragraph(destinatario, S["normal"]))
    elements.append(Spacer(1, 8))

    fecha_subasta_str = ident.get("fecha_subasta") or ""
    try:
        fsd = datetime.strptime(fecha_subasta_str, "%d-%m-%Y")
        fecha_subasta_texto = f"{fsd.day} de {meses[fsd.month]} de {fsd.year}"
    except Exception:
        fecha_subasta_texto = fecha_subasta_str

    elements.append(Paragraph(
        f"<b>Referencias:</b> Lote {ident.get('numero_lote')} — Subasta {fecha_subasta_texto} — "
        f"{ident.get('propiedad')}, {ident.get('comuna')}",
        S["normal"],
    ))
    elements.append(Spacer(1, 8))

    fecha_mandato_str = ident.get("fecha_firma_mandato") or ""
    try:
        fmd = datetime.strptime(fecha_mandato_str, "%d-%m-%Y")
        fecha_mandato_texto = f"{fmd.day} de {meses[fmd.month]} de {fmd.year}"
    except Exception:
        fecha_mandato_texto = fecha_mandato_str

    elements.append(Paragraph(
        f"De acuerdo a lo convenido en mandato firmado con fecha {fecha_mandato_texto} suscrito entre "
        f"<b>{mandante}</b> y Macal, se detalla liquidación de las propiedades referidas a continuación:",
        S["normal"],
    ))
    elements.append(Spacer(1, 14))

    # ── Tabla propiedad ───────────────────────────────────────────────────────
    adj_pesos = insum.get("adjudicacion_pesos")
    abonos = insum.get("abonos_comprador_pesos")

    prop_table = Table(
        [
            [
                Paragraph("Lote", S["th_white"]),
                Paragraph("Dirección", S["th_white"]),
                Paragraph("Comuna", S["th_white"]),
                Paragraph("Valor Adjudicado", S["th_white"]),
                Paragraph("Valor Pagado Comprador", S["th_white"]),
            ],
            [
                Paragraph(str(ident.get("numero_lote", "")), S["cell"]),
                Paragraph(str(ident.get("propiedad", "")), S["cell"]),
                Paragraph(str(ident.get("comuna", "")), S["cell"]),
                Paragraph(_fmt_clp(adj_pesos), S["cell"]),
                Paragraph(_fmt_clp(abonos), S["cell_bold"]),
            ],
        ],
        colWidths=[1.5 * cm, 6 * cm, 3.5 * cm, 3 * cm, 4 * cm],
    )
    prop_table.setStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ORANGE),
        ("BACKGROUND", (0, 1), (-1, 1), GRAY_LIGHT),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("BOX", (0, 0), (-1, -1), 1, ORANGE),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [GRAY_LIGHT, WHITE]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ])
    elements.append(prop_table)
    elements.append(Spacer(1, 18))

    # ── Detalle liquidación ───────────────────────────────────────────────────
    elements.append(Paragraph("Detalle de montos de Liquidación de Pago", S["bold"]))
    elements.append(Spacer(1, 8))

    # Etiqueta comisión
    comision_macal_val = calculo.get("comision_macal")
    if param.get("tipo_comision") == "Porcentaje" and comision_macal_val is not None:
        etiqueta_comision = f"Comisión Macal ({comision_macal_val:g}%)"
    else:
        etiqueta_comision = "Comisión Macal"

    # Etiqueta premio
    tramo = param.get("tramo_aplicado")
    if tramo:
        base_uf_mostrar = tramo.get("base_uf_efectiva") or tramo.get("base_uf") or 0.0
        etiqueta_premio = f"Premio Macal ({tramo.get('porcentaje', 0):g}% sobre {base_uf_mostrar:,.2f} UF)"
    else:
        etiqueta_premio = "Premio Macal"

    def _row(label, value, bold=False):
        ls = S["small"] if not bold else S["bold"]
        rs = S["right"] if not bold else S["right_bold"]
        return [Paragraph(label, ls), Paragraph(_fmt_clp(value), rs)]

    # INGRESOS
    elements.append(Paragraph("INGRESOS", S["section"]))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=ORANGE, spaceAfter=4))

    ing_table = Table(
        [_row("Abonado por Comprador", abonos, bold=True)],
        colWidths=[13 * cm, 5 * cm],
        hAlign="LEFT",
    )
    ing_table.setStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])
    elements.append(ing_table)
    elements.append(Spacer(1, 8))

    # GASTOS (descuenta_gastos == "Sí")
    if calculo.get("descuenta_gastos") == "Sí":
        elements.append(Paragraph("GASTOS", S["section"]))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=ORANGE, spaceAfter=4))

        gasto_rows = [
            _row("Total Gastos", calculo.get("deducciones_totales"), bold=True),
            _row(etiqueta_comision, calculo.get("comision") or 0),
            _row("IVA Comisión Macal", calculo.get("iva_comision") or 0),
            _row(etiqueta_premio, calculo.get("premio") or 0),
            _row("IVA Premio Macal", calculo.get("iva_premio") or 0),
            _row("Publicidad", calculo.get("publicidad") or 0),
            _row("IVA Publicidad", calculo.get("iva_publicidad") or 0),
            _row("Costo Vale Vista", calculo.get("costo_vale_vista") or 0),
            _row("Costo Instrucciones Notariales", calculo.get("costo_instrucciones") or 0),
            _row("Costo Antecedentes Legales", calculo.get("costo_antecedentes") or 0),
        ]
        gasto_table = Table(gasto_rows, colWidths=[13 * cm, 5 * cm], hAlign="LEFT")
        gasto_table.setStyle([
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 1), (0, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, GRAY_LIGHT]),
        ])
        elements.append(gasto_table)
        elements.append(Spacer(1, 8))

    # PAGO A MANDANTE
    elements.append(Paragraph("PAGO A MANDANTE", S["section"]))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=ORANGE, spaceAfter=4))

    saldo = calculo.get("saldo_por_pagar_al_vendedor")
    vale = calculo.get("monto_vale_vista") or 0

    if calculo.get("vale_vista_var") == "Sí":
        pago_rows = [
            _row("Total Pago a Mandante", (vale + (saldo or 0)), bold=True),
            _row("Vale Vista", vale),
            _row("Saldo a pagar", saldo),
        ]
    else:
        pago_rows = [_row("Saldo a pagar", saldo, bold=True)]

    pago_table = Table(pago_rows, colWidths=[13 * cm, 5 * cm], hAlign="LEFT")
    pago_table.setStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])
    elements.append(pago_table)
    elements.append(Spacer(1, 6))

    # Caja total destacada
    total_box = Table(
        [[Paragraph("SALDO NETO A PAGAR", S["total_label"]), Paragraph(_fmt_clp(saldo), S["total_value"])]],
        colWidths=[10 * cm, 8 * cm],
    )
    total_box.setStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ORANGE_LIGHT),
        ("BOX", (0, 0), (-1, -1), 1.5, ORANGE),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ])
    elements.append(total_box)

    # GASTOS POR PAGAR (descuenta_gastos == "No")
    if calculo.get("descuenta_gastos") == "No":
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("GASTOS POR PAGAR", S["section"]))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=ORANGE, spaceAfter=4))

        gasto_rows2 = [
            _row("Total Gastos", calculo.get("total_gastos") or 0, bold=True),
            _row(etiqueta_comision, calculo.get("comision") or 0),
            _row("IVA Comisión Macal", calculo.get("iva_comision") or 0),
            _row(etiqueta_premio, calculo.get("premio") or 0),
            _row("IVA Premio Macal", calculo.get("iva_premio") or 0),
            _row("Publicidad", calculo.get("publicidad") or 0),
            _row("IVA Publicidad", calculo.get("iva_publicidad") or 0),
            _row("Costo Vale Vista", calculo.get("costo_vale_vista") or 0),
            _row("Costo Instrucciones Notariales", calculo.get("costo_instrucciones") or 0),
            _row("Costo Antecedentes Legales", calculo.get("costo_antecedentes") or 0),
        ]
        gasto_table2 = Table(gasto_rows2, colWidths=[13 * cm, 5 * cm], hAlign="LEFT")
        gasto_table2.setStyle([
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 1), (0, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, GRAY_LIGHT]),
        ])
        elements.append(gasto_table2)

    # Footer
    elements.append(Spacer(1, 14))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_LIGHT, spaceAfter=4))
    elements.append(Paragraph(
        f"Documento generado el {fecha_hoy} — Macal LTDA",
        S["small_gray"],
    ))

    doc.build(elements)
