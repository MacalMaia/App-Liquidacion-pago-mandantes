import type { ResultadoLiquidacion, FormData } from "./types";

const BASE = import.meta.env.VITE_API_URL ?? "";

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

  const res = await fetch(`${BASE}/api/liquidar`, { method: "POST", body });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Error desconocido");
  }
  return res.json();
}

export async function descargarPDF(resultado: ResultadoLiquidacion): Promise<void> {
  const res = await fetch(`${BASE}/api/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(resultado),
  });
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
