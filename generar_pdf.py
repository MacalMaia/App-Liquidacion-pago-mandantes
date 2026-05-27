from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from datetime import datetime
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

# Fuente Montserrat
pdfmetrics.registerFont(TTFont("Montserrat", "fonts/Montserrat-Regular.ttf"))
pdfmetrics.registerFont(TTFont("Montserrat-Bold", "fonts/Montserrat-Bold.ttf"))
registerFontFamily(
    "Montserrat",
    normal="Montserrat",
    bold="Montserrat-Bold"
)

def generar_pdf(resultado, output_path="liquidacion_mandante.pdf"):
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "Montserrat"
    styles["Title"].fontName = "Montserrat-Bold"
    styles.add(ParagraphStyle(name="Fecha_Logo", parent=styles["Normal"], alignment=2))
    styles.add(ParagraphStyle(name="Titulos_Tabla", parent=styles["Normal"], fontName="Montserrat-Bold", alignment=1, textColor=colors.white))
    styles.add(ParagraphStyle(name="Celda_Tabla", parent=styles["Normal"], alignment=1))
    styles.add(ParagraphStyle(name="Normal_font8", parent=styles["Normal"], fontSize=8))
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm
        )
    elements = []

    calculo = resultado.get("calculo", {})
    ident = resultado.get("identificacion", {})
    insum = resultado.get("insumos", {})
    param = resultado.get("parametros", {})

    #--- PDF ---#
    #-- Logo Macal --#
    logo = Image("logo/logo_macal_horizontal.png")

    aspect_ratio = logo.imageHeight / float(logo.imageWidth)

    logo.drawWidth = 6.5 * cm
    logo.drawHeight = logo.drawWidth * aspect_ratio  # altura proporcional

    # Fecha de hoy en formato lindo
    meses = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
        5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
        9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
    }
    
    hoy = datetime.now()
    fecha_larga = f"Santiago, {hoy.day} de {meses[hoy.month]} de {hoy.year}"

    # Alinear a la derecha
    table_logo = Table([
        [logo], 
        [Paragraph(fecha_larga, styles["Fecha_Logo"])],
        ],
        colWidths=[18 * cm])
    table_logo.setStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"), 
        ("BOTTOMPADDING", (0, 0), (0, 0), 12),
        ])
    elements.append(table_logo)

    elements.append(Spacer(1, 35))

    elements.append(Paragraph("Liquidación de Pago", styles["Title"]))

    elements.append(Spacer(1, 30))

    rep_legal = ident.get("representante_legal")
    if rep_legal == "null":  
        rep_legal = None

    elements.append(
    Paragraph(f"<b>Señor/a</b> {rep_legal}, {ident.get('mandante', '')}" if rep_legal else f"Señor/a {ident.get('mandante', '')}", styles["Normal"]))
    
    elements.append(Spacer(1, 20))

    fecha_subasta = datetime.strptime(ident.get('fecha_subasta'), "%d-%m-%Y")
    fecha_subasta_texto = f"{fecha_subasta.day} de {meses[fecha_subasta.month]} de {fecha_subasta.year}"

    elements.append(Paragraph(f"<b>Referencias: </b>Lote {ident.get('numero_lote')} - Subasta {fecha_subasta_texto} - {ident.get('propiedad')}, {ident.get('comuna')}", styles["Normal"]))

    elements.append(Spacer(1, 20))

    # Tabla con detalles de propiedad #
    fecha_mandato = datetime.strptime(ident.get('fecha_firma_mandato'), "%d-%m-%Y")
    fecha_mandato_texto = f"{fecha_mandato.day} de {meses[fecha_mandato.month]} de {fecha_mandato.year}"

    elements.append(Paragraph(f"De acuerdo a lo convenido en mandato firmado con fecha {fecha_mandato_texto} suscrito entre <b>{ident.get('mandante')}</b> y Macal, se detalla liquidación de las propiedades referidas a continuación:", styles["Normal"]))

    elements.append(Spacer(1, 30))

    table_propiedad = Table([
        [
            Paragraph("Lote", styles["Titulos_Tabla"]), 
            Paragraph("Dirección", styles["Titulos_Tabla"]), 
            Paragraph("Comuna", styles["Titulos_Tabla"]), 
            Paragraph("Valor Adjudicado", styles["Titulos_Tabla"]), 
            Paragraph("Valor Pagado Comprador", styles["Titulos_Tabla"]),
            ], 
        [
            Paragraph(str(ident.get('numero_lote')), styles["Celda_Tabla"]),
            Paragraph(ident.get('propiedad'), styles["Celda_Tabla"]), 
            Paragraph(ident.get('comuna'), styles["Celda_Tabla"]), 
            Paragraph(f"${insum.get('adjudicacion_pesos'):,}".replace(",", "."), styles["Celda_Tabla"]), 
            Paragraph(f"<b>${insum.get('abonos_comprador_pesos'):,}</b>".replace(",", "."), styles["Celda_Tabla"]), 
            ]],
        colWidths=[1.5 * cm, 6 * cm, 3.5 * cm, 3 * cm, 3 * cm, 3 * cm])
    table_propiedad.setStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        # Encabezado
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#FF6600")),     # fondo gris claro

        # Celdas del cuerpo
        ("BACKGROUND", (0,1), (-1,-1), colors.whitesmoke),   # fondo celeste claro
        
         # Bordes
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),         # todas las líneas
        ("BOX", (0,0), (-1,-1), 1, colors.black),            # borde exterior grueso
        ]) 
    elements.append(table_propiedad)
    # Fin tabla propiedad #

    elements.append(Spacer(1, 40))

    elements.append(Paragraph(f"<b>Detalle de montos de Liquidación de Pago</b>", styles["Normal"]))

    elements.append(Spacer(1, 15))

    # Tablas con detalles de abonos y descuentos #

    elements.append(Paragraph(f"<b>INGRESOS</b>", styles["Normal_font8"]))

    elements.append(Spacer(1, 2))

    # ABONOS COMPRADOR
    table_liquidacion1 = Table([
        [Paragraph("<b>Abonado por Comprador</b>", styles["Normal_font8"]), Paragraph(f"<b>${insum.get('abonos_comprador_pesos'):,}</b>".replace(",", "."), styles["Normal_font8"]),],
        ],
        colWidths=[6 * cm, 4 * cm],
        hAlign="LEFT",
        )
    table_liquidacion1.setStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]) 
    elements.append(table_liquidacion1)

    elements.append(Spacer(1, 10))

    # DESCUENTOS SI descuenta_gastos = "Sí" (se muestran entre Pagado y Saldo para que parezca resta)    
    # Construye etiqueta comisión para colocar el signo "%" si corresponde
    comision_macal_val = calculo.get('comision_macal')
    if param.get('tipo_comision') == "Porcentaje" and comision_macal_val is not None:
        etiqueta_comision = f"Comisión Macal ({comision_macal_val:,}%)".replace(".", ",")
    else:
        etiqueta_comision = "Comisión Macal"

    # Construye etiqueta premio con tramo aplicado
    tramo = param.get("tramo_aplicado")
    if tramo:
        etiqueta_premio = f"Premio Macal ({tramo.get('porcentaje',0):,}% sobre {tramo.get('base_uf',0):,} UF)".replace(".", ",")
    else:
        etiqueta_premio = "Premio Macal"
    
    # Tabla de descuentos
    if calculo.get('descuenta_gastos') == "Sí":
        elements.append(Paragraph(f"<b>GASTOS</b>", styles["Normal_font8"]))

        elements.append(Spacer(1, 2))
        
        table_liquidacion2 = Table([
            [Paragraph("<b>Total Gastos</b>", styles["Normal_font8"]), Paragraph(f"<b>${calculo.get('deducciones_totales'):,}</b>".replace(",", "."), styles["Normal_font8"]),],
            [Paragraph(etiqueta_comision, styles["Normal_font8"]), Paragraph(f"${calculo.get('comision') or 0:,}".replace(",", "."), styles["Normal_font8"]),],
            [Paragraph(f"IVA Comisión Macal", styles["Normal_font8"]), Paragraph(f"${calculo.get('iva_comision') or 0:,}".replace(",", "."), styles["Normal_font8"]),],
            [Paragraph(etiqueta_premio, styles["Normal_font8"]), Paragraph(f"${calculo.get('premio') or 0:,}".replace(",", "."), styles["Normal_font8"]),],
            [Paragraph(f"IVA Premio Macal", styles["Normal_font8"]), Paragraph(f"${calculo.get('iva_premio') or 0:,}".replace(",", "."), styles["Normal_font8"]),],
            [Paragraph(f"Publicidad", styles["Normal_font8"]), Paragraph(f"${calculo.get('publicidad') or 0:,}".replace(",", "."), styles["Normal_font8"]),],
            [Paragraph(f"IVA Publicidad", styles["Normal_font8"]), Paragraph(f"${calculo.get('iva_publicidad') or 0:,}".replace(",", "."), styles["Normal_font8"]),],
            [Paragraph(f"Costo Vale Vista", styles["Normal_font8"]), Paragraph(f"${(calculo.get('costo_vale_vista') or 0):,}".replace(",", "."), styles["Normal_font8"]),],
            [Paragraph(f"Costo Instrucciones Notariales", styles["Normal_font8"]), Paragraph(f"${+(calculo.get('costo_instrucciones') or 0):,}".replace(",", "."), styles["Normal_font8"]),],
            [Paragraph(f"Costo Antecedentes Legales", styles["Normal_font8"]), Paragraph(f"${+(calculo.get('costo_antecedentes') or 0):,}".replace(",", "."), styles["Normal_font8"]),],
            ],
            colWidths=[6 * cm, 4 * cm],
            hAlign="LEFT",
            )
        table_liquidacion2.setStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0,1), (0,9), 10),
            ]) 
        elements.append(table_liquidacion2)

        elements.append(Spacer(1, 10))

    # SALDO A PAGAR A VENDEDOR (Con condicional si existe abono con vale vista para restarlo del pago)
    elements.append(Paragraph(f"<b>PAGO A MANDANTE</b>", styles["Normal_font8"]))

    #spacer elements.append(Spacer(1, 5))

    if calculo.get('vale_vista_var') == "Sí":
        
        table_liquidacion5 = Table([
            [Paragraph("<b>Total Pago a Mandante</b>", styles["Normal_font8"]), Paragraph(f"<b>${calculo.get('monto_vale_vista') + calculo.get('saldo_por_pagar_al_vendedor') or 0:,}</b>".replace(",", "."), styles["Normal_font8"]),],
            ],
            colWidths=[6 * cm, 4 * cm],
            hAlign="LEFT",
            )
        table_liquidacion5.setStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]) 
        elements.append(table_liquidacion5)

        table_liquidacion3 = Table([
            [Paragraph("Vale Vista", styles["Normal_font8"]), Paragraph(f"${calculo.get('monto_vale_vista') or 0:,}".replace(",", "."), styles["Normal_font8"]),],
            ],
            colWidths=[6 * cm, 4 * cm],
            hAlign="LEFT",
            )
        table_liquidacion3.setStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]) 
        elements.append(table_liquidacion3)

        table_liquidacion4 = Table([
            [Paragraph("Saldo a pagar", styles["Normal_font8"]), Paragraph(f"${calculo.get('saldo_por_pagar_al_vendedor') or 0:,}".replace(",", "."), styles["Normal_font8"]),],
            ],
            colWidths=[6 * cm, 4 * cm],
            hAlign="LEFT",
            )
        table_liquidacion4.setStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]) 
        elements.append(table_liquidacion4)

    elif calculo.get('vale_vista_var') == "No":
        table_liquidacion4 = Table([
            [Paragraph("<b>Saldo a pagar</b>", styles["Normal_font8"]), Paragraph(f"<b>${calculo.get('saldo_por_pagar_al_vendedor') or 0:,}</b>".replace(",", "."), styles["Normal_font8"]),],
            ],
            colWidths=[6 * cm, 4 * cm],
            hAlign="LEFT",
            )
        table_liquidacion4.setStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]) 
        elements.append(table_liquidacion4)

    elements.append(Spacer(1, 10))

    # DESCUENTOS NO descuenta_gastos = "No" (se muestran despues del saldo para dejarlos "Por pagar")

    if calculo.get('descuenta_gastos') == "No":
        elements.append(Paragraph(f"<b>GASTOS POR PAGAR</b>", styles["Normal_font8"]))

        elements.append(Spacer(1, 2))

        table_liquidacion2 = Table([
            [Paragraph("<b>Total Gastos</b>", styles["Normal_font8"]), Paragraph(f"<b>${calculo.get('total_gastos'):,}</b>".replace(",", "."), styles["Normal_font8"]),],
            [Paragraph(etiqueta_comision, styles["Normal_font8"]), Paragraph(f"${calculo.get('comision') or 0:,}".replace(",", "."), styles["Normal_font8"]),],
            [Paragraph(f"IVA Comisión Macal", styles["Normal_font8"]), Paragraph(f"${calculo.get('iva_comision') or 0:,}".replace(",", "."), styles["Normal_font8"]),],
            [Paragraph(etiqueta_premio, styles["Normal_font8"]), Paragraph(f"${calculo.get('premio') or 0:,}".replace(",", "."), styles["Normal_font8"]),],
            [Paragraph(f"IVA Premio Macal", styles["Normal_font8"]), Paragraph(f"${calculo.get('iva_premio') or 0:,}".replace(",", "."), styles["Normal_font8"]),],
            [Paragraph(f"Publicidad", styles["Normal_font8"]), Paragraph(f"${calculo.get('publicidad') or 0:,}".replace(",", "."), styles["Normal_font8"]),],
            [Paragraph(f"IVA Publicidad", styles["Normal_font8"]), Paragraph(f"${calculo.get('iva_publicidad') or 0:,}".replace(",", "."), styles["Normal_font8"]),],
            [Paragraph(f"Costo Vale Vista", styles["Normal_font8"]), Paragraph(f"${(calculo.get('costo_vale_vista') or 0):,}".replace(",", "."), styles["Normal_font8"]),],
            [Paragraph(f"Costo Instrucciones Notariales", styles["Normal_font8"]), Paragraph(f"${+(calculo.get('costo_instrucciones') or 0):,}".replace(",", "."), styles["Normal_font8"]),],
            [Paragraph(f"Costo Antecedentes Legales", styles["Normal_font8"]), Paragraph(f"${+(calculo.get('costo_antecedentes') or 0):,}".replace(",", "."), styles["Normal_font8"]),],
            ],
            colWidths=[6 * cm, 4 * cm],
            hAlign="LEFT",
            )
        table_liquidacion2.setStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0,1), (0,7), 10),
            ]) 
        elements.append(table_liquidacion2)

    doc.build(elements)