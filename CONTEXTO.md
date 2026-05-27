# Contexto del Proyecto — App Liquidación Pago Mandantes

---

## Webapp en GCP (v2)

La aplicación ahora tiene dos modos de uso:
- **Desktop (Tkinter)**: `main.py` — uso local sin cambios
- **Webapp (FastAPI + React)**: `backend/` + `frontend/` — desplegable en Cloud Run

### Estructura del repo

```
backend/
  app/
    main.py                  # FastAPI app, monta frontend/dist como static
    routes/liquidacion.py    # POST /api/liquidar, POST /api/pdf
    services/pago_mandates.py  # lógica de extracción y cálculo (acepta bytes)
    services/generar_pdf.py    # genera PDF rediseñado, devuelve bytes
    auth/sso_microsoft.py      # stub comentado de SSO Microsoft
    fonts/                   # Montserrat
    logo/
  requirements.txt
frontend/
  src/
    pages/Liquidador.tsx     # página única con stepper de 4 pasos
    components/              # Header, PDFDropzone, ParametrosLegalesForm, ResultadoCard, LoadingState
    lib/api.ts               # llamadas al backend
    lib/types.ts             # tipos TypeScript
  tailwind.config.js         # paleta naranja/morado/gris
Dockerfile                   # multi-stage: build React → uvicorn
cloudbuild.yaml              # CI/CD: build → push → deploy a Cloud Run
.env.example                 # template de variables de entorno
```

### Correr localmente (desarrollo)

```bash
# Backend
cd backend
pip install -r requirements.txt
ANTHROPIC_API_KEY=sk-ant-... uvicorn app.main:app --reload --port 8000

# Frontend (en otra terminal)
cd frontend
npm install
npm run dev          # http://localhost:5173 (proxy a :8000 via vite.config.ts)
```

### Deploy en GCP Cloud Run

#### 1. Configuración inicial (solo una vez)

```bash
PROJECT_ID="TU-PROYECTO-GCP"   # cambia esto
REGION="southamerica-west1"
SERVICE="liquidador"
REPO="liquidador-repo"

# Habilitar APIs
gcloud services enable run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  --project=$PROJECT_ID

# Crear repositorio de imágenes
gcloud artifacts repositories create $REPO \
  --repository-format=docker \
  --location=$REGION \
  --project=$PROJECT_ID

# Guardar API key como secret
echo -n "sk-ant-TU-API-KEY" | \
  gcloud secrets create anthropic-api-key \
    --data-file=- \
    --replication-policy=automatic \
    --project=$PROJECT_ID

# Dar acceso al Cloud Build service account al secret
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
gcloud secrets add-iam-policy-binding anthropic-api-key \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=$PROJECT_ID

# Lo mismo para la cuenta de Cloud Run
gcloud secrets add-iam-policy-binding anthropic-api-key \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=$PROJECT_ID
```

#### 2. Deploy

```bash
gcloud builds submit --config cloudbuild.yaml \
  --substitutions _PROJECT_ID=$PROJECT_ID,_REGION=$REGION,_SERVICE_NAME=$SERVICE,_REPO_NAME=$REPO \
  --project=$PROJECT_ID
```

#### 3. Ver la URL del servicio

```bash
gcloud run services describe $SERVICE --region=$REGION --format='value(status.url)'
```

### Activar SSO Microsoft (cuando se requiera)

1. Registrar aplicación en Azure AD (portal.azure.com → App registrations).
2. Agregar secrets en Secret Manager:
   ```bash
   gcloud secrets create ms-client-id --data-file=- <<< "TU-CLIENT-ID"
   gcloud secrets create ms-tenant-id --data-file=- <<< "TU-TENANT-ID"
   gcloud secrets create ms-client-secret --data-file=- <<< "TU-SECRET"
   ```
3. Agregar al `--set-secrets` en `cloudbuild.yaml`:
   ```
   MS_CLIENT_ID=ms-client-id:latest,MS_TENANT_ID=ms-tenant-id:latest,MS_CLIENT_SECRET=ms-client-secret:latest
   ```
4. En `backend/app/main.py`, descomentar las líneas del `MicrosoftSSOMiddleware`.
5. En `backend/app/auth/sso_microsoft.py`, descomentar todo el código.
6. Redesplegar.

---

## Propósito

Aplicación de escritorio para el equipo de Macal que calcula y genera la liquidación de pago al mandante (vendedor) de una propiedad subastada. A partir de dos PDFs —el mandato legalizado y la liquidación de pago emitida por CORE— calcula la comisión, IVA, premio, gastos adicionales y el saldo final a pagar al mandante, y genera un PDF de liquidación con la marca de Macal.

---

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| GUI | Python 3 + Tkinter |
| Extracción de datos desde PDFs | Anthropic Claude API (`claude-opus-4-1` y `claude-3-7-sonnet`) |
| Generación de PDF de salida | ReportLab |
| Fuentes | Montserrat (Regular + Bold) |
| Entorno de ejecución | `venv` (Windows), launcher `App Liquidacion.bat` |

