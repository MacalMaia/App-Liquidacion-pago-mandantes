import type { FormData } from "../lib/types";

interface Props {
  form: FormData;
  onChange: (f: FormData) => void;
}

type SiNo = "Sí" | "No" | "";

function SelectSiNo({
  label, value, onChange,
}: { label: string; value: SiNo; onChange: (v: SiNo) => void }) {
  return (
    <div>
      <label className="block text-xs font-medium text-brand-gray-300 mb-1">{label}</label>
      <div className="relative">
        <select
          className="select-field pr-8"
          value={value}
          onChange={(e) => onChange(e.target.value as SiNo)}
        >
          <option value="">—</option>
          <option value="Sí">Sí</option>
          <option value="No">No</option>
        </select>
        <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-brand-gray-200">▾</span>
      </div>
    </div>
  );
}

function MontoInput({ label, value, onChange, disabled }: {
  label: string; value: string; onChange: (v: string) => void; disabled: boolean;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-brand-gray-300 mb-1">{label}</label>
      <input
        type="number"
        className="input-field"
        placeholder="0"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        min={0}
      />
    </div>
  );
}

export default function ParametrosLegalesForm({ form, onChange }: Props) {
  const set = (key: keyof FormData, val: string) =>
    onChange({ ...form, [key]: val });

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {/* Vale Vista */}
      <SelectSiNo
        label="¿Pago incluye Vale Vista?"
        value={form.vale_vista}
        onChange={(v) => onChange({ ...form, vale_vista: v, costo_vale_vista: "", monto_vale_vista: "" })}
      />
      <MontoInput
        label="Costo Vale Vista (CLP)"
        value={form.costo_vale_vista}
        onChange={(v) => set("costo_vale_vista", v)}
        disabled={form.vale_vista !== "Sí"}
      />
      <MontoInput
        label="Monto Vale Vista (CLP)"
        value={form.monto_vale_vista}
        onChange={(v) => set("monto_vale_vista", v)}
        disabled={form.vale_vista !== "Sí"}
      />

      {/* Instrucciones */}
      <SelectSiNo
        label="¿Incluye Instrucciones Notariales?"
        value={form.instrucciones}
        onChange={(v) => onChange({ ...form, instrucciones: v, costo_instrucciones: "" })}
      />
      <MontoInput
        label="Costo Instrucciones (CLP)"
        value={form.costo_instrucciones}
        onChange={(v) => set("costo_instrucciones", v)}
        disabled={form.instrucciones !== "Sí"}
      />

      {/* Descuenta gastos */}
      <SelectSiNo
        label="¿Se descuentan gastos en liquidación?"
        value={form.descuenta_gastos}
        onChange={(v) => onChange({ ...form, descuenta_gastos: v })}
      />

      {/* Antecedentes */}
      <SelectSiNo
        label="¿Incluye Antecedentes Legales?"
        value={form.antecedentes}
        onChange={(v) => onChange({ ...form, antecedentes: v, costo_antecedentes: "" })}
      />
      <MontoInput
        label="Costo Antecedentes (CLP)"
        value={form.costo_antecedentes}
        onChange={(v) => set("costo_antecedentes", v)}
        disabled={form.antecedentes !== "Sí"}
      />
    </div>
  );
}
