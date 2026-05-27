import type { ResultadoLiquidacion } from "../lib/types";
import { fmtClp } from "../lib/api";

interface Props {
  resultado: ResultadoLiquidacion;
}

function Row({ label, value, bold }: { label: string; value: string; bold?: boolean }) {
  return (
    <div className={`flex justify-between items-center py-1.5 border-b border-brand-gray-50 last:border-0 ${bold ? "font-semibold" : ""}`}>
      <span className="text-sm text-brand-gray-300">{label}</span>
      <span className={`text-sm tabular-nums ml-4 text-right ${bold ? "text-brand-gray-500" : "text-brand-gray-400"}`}>{value}</span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="section-title">{title}</p>
      <div className="bg-white rounded-xl border border-brand-gray-50 px-4 py-1">{children}</div>
    </div>
  );
}

export default function ResultadoCard({ resultado }: Props) {
  const { identificacion: id, insumos, parametros: p, calculo: c, alertas } = resultado;

  const etqComision =
    p.tipo_comision === "Porcentaje" && c.comision_macal != null
      ? `Comisión Macal (${c.comision_macal}%)`
      : "Comisión Macal";

  const tramo = p.tramo_aplicado;
  const etqPremio = tramo
    ? `Premio Macal (${tramo.porcentaje}% sobre ${(tramo.base_uf_efectiva ?? tramo.base_uf).toFixed(2)} UF)`
    : "Premio Macal";

  return (
    <div className="space-y-5">
      {alertas.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-1">
          <p className="text-xs font-bold uppercase tracking-widest text-amber-600">Avisos</p>
          {alertas.map((a, i) => (
            <p key={i} className="text-sm text-amber-700">• {a}</p>
          ))}
        </div>
      )}

      <Section title="Identificación">
        <Row label="Mandante" value={id.mandante ?? "—"} />
        <Row label="Lote" value={String(id.numero_lote ?? "—")} />
        <Row label="Propiedad" value={id.propiedad ?? "—"} />
        <Row label="Comuna" value={id.comuna ?? "—"} />
        <Row label="Fecha subasta" value={id.fecha_subasta ?? "—"} />
      </Section>

      <Section title="Parámetros del mandato">
        <Row label="Tipo comisión" value={p.tipo_comision || "—"} />
        <Row label="% Comisión Macal" value={c.comision_macal != null ? `${c.comision_macal}%` : "No encontrado en PDF"} />
        <Row label="Premio" value={p.paga_premio ? "Sí" : "No"} />
        {tramo && (
          <Row
            label="Tramo aplicado"
            value={`${tramo.porcentaje}% sobre ${(tramo.base_uf_efectiva ?? tramo.base_uf).toFixed(2)} UF`}
          />
        )}
        <Row label="Tipo propiedad" value={p.tipo_propiedad ?? "no determinado"} />
      </Section>

      <Section title="Ingresos">
        <Row label="Abonado por comprador" value={fmtClp(insumos.abonos_comprador_pesos)} bold />
      </Section>

      {c.descuenta_gastos === "Sí" && (
        <Section title="Gastos">
          <Row label="Total gastos" value={fmtClp(c.deducciones_totales)} bold />
          <Row label={etqComision} value={fmtClp(c.comision)} />
          <Row label="IVA Comisión Macal" value={fmtClp(c.iva_comision)} />
          <Row label={etqPremio} value={fmtClp(c.premio)} />
          <Row label="IVA Premio Macal" value={fmtClp(c.iva_premio)} />
          <Row label="Publicidad" value={fmtClp(c.publicidad)} />
          <Row label="IVA Publicidad" value={fmtClp(c.iva_publicidad)} />
          <Row label="Costo Vale Vista" value={fmtClp(c.costo_vale_vista)} />
          <Row label="Costo Instrucciones Notariales" value={fmtClp(c.costo_instrucciones)} />
          <Row label="Costo Antecedentes Legales" value={fmtClp(c.costo_antecedentes)} />
        </Section>
      )}

      <Section title="Pago a Mandante">
        {c.vale_vista_var === "Sí" ? (
          <>
            <Row label="Total pago" value={fmtClp((c.monto_vale_vista ?? 0) + (c.saldo_por_pagar_al_vendedor ?? 0))} bold />
            <Row label="Vale Vista" value={fmtClp(c.monto_vale_vista)} />
            <Row label="Saldo a pagar" value={fmtClp(c.saldo_por_pagar_al_vendedor)} />
          </>
        ) : (
          <Row label="Saldo a pagar" value={fmtClp(c.saldo_por_pagar_al_vendedor)} bold />
        )}
      </Section>

      {c.descuenta_gastos === "No" && (
        <Section title="Gastos por pagar">
          <Row label="Total gastos" value={fmtClp(c.total_gastos)} bold />
          <Row label={etqComision} value={fmtClp(c.comision)} />
          <Row label="IVA Comisión Macal" value={fmtClp(c.iva_comision)} />
          <Row label={etqPremio} value={fmtClp(c.premio)} />
          <Row label="IVA Premio Macal" value={fmtClp(c.iva_premio)} />
          <Row label="Publicidad" value={fmtClp(c.publicidad)} />
          <Row label="IVA Publicidad" value={fmtClp(c.iva_publicidad)} />
          <Row label="Costo Vale Vista" value={fmtClp(c.costo_vale_vista)} />
          <Row label="Costo Instrucciones Notariales" value={fmtClp(c.costo_instrucciones)} />
          <Row label="Costo Antecedentes Legales" value={fmtClp(c.costo_antecedentes)} />
        </Section>
      )}

      <div className="bg-brand-orange-50 border-2 border-brand-orange-500 rounded-xl p-5 flex justify-between items-center">
        <span className="font-bold text-brand-orange-500 uppercase tracking-wide text-sm">
          Saldo Neto a Pagar
        </span>
        <span className="text-2xl font-bold text-brand-orange-500 tabular-nums">
          {fmtClp(c.saldo_por_pagar_al_vendedor)}
        </span>
      </div>
    </div>
  );
}
