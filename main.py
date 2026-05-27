import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from pago_mandates import (
    extract_json_mandato_from_pdf,
    extraer_json_liquidacion,
    liquidar_pago,
    _int_or_none,
)
from generar_pdf import generar_pdf

class PagoVendedorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Calculadora de Liquidación a Mandante")
        # Posición y tamaño de la ventana Tkinter
        w, h = 800, 800
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        # Rutas de los PDF
        self.mandato_pdf = None
        self.liquidacion_pdf = None

        # Contenedor horizontal para los frames de MANDATO y LIQUIDACION
        frame_cargas = ttk.Frame(root)
        frame_cargas.pack(pady=10, padx=10, fill="x")

        # Permitir que ambas columnas se expandan
        frame_cargas.columnconfigure(0, weight=1)
        frame_cargas.columnconfigure(1, weight=1)

        # --- Frame para MANDATO ---
        frame_mandato = ttk.LabelFrame(frame_cargas, text="Mandato Legalizado", padding=(10, 5))
        frame_mandato.grid(row=0, column=0, padx=10, sticky="ew")  # Sticky hace que se expanda horizontalmente

        btn_mandato = ttk.Button(frame_mandato, text="📄 Cargar Mandato", command=self.cargar_mandato)
        btn_mandato.pack(pady=5)

        # --- Frame para LIQUIDACION ---
        frame_liquidacion = ttk.LabelFrame(frame_cargas, text="Liquidación de Pago (de CORE)", padding=(10, 5))
        frame_liquidacion.grid(row=0, column=1, padx=10, sticky="ew")

        btn_liquidacion = ttk.Button(frame_liquidacion, text="📄 Cargar Liquidación", command=self.cargar_liquidacion)
        btn_liquidacion.pack(pady=5)
        
        # --- Frame para DATOS DESDE LEGAL ---
        input_frame = ttk.LabelFrame(root, text="Datos desde Legal", padding=(10, 5))
        input_frame.pack(pady=10, padx=10, fill="x")

        # Configurar columnas para que se repartan el espacio horizontal
        input_frame.columnconfigure(0, weight=1)
        input_frame.columnconfigure(1, weight=1)
        input_frame.columnconfigure(2, weight=1)

        # --- Variables ---
        self.vale_vista_var = tk.StringVar()
        self.costo_vale_vista_var = tk.StringVar()
        self.monto_vale_vista_var = tk.StringVar()
        self.instrucciones_var = tk.StringVar()
        self.costo_instrucciones_var = tk.StringVar()
        self.descuenta_gastos_var = tk.StringVar()
        self.antecedentes_var = tk.StringVar()
        self.costo_antecedentes_var = tk.StringVar()

        # --- Sección Vale Vista ---
        ttk.Label(input_frame, text="¿Pago incluye Vale Vista?").grid(row=0, column=0, sticky="w", pady=(5, 2))
        vale_combobox = ttk.Combobox(
            input_frame,
            textvariable=self.vale_vista_var,
            values=["", "Sí", "No"],
            state="readonly",
            width=20
        )
        vale_combobox.grid(row=1, column=0, sticky="w", padx=(0, 10))
        vale_combobox.set("")

        ttk.Label(input_frame, text="Costo de vale vista (CLP):").grid(row=0, column=1, sticky="w", pady=(5, 2))
        self.entry_costo_vale_vista = ttk.Entry(input_frame, textvariable=self.costo_vale_vista_var, state="disabled", width=20)
        self.entry_costo_vale_vista.grid(row=1, column=1, sticky="w")

        ttk.Label(input_frame, text="Monto de vale vista (CLP):").grid(row=0, column=2, sticky="w", pady=(5, 2))
        self.entry_monto_vale_vista = ttk.Entry(input_frame, textvariable=self.monto_vale_vista_var, state="disabled", width=20)
        self.entry_monto_vale_vista.grid(row=1, column=2, sticky="w")

        # --- Sección Instrucciones Notariales ---
        ttk.Label(input_frame, text="¿Incluye Instrucciones Notariales?").grid(row=2, column=0, sticky="w", pady=(10, 2))
        instrucciones_combobox = ttk.Combobox(
            input_frame,
            textvariable=self.instrucciones_var,
            values=["", "Sí", "No"],
            state="readonly",
            width=20
        )
        instrucciones_combobox.grid(row=3, column=0, sticky="w", padx=(0, 10))
        instrucciones_combobox.set("")

        ttk.Label(input_frame, text="Costo de instrucciones notariales (CLP):").grid(row=2, column=1, sticky="w", pady=(10, 2))
        self.entry_instrucciones = ttk.Entry(input_frame, textvariable=self.costo_instrucciones_var, state="disabled", width=20)
        self.entry_instrucciones.grid(row=3, column=1, sticky="w")

        ttk.Label(input_frame, text="¿Se descuentan gastos en Liquidación?:").grid(row=2, column=2, sticky="w", pady=(10, 2))
        descuenta_gastos_combobox = ttk.Combobox(
            input_frame,
            textvariable=self.descuenta_gastos_var,
            values=["", "Sí", "No"],
            state="readonly",
            width=20
        )
        descuenta_gastos_combobox.grid(row=3, column=2, sticky="w")
        descuenta_gastos_combobox.set("")  # valor inicial vacío

        # --- Seccion para Antecedentes Legales ---
        ttk.Label(input_frame, text="¿Incluye Antecedentes Legales?").grid(row=4, column=0, sticky="w", pady=(10,2))
        antecedentes_combobox = ttk.Combobox(
            input_frame,
            textvariable=self.antecedentes_var,
            values=["","Sí","No"],
            state="readonly",
            width=20
        )
        antecedentes_combobox.grid(row=5, column=0, sticky="w", pady=(10,2))
        antecedentes_combobox.set("")

        ttk.Label(input_frame, text="Costo de Antecedentes Legales (CLP):").grid(row=4, column=1, sticky="w", pady=(10,2))
        self.entry_antecedentes = ttk.Entry(input_frame, textvariable=self.costo_antecedentes_var, state="disabled", width=20)
        self.entry_antecedentes.grid(row=5, column=1, sticky="w")

        # --- Funciones para habilitar/deshabilitar campos ---
        def toggle_vale_vista(*args):
            if self.vale_vista_var.get() == "Sí":
                self.entry_costo_vale_vista.configure(state="normal")
                self.entry_monto_vale_vista.configure(state="normal")
            else:
                self.entry_costo_vale_vista.configure(state="disabled")
                self.costo_vale_vista_var.set("")
                self.entry_monto_vale_vista.configure(state="disabled")
                self.monto_vale_vista_var.set("")

        def toggle_instrucciones(*args):
            if self.instrucciones_var.get() == "Sí":
                self.entry_instrucciones.configure(state="normal")
            else:
                self.entry_instrucciones.configure(state="disabled")
                self.costo_instrucciones_var.set("")
            
        def toggle_antecedentes(*args):
            if self.antecedentes_var.get() == "Sí":
                self.entry_antecedentes.configure(state="normal")
            else:
                self.entry_antecedentes.configure(state="disabled")
                self.costo_antecedentes_var.set("")

        self.vale_vista_var.trace_add("write", toggle_vale_vista)
        self.instrucciones_var.trace_add("write", toggle_instrucciones)
        self.antecedentes_var.trace_add("write", toggle_antecedentes)

        # Boton de calculo
        tk.Button(root, text="💰 Calcular Pago", command=self.calcular_pago).pack(pady=10)

        # Boton generar PDF
        self.btn_generar_pdf = tk.Button(root, text="📄 Generar PDF", command=self.generar_pdf_gui, state="disabled")
        self.btn_generar_pdf.pack(pady=5)

        # Frame para resultados (tabla fija)
        canvas_frame = tk.Frame(root)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(canvas_frame)
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        self.resultados_frame = tk.Frame(canvas)

        self.resultados_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.resultados_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # --- Activa scroll con rueda del mouse ---
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def cargar_mandato(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if file_path:
            self.mandato_pdf = file_path
            #messagebox.showinfo("Éxito", "Mandato cargado correctamente.")

    def cargar_liquidacion(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if file_path:
            self.liquidacion_pdf = file_path
            #messagebox.showinfo("Éxito", "Liquidación cargada correctamente.")

    def calcular_pago(self):
        if not self.mandato_pdf or not self.liquidacion_pdf:
            messagebox.showwarning("Faltan archivos", "Debes cargar ambos PDFs antes de calcular.")
            return

        try:
            # 🧾 1. Extraer datos de los PDFs usando Claude
            man = extract_json_mandato_from_pdf(Path(self.mandato_pdf))
            liq = extraer_json_liquidacion(Path(self.liquidacion_pdf))

            # 📉 2. Agregar descuentos manuales si corresponden
            if self.vale_vista_var.get() == "Sí":
                man["costo_vale_vista"] = _int_or_none(self.costo_vale_vista_var.get())
            else:
                man["costo_vale_vista"] = 0
            
            if self.vale_vista_var.get() == "Sí":
                man["monto_vale_vista"] = _int_or_none(self.monto_vale_vista_var.get())
            else:
                man["monto_vale_vista"] = 0

            if self.instrucciones_var.get() == "Sí":
                man["costo_instrucciones"] = _int_or_none(self.costo_instrucciones_var.get())
            else:
                man["costo_instrucciones"] = 0

            if self.antecedentes_var.get() == "Sí":
                man["costo_antecedentes"] = _int_or_none(self.costo_antecedentes_var.get())
            else:
                man["costo_antecedentes"] = 0

            man["vale_vista_var"] = self.vale_vista_var.get() or None
            man["instrucciones_var"] = self.instrucciones_var.get() or None
            man["descuenta_gastos"] = self.descuenta_gastos_var.get() or None
            man["antecedentes_var"] = self.antecedentes_var.get() or None
            
            print("🔍 Resultado generado:")
            from pprint import pprint
            print("📦 man con variables manuales:")
            pprint(man)

            # 🧮 3. Calcular resultado
            self.resultado = liquidar_pago(liq, man)
            self.btn_generar_pdf.config(state="normal")
            resultado = self.resultado

            print("📊 Sección 'calculo':")
            pprint(self.resultado["calculo"])
            
            # 🖨️ 4. Mostrar resultado en GUI (formato fijo)
            for widget in self.resultados_frame.winfo_children():
                widget.destroy()

            row = 0
            def add_section(title):
                nonlocal row
                lbl = tk.Label(self.resultados_frame, text=title, font=("TkDefaultFont", 11, "bold"))
                lbl.grid(row=row, column=0, columnspan=2, sticky="w", pady=(10, 2))
                row += 1

            def add_item(label, value, bold=False, multiline=False):
                nonlocal row
                style = ("TkDefaultFont", 10, "bold") if bold else ("TkDefaultFont", 10)

                # Formatear números con separador de miles, texto dejarlo tal cual
                if isinstance(value, (int, float)):
                    display_value = f"{value:,}"
                else:
                    display_value = str(value)

                # Columna 1: título fijo
                tk.Label(self.resultados_frame, text=label, anchor="w", font=style, width=35).grid(
                    row=row, column=0, sticky="w", padx=5
                    )
                
                # Columna 2: valor
                tk.Label(
                    self.resultados_frame, 
                    text=display_value, 
                    anchor="w", 
                    justify="left", 
                    font=style, 
                    wraplength=500 if multiline else 0
                ).grid(row=row, column=1, sticky="w", padx=5)

                row += 1

            calculo = resultado.get("calculo", {})
            param = resultado.get("parametros", {})
            insumos = resultado.get("insumos", {})
            info = resultado.get("identificacion", {})

            add_section("IDENTIFICACION")
            add_item("Mandante", info.get("mandante", 0))
            add_item("Lote", info.get("numero_lote", 0))
            add_item("Propiedad", info.get("propiedad", 0))
            add_item("Comuna", info.get("comuna", 0))

            add_section("PARAMETROS")
            add_item("Tipo Comision Macal", param.get("tipo_comision", 0))
            add_item("% Comision Macal", calculo.get("comision_macal") or "No encontrado en PDF")
            add_item("Premio (Si/No)", "Sí" if param.get("paga_premio") else "No")
            add_item("Tipo propiedad", param.get("tipo_propiedad") or "no determinado")
            tramo = param.get("tramo_aplicado")
            if tramo:
                add_item("Tramo premio aplicado", f"{tramo.get('porcentaje',0)}% sobre {tramo.get('base_uf',0)} UF — {tramo.get('condicion','')}", multiline=True)
            else:
                add_item("Tramo premio aplicado", "Ninguno")
            add_item("Condicion para premio", param.get("condicion_premio", ""), multiline=True)
            add_item("Publicidad (Si/No)", "Sí" if param.get("paga_publicidad") else "No")
            add_item("Pago incluye Vale Vista", calculo.get("vale_vista_var", ""))
            add_item("Incluye Instrucciones Notariales", calculo.get("instrucciones_var", ""))
            add_item("Descuenta gastos en Liquidación", calculo.get("descuenta_gastos", ""))
            add_item("Incluye Antecedentes Legales", calculo.get("antecedentes_var", ""))
            
            add_section("INGRESOS")
            add_item("Abonos comprador", insumos.get("abonos_comprador_pesos", 0), bold=True)

            if calculo.get('descuenta_gastos') == "Sí":
                add_section("GASTOS")            
                add_item("Total Gastos", calculo.get("deducciones_totales") or 0, bold=True)
                add_item("Comisión Macal", calculo.get("comision") or 0)
                add_item("IVA Comisión", calculo.get("iva_comision") or 0)
                add_item("Premio en pesos", calculo.get("premio") or 0)
                add_item("IVA Premio", calculo.get("iva_premio") or 0)
                add_item("Costo Publicidad", calculo.get("publicidad") or 0)
                add_item("IVA Publicidad", calculo.get("iva_publicidad") or 0)
                add_item("Costo Instrucciones Notariales", calculo.get("costo_instrucciones") or 0)
                add_item("Costo Vale vista", calculo.get("costo_vale_vista") or 0)
                add_item("Costo Antecedentes Legales", calculo.get("costo_antecedentes") or 0)
                
            add_section("PAGO A MANDANTE")
            if calculo.get('vale_vista_var') == "Sí":
                add_item("Total pago", calculo.get("monto_vale_vista", 0) + calculo.get("saldo_por_pagar_al_vendedor"), bold=True)
                add_item("Vale vista", calculo.get("monto_vale_vista", 0))
                add_item("Saldo a pagar", calculo.get("saldo_por_pagar_al_vendedor", 0))
            elif calculo.get('vale_vista_var') == "No":
                add_item("Saldo a pagar", calculo.get("saldo_por_pagar_al_vendedor", 0), bold=True)

            if calculo.get('descuenta_gastos') == "No":
                add_section("GASTOS POR PAGAR")       
                add_item("Total Gastos", calculo.get("total_gastos") or 0, bold=True)
                add_item("Comisión Macal", calculo.get("comision") or 0)
                add_item("IVA Comisión", calculo.get("iva_comision") or 0)
                add_item("Premio en pesos", calculo.get("premio") or 0)
                add_item("IVA Premio", calculo.get("iva_premio") or 0)
                add_item("Costo Publicidad", calculo.get("publicidad") or 0)
                add_item("IVA Publicidad", calculo.get("iva_publicidad") or 0)
                add_item("Costo Instrucciones Notariales", calculo.get("costo_instrucciones") or 0)
                add_item("Costo Vale vista", calculo.get("costo_vale_vista") or 0)
                add_item("Costo Antecedentes Legales", calculo.get("costo_antecedentes") or 0)

        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error durante el cálculo:\n{e}")
    
    def generar_pdf_gui(self):
        try:
            # Verificar que ya se haya calculado un resultado
            if not hasattr(self, "resultado") or self.resultado is None:
                messagebox.showwarning("Falta cálculo", "Primero debes calcular el pago antes de generar el PDF.")
                return

            # Pedir ubicación para guardar el archivo
            file_path = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                title="Guardar PDF como"
            )

            if file_path:
                generar_pdf(self.resultado, output_path=file_path)
                messagebox.showinfo("PDF generado", f"El archivo se ha guardado en:\n{file_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al generar el PDF:\n{e}")

# Ejecutar la app
if __name__ == "__main__":
    root = tk.Tk()
    app = PagoVendedorApp(root)
    root.mainloop()