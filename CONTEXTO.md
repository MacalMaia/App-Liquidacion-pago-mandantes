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

#### Datos de producción actuales

| Parámetro | Valor |
|---|---|
| Proyecto GCP | `prod-microservices-473214` |
| Región | `southamerica-west1` |
| Servicio Cloud Run | `app-liquidacion-pago-mandantes` |
| Repositorio Artifact Registry | `cloud-run-source-deploy` |
| URL de producción | `https://app-liquidacion-pago-mandantes-150247226935.southamerica-west1.run.app` |

#### Variables de entorno en producción

Todas las variables están configuradas como **variables de entorno normales** en el panel
"Variables y secretos" del servicio Cloud Run (NO como GCP Secrets). Para cambiarlas:
Cloud Run → Servicios → `app-liquidacion-pago-mandantes` → Editar → Variables y secretos.

| Variable | Descripción |
|---|---|
| `ANTHROPIC_API_KEY` | API key de Anthropic |
| `AZURE_CLIENT_ID_SSO` | Application (client) ID del registro en Entra ID |
| `AZURE_TENANT_ID_SSO` | Directory (tenant) ID |
| `MS_CLIENT_SECRET` | Client secret del registro en Entra ID |
| `MS_REDIRECT_URI` | `https://<url-servicio>/auth/callback` |
| `ALLOWED_ORIGINS` | Origen permitido por CORS (URL del servicio) |
| `SESSION_SECRET` | Clave aleatoria para firmar cookies de sesión |

> ⚠️ **CRÍTICO:** el `cloudbuild.yaml` NO debe tener `--set-secrets` ni `--set-env-vars`.
> Si se agrega `--set-secrets ANTHROPIC_API_KEY=...`, el deploy falla porque la variable
> ya existe como env var normal y no se puede cambiar de tipo.

#### Deploy manual (procedimiento actual)

El trigger automático de GitHub no está disparándose. Hasta que se repare, **todo deploy
se hace con este comando** desde la raíz del repo:

```bash
gcloud builds submit --config cloudbuild.yaml \
  --substitutions COMMIT_SHA=$(git rev-parse HEAD) \
  --project=prod-microservices-473214
```

Los defaults del `cloudbuild.yaml` ya tienen el proyecto, región, servicio y repo correctos.
El comando sube el código local, construye la imagen Docker y despliega en Cloud Run (~4 min).

#### Ver la revisión activa

```bash
gcloud run services describe app-liquidacion-pago-mandantes \
  --region=southamerica-west1 --project=prod-microservices-473214 \
  --format="value(status.latestReadyRevisionName, spec.template.spec.containers[0].image)"
```

#### SSO Microsoft (activo)

El SSO ya está habilitado y funcionando. Las credenciales están en las variables de entorno
del servicio (ver tabla arriba). El middleware se activa automáticamente cuando
`AZURE_CLIENT_ID_SSO`, `AZURE_TENANT_ID_SSO` y `MS_CLIENT_SECRET` están definidas.

- Rutas de auth: `/auth/login`, `/auth/callback`, `/auth/logout`, `/auth/me`
- El Redirect URI registrado en Azure debe ser exactamente: `https://<url-servicio>/auth/callback`
- Los nombres de variable aceptados son `AZURE_CLIENT_ID_SSO`/`AZURE_TENANT_ID_SSO` (como
  están en el panel) O `MS_CLIENT_ID`/`MS_TENANT_ID` — el código acepta ambos.

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

- La API key de Anthropic está en la variable de entorno `ANTHROPIC_API_KEY` del servicio Cloud Run.
- El venv está compilado para Windows (Python 3.13). En macOS/Linux se necesita recrear el venv.
- Si la liquidación CORE trae la columna "CARGO" en UF (sin CLP), la app calcula `adj_pesos = UF × valor_UF` y muestra una alerta informativa en pantalla y en el PDF.

---

## Problemas conocidos, soluciones y lecciones aprendidas

Esta sección documenta los problemas reales encontrados en producción y cómo se resolvieron,
para no repetir el ciclo de diagnóstico.

### 1. PDFs de fojas.cl rechazados por Anthropic (400 "The PDF specified was not valid")

**Síntoma:** POST a `/api/liquidar` devuelve 500. El log muestra
`anthropic.BadRequestError: The PDF specified was not valid`.

**Causa:** Los mandatos notariales descargados de fojas.cl tienen dos problemas que Anthropic
no acepta:
1. El archivo empieza con basura HTML (`<br>-->?...`) y el `%PDF` real está en el byte 145.
2. El PDF viene cifrado con contraseña de usuario vacía (firma electrónica avanzada).

