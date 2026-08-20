import type { ResultadoLiquidacion, FormData } from "./types";

const BASE = import.meta.env.VITE_API_URL ?? "";

// Si el backend responde 401 (sesión SSO expirada o ausente), redirige al login
// de Microsoft. Devuelve la respuesta intacta cuando no es 401.
function handleAuth(res: Response): Response {
  if (res.status === 401) {
    window.location.href = `${BASE}/auth/login`;
    throw new Error("Redirigiendo al inicio de sesión…");
  }
  return res;
}

export async function liquidar(
  mandatoFile: File,
  liquidacionFile: File,
  form: FormData
): Promise<ResultadoLiquidacion> {
  const body = new FormData();
  body.append("mandato", mandatoFile);
  body.append("liquidacion", liquidacionFile);
  body.append("vale_vista", form.vale_vista || "No");
  if (form.vale_vista === "Sí") {
    body.append("costo_vale_vista", form.costo_vale_vista || "0");
    body.append("monto_vale_vista", form.monto_vale_vista || "0");
  }
  body.append("instrucciones", form.instrucciones || "No");
  if (form.instrucciones === "Sí") {
    body.append("costo_instrucciones", form.costo_instrucciones || "0");
  }
  body.append("antecedentes", form.antecedentes || "No");
  if (form.antecedentes === "Sí") {
    body.append("costo_antecedentes", form.costo_antecedentes || "0");
  }
  body.append("descuenta_gastos", form.descuenta_gastos || "Sí");

  const res = handleAuth(
    await fetch(`${BASE}/api/liquidar`, {
      method: "POST",
      body,
      credentials: "include",
    })
  );
  if (!res.ok) {
    let msg = `Error ${res.status}`;
    try {
      const body = await res.text();
      try {
        const err = JSON.parse(body);
        const detail = err.detail;
        msg =
          typeof detail === "string"
            ? detail
            : Array.isArray(detail)
              ? detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join("; ")
              : body || res.statusText;
      } catch {
        msg = body.slice(0, 300) || res.statusText;
      }
    } catch {
      msg = res.statusText || `Error ${res.status}`;
    }
    throw new Error(msg || "Error desconocido");
  }
  return res.json();
}

export async function descargarPDF(resultado: ResultadoLiquidacion): Promise<void> {
  const res = handleAuth(
    await fetch(`${BASE}/api/pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(resultado),
      credentials: "include",
    })
  );
  if (!res.ok) throw new Error("Error generando PDF");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  // Usar el nombre que sugiere el Content-Disposition del servidor
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename=([^\s;]+)/);
  a.download = match ? match[1] : "preliquidacion.pdf";
  a.click();
  URL.revokeObjectURL(url);
}

export function fmtClp(v: number | null | undefined): string {
  if (v == null) return "$0";
  return "$" + Math.round(v).toLocaleString("es-CL");
}