---

## Archivos clave

```
App Liquidación pago mandantes/
├── main.py              # GUI Tkinter y orquestación general
├── pago_mandates.py     # Extracción Claude + función pura liquidar_pago()
├── generar_pdf.py       # Generación del PDF de liquidación con ReportLab
├── fonts/               # Montserrat-Regular.ttf, Montserrat-Bold.ttf
├── logo/                # logo_macal_horizontal.png
├── venv/                # Entorno virtual Windows (Python 3.13)
└── App Liquidacion.bat  # Launcher: activa venv y ejecuta main.py
```

---

## Arquitectura y flujo de datos

```
[Usuario]
    │
    ├─ Carga PDF Mandato (notarial)
    ├─ Carga PDF Liquidación (CORE)
    └─ Ingresa parámetros manuales (vale vista, instrucciones notariales,
       antecedentes legales, ¿descuenta gastos en liquidación?)
    │
    ▼
[main.py] llama a pago_mandates.py:
    │
    ├─ extract_json_mandato_from_pdf()
    │      → Claude claude-opus-4-1 lee el mandato notarial
    │      → Devuelve JSON con condiciones comerciales del mandante
    │
    ├─ extraer_json_liquidacion()
    │      → Claude claude-3-7-sonnet lee la liquidación CORE
    │      → Devuelve JSON con datos numéricos de la subasta
    │
    └─ liquidar_pago(liq, man)
           → Cálculo puro: comisión, IVA, premio, saldo
           → Devuelve dict estructurado: identificacion / insumos / parametros / calculo / alertas
    │
    ▼
[main.py] renderiza resultado en GUI (tabla con scroll)
    │
    └─ [generar_pdf.py] genera PDF de liquidación para el mandante
```

---

## JSON extraído del mandato

Modelo: `claude-opus-4-1-20250805`

| Campo | Descripción |
|---|---|
| `mandante` | Nombre del mandante (vendedor) |
| `representante_legal` | Representante legal, o `null` |
| `fecha_firma_mandato` | Fecha del mandato (`dd-mm-yyyy`) |
| `comision_macal` | Monto o porcentaje de comisión pactado |
| `tipo_comision` | `"Porcentaje"` o `"Pesos"` |
| `paga_premio` | `true`/`false` — ¿el mandante paga premio por sobre base? |
| `porcentaje_premio` | Porcentaje del premio (float), o `null` |
| `base_premio` | Monto base CLP a partir del cual aplica el premio |
| `condicion_premio` | Texto literal de la cláusula de premio |
| `paga_publicidad` | `true`/`false` — ¿el mandante paga publicidad? |
| `monto_publicidad_pesos` | Monto fijo de publicidad en CLP, o `0` |

---

## JSON extraído de la liquidación CORE

Modelo: `claude-3-7-sonnet-20250219`

| Campo | Descripción |
|---|---|
| `cliente_vendedor` | Nombre del vendedor/mandante en el encabezado del doc |
| `numero_lote` | Número de lote (entero) |
| `propiedad` | Dirección de la propiedad |
| `comuna` | Comuna |
| `valor_adjudicacion_pesos` | Primera línea columna "CARGO" (CLP entero), o `null` si no aparece |
| `valor_adjudicacion_uf` | Primera línea columna "CARGO UF" (float) |
| `fecha_subasta` | Fecha del remate (`dd-mm-yyyy`) |
| `uf_dia_subasta` | Primera fila columna "VALOR UF" (float) |
| `abonos_comprador_pesos` | Fila "ABONADO EN PESOS" (CLP entero) |

> **Nota importante:** Algunas liquidaciones no incluyen el valor de adjudicación en pesos (columna "CARGO" vacía). En ese caso `valor_adjudicacion_pesos` viene `null`. La app resuelve esto multiplicando `valor_adjudicacion_uf × uf_dia_subasta` y registra una alerta en el resultado.

---

## Parámetros manuales (ingresados en la GUI)

| Parámetro | Posibles valores | Descripción |
|---|---|---|
| `vale_vista_var` | `"Sí"` / `"No"` | ¿El pago al mandante incluye vale vista? |
| `costo_vale_vista` | CLP | Costo bancario del vale vista |
| `monto_vale_vista` | CLP | Monto del vale vista entregado al mandante |
| `instrucciones_var` | `"Sí"` / `"No"` | ¿Incluye instrucciones notariales? |
| `costo_instrucciones` | CLP | Costo de las instrucciones notariales |
| `descuenta_gastos` | `"Sí"` / `"No"` | ¿Los gastos de Macal se descuentan de la liquidación? |
| `antecedentes_var` | `"Sí"` / `"No"` | ¿Incluye antecedentes legales? |
| `costo_antecedentes` | CLP | Costo de los antecedentes legales |