**Solución implementada:** `_normalizar_pdf()` en `pago_mandates.py` que, antes de enviar
el PDF a Anthropic:
1. Recorta todo lo que hay antes de `%PDF`.
2. Desbloquea la contraseña vacía con `pypdf`.
3. Reescribe el PDF ya sin cifrado.

**Dependencias requeridas:** `pypdf[crypto]>=5.0.0` en `requirements.txt`. El `[crypto]`
es obligatorio para poder descifrar; sin él, pypdf falla al intentar desbloquear el PDF.

---

### 2. `anthropic 1.0.0` rompe la API (`Messages.create() got an unexpected keyword argument 'temperature'`)

**Síntoma:** POST a `/api/liquidar` devuelve 422 con el mensaje de error anterior.

**Causa:** En agosto 2026 se publicó `anthropic 1.0.0`, que cambió la API de
`Messages.create()` e incompatibilizó con el código existente (entre otros, ya no acepta
`temperature` como kwarg directo).

**Solución:** `requirements.txt` pina `anthropic>=0.68.0,<1.0` para usar la última versión
estable 0.x (0.125.0 al momento del fix). Migrar a la API 1.0 requiere revisar el changelog
de Anthropic y actualizar las llamadas en `pago_mandates.py`.

---

### 3. El trigger automático de GitHub no dispara builds en Cloud Build

**Síntoma:** Se hace `git push origin main` pero no aparece ningún build nuevo en Cloud Build.
La revisión activa en Cloud Run sigue siendo la anterior.

**Causa:** El webhook de GitHub hacia Cloud Build dejó de funcionar (causa exacta no
investigada, posiblemente expiración de tokens o cambio en la configuración del trigger).

**Workaround (deploy manual):**
```bash
gcloud builds submit --config cloudbuild.yaml \
  --substitutions COMMIT_SHA=$(git rev-parse HEAD) \
  --project=prod-microservices-473214
```

**Diagnóstico:** Para verificar qué revisión está activa y qué commit tiene:
```bash
gcloud run services describe app-liquidacion-pago-mandantes \
  --region=southamerica-west1 --project=prod-microservices-473214 \
  --format="value(status.latestReadyRevisionName, spec.template.spec.containers[0].image)"
```
El SHA al final del nombre de imagen debe coincidir con `git rev-parse HEAD`.

---

### 4. Deploy falla: "Cannot update environment variable ANTHROPIC_API_KEY to the given type"

**Síntoma:** El paso 3 (deploy) del `gcloud builds submit` falla con ese mensaje.

**Causa:** El `cloudbuild.yaml` tenía `--set-secrets ANTHROPIC_API_KEY=anthropic-api-key:latest`,
pero `ANTHROPIC_API_KEY` ya existía en el servicio como variable de entorno normal (no como
GCP Secret). Cloud Run no permite cambiar el tipo de una variable en un deploy.

**Solución:** Eliminar cualquier `--set-secrets` y `--set-env-vars` del paso de deploy en
`cloudbuild.yaml`. Sin esos flags, el deploy preserva intactas todas las variables que ya
están configuradas en el servicio.

---

### 5. El build falla en el paso de push: "Repository 'liquidador-repo' not found"

**Síntoma:** El paso de docker push falla con `name unknown: Repository "liquidador-repo" not found`.

**Causa:** El `cloudbuild.yaml` tenía `_REPO_NAME: "liquidador-repo"` como default, pero ese
repositorio no existe en Artifact Registry. El repositorio real se llama `cloud-run-source-deploy`.

**Solución:** Los defaults del `cloudbuild.yaml` ya fueron corregidos. Si se necesita
inspeccionarlos: `gcloud artifacts repositories list --project=prod-microservices-473214`.

---

### 6. Formato del documento de liquidación cambió (SALDO-PRECIO vs Liquidación de Pago)

**Síntoma:** La comisión se calcula sobre un valor erróneo; el sistema confunde el total
abonado por el comprador con el valor de adjudicación.

**Causa:** El sistema MAIA cambió el formato del documento fuente de "Liquidación de Pago"
a "SALDO - PRECIO". En el nuevo formato no siempre existe una columna en pesos para la
adjudicación, y el modelo de IA confundía la fila "ABONADO AL" (total pagado por el
comprador) con el valor de adjudicación.

**Solución implementada:**
1. El prompt de extracción reconoce ambos formatos (A y B) y prohíbe usar "ABONADO AL"
   como valor de adjudicación.
2. El cálculo siempre usa `UF adjudicada × valor UF del día` como fuente de verdad para
   la adjudicación en pesos (campo inequívoco en ambos formatos), y el valor extraído por
   la IA solo sirve como chequeo cruzado que genera una alerta si discrepa.