---

## Cálculo en `liquidar_pago()` — detalle completo

### 1. Base de la comisión

La comisión siempre se calcula sobre el valor de adjudicación en pesos (`adj_pesos`).

Si la liquidación no trae `valor_adjudicacion_pesos` (campo `null`), se usa como fallback:

```
adj_pesos = round(valor_adjudicacion_uf × uf_dia_subasta)
```

Se registra una alerta en el resultado indicando que se usó este cálculo alternativo.

### 2. Comisión Macal

```
Si tipo_comision = "Porcentaje":
    comision = round(adj_pesos × comision_macal / 100)

Si tipo_comision = "Pesos":
    comision = comision_macal (monto fijo)

iva_comision = round(comision × 0.19)
```

### 3. Premio

```
Si paga_premio = true:
    diferencial = max(0, adj_pesos - base_premio)
    premio = round(diferencial × porcentaje_premio / 100)

iva_premio = round(premio × 0.19)
```

### 4. Publicidad

```
Si paga_publicidad = true:
    publicidad = monto_publicidad_pesos
iva_publicidad = round(publicidad × 0.19)
```

### 5. Total gastos

```
total_gastos = comision + iva_comision + premio + iva_premio
             + publicidad + iva_publicidad
             + costo_vale_vista + costo_instrucciones + costo_antecedentes
```

### 6. Deducciones según opción seleccionada

```
Si descuenta_gastos = "Sí":  deducciones = total_gastos
Si descuenta_gastos = "No":  deducciones = 0
```

### 7. Saldo a pagar al mandante

```
Si vale_vista_var = "No":
    teorico_vendedor = abonos_comprador_pesos - deducciones

Si vale_vista_var = "Sí":
    teorico_vendedor = abonos_comprador_pesos - monto_vale_vista - deducciones

saldo_por_pagar = max(0, min(abonos, teorico_vendedor))
```

---

## Estructura del resultado (`liquidar_pago`)

```python
{
  "identificacion": { mandante, representante_legal, fecha_subasta,
                      numero_lote, propiedad, comuna, fecha_firma_mandato },
  "insumos": { adjudicacion_pesos, adjudicacion_uf, uf_dia_subasta,
               adjudicacion_uf_en_pesos, abonos_comprador_pesos },
  "parametros": { tipo_comision, paga_premio, porcentaje_premio,
                  condicion_premio, base_premio, paga_publicidad, ... },
  "calculo": { comision, iva_comision, premio, iva_premio, publicidad,
               iva_publicidad, vale_vista_var, costo_vale_vista, monto_vale_vista,
               instrucciones_var, costo_instrucciones, descuenta_gastos,
               antecedentes_var, costo_antecedentes, deducciones_totales,
               total_gastos, saldo_por_pagar_al_vendedor },
  "alertas": [ "lista de advertencias si hubo problemas o datos faltantes" ]
}
```

---

## PDF generado (`generar_pdf.py`)

El PDF de liquidación incluye:

1. Logo Macal + fecha actual
2. Encabezado con nombre del mandante
3. Referencias: lote, fecha subasta, propiedad, comuna
4. Tabla de propiedad: lote, dirección, comuna, valor adjudicado, valor pagado por comprador
5. Sección INGRESOS: abonado por comprador
6. Sección GASTOS (si `descuenta_gastos = "Sí"`): desglose de comisión, IVA, premio, publicidad, etc.
7. Sección PAGO A MANDANTE: vale vista (si aplica) + saldo a pagar
8. Sección GASTOS POR PAGAR (si `descuenta_gastos = "No"`)

---

## Cómo ejecutar

### Windows (producción)

```
Doble clic en: App Liquidacion.bat
```

El bat activa el venv (`venv/Scripts/activate.bat`) y lanza `main.py`.

### Línea de comandos (desarrollo)

```bash
# Activar venv (Windows)
venv\Scripts\activate

# Ejecutar
python main.py
```

### Dependencias principales (en venv)

- `anthropic==0.68.0`
- `reportlab==4.4.4`
- `pillow==11.3.0`

---

## Modelos Claude utilizados

| Función | Modelo |
|---|---|
| Extracción mandato notarial | `claude-opus-4-1-20250805` |
| Extracción liquidación CORE | `claude-3-7-sonnet-20250219` |

Ambas llamadas usan `temperature=0` y `max_tokens=800`. Los PDFs se envían como documentos base64 (`media_type: application/pdf`).

---

## Notas operacionales

- La API key de Anthropic está hardcodeada en `pago_mandates.py` (variable `API_KEY`). Para producción se recomienda mover a variable de entorno.
- El venv está compilado para Windows (Python 3.13). En macOS/Linux se necesita recrear el venv.
- Si la liquidación CORE trae la columna "CARGO" en UF (sin CLP), la app calcula `adj_pesos = UF × valor_UF` y muestra una alerta informativa en pantalla y en el PDF.
