import { useState } from "react";
import type { ResultadoLiquidacion, FormData } from "../lib/types";
import { liquidar, descargarPDF } from "../lib/api";
import PDFDropzone from "../components/PDFDropzone";
import ParametrosLegalesForm from "../components/ParametrosLegalesForm";
import ResultadoCard from "../components/ResultadoCard";
import LoadingState from "../components/LoadingState";

type Step = 1 | 2 | 3 | 4;

const STEPS = [
  { n: 1, label: "Cargar PDFs" },
  { n: 2, label: "Datos Legales" },
  { n: 3, label: "Calcular" },
  { n: 4, label: "Descargar" },
];

function Stepper({ current }: { current: Step }) {
  return (
    <div className="flex items-center gap-0 mb-8">
      {STEPS.map((s, i) => (
        <div key={s.n} className="flex items-center flex-1">
          <div className="flex flex-col items-center flex-1">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-colors ${
                s.n < current
                  ? "bg-brand-orange-500 text-white"
                  : s.n === current
                  ? "bg-brand-purple-500 text-white ring-4 ring-brand-purple-50"
                  : "bg-brand-gray-50 text-brand-gray-200"
              }`}
            >
              {s.n < current ? (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                s.n
              )}
            </div>
            <span
              className={`text-xs mt-1 font-medium whitespace-nowrap ${
                s.n === current ? "text-brand-purple-500" : s.n < current ? "text-brand-orange-500" : "text-brand-gray-100"
              }`}
            >
              {s.label}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <div className={`h-0.5 flex-1 mx-1 mb-5 transition-colors ${s.n < current ? "bg-brand-orange-500" : "bg-brand-gray-50"}`} />
          )}
        </div>
      ))}
    </div>
  );
}

const FORM_DEFAULT: FormData = {
  vale_vista: "",
  costo_vale_vista: "",
  monto_vale_vista: "",
  instrucciones: "",
  costo_instrucciones: "",
  antecedentes: "",
  costo_antecedentes: "",
  descuenta_gastos: "",
};

export default function Liquidador() {
  const [step, setStep] = useState<Step>(1);
  const [mandatoFile, setMandatoFile] = useState<File | null>(null);
  const [liquidacionFile, setLiquidacionFile] = useState<File | null>(null);
  const [form, setForm] = useState<FormData>(FORM_DEFAULT);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultado, setResultado] = useState<ResultadoLiquidacion | null>(null);

  const canGoToStep2 = mandatoFile && liquidacionFile;
  const canCalcular = form.descuenta_gastos !== "" && form.vale_vista !== "" && form.instrucciones !== "" && form.antecedentes !== "";

  async function handleCalcular() {
    if (!mandatoFile || !liquidacionFile) return;
    setLoading(true);
    setError(null);
    try {
      const res = await liquidar(mandatoFile, liquidacionFile, form);
      setResultado(res);
      setStep(4);
    } catch (e: any) {
      setError(e.message ?? "Error desconocido");
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    setStep(1);
    setMandatoFile(null);
    setLiquidacionFile(null);
    setForm(FORM_DEFAULT);
    setResultado(null);
    setError(null);
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <Stepper current={step} />

      {/* Step 1 — Cargar PDFs */}
      {step === 1 && (
        <div className="card space-y-4">
          <h2 className="font-bold text-lg text-brand-gray-500">Cargar documentos</h2>
          <p className="text-sm text-brand-gray-200">
            Sube el mandato notarial y la liquidación de pago.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <p className="text-xs font-medium text-brand-gray-300 mb-2">Mandato Notarial</p>
              <PDFDropzone label="Mandato notarial" file={mandatoFile} onChange={setMandatoFile} />
            </div>
            <div>
              <p className="text-xs font-medium text-brand-gray-300 mb-2">Liquidación de Pago (MAIA)</p>
              <PDFDropzone label="Liquidación de Pago" file={liquidacionFile} onChange={setLiquidacionFile} />
            </div>
          </div>
          <div className="flex justify-end pt-2">
            <button
              className="btn-primary"
              disabled={!canGoToStep2}
              onClick={() => setStep(2)}
            >
              Siguiente →
            </button>
          </div>
        </div>
      )}

      {/* Step 2 — Datos Legales */}
      {step === 2 && (
        <div className="card space-y-4">
          <h2 className="font-bold text-lg text-brand-gray-500">Datos desde Legal</h2>
          <p className="text-sm text-brand-gray-200">
            Completa los valores que no están en los PDFs.
          </p>
          <ParametrosLegalesForm form={form} onChange={setForm} />
          <div className="flex justify-between pt-2">
            <button className="btn-secondary" onClick={() => setStep(1)}>← Volver</button>
            <button
              className="btn-primary"
              disabled={!canCalcular}
              onClick={() => setStep(3)}
            >
              Siguiente →
            </button>
          </div>
        </div>
      )}

      {/* Step 3 — Calcular */}
      {step === 3 && (
        <div className="card space-y-4">
          {loading ? (
            <LoadingState />
          ) : (
            <>
              <h2 className="font-bold text-lg text-brand-gray-500">Listo para calcular</h2>
              <div className="bg-brand-gray-50 rounded-lg p-4 space-y-1 text-sm">
                <p><span className="font-medium">Mandato:</span> {mandatoFile?.name}</p>
                <p><span className="font-medium">Liquidación:</span> {liquidacionFile?.name}</p>
                <p><span className="font-medium">Vale Vista:</span> {form.vale_vista || "—"}</p>
                <p><span className="font-medium">Descuenta gastos:</span> {form.descuenta_gastos || "—"}</p>
              </div>
              {error && (
                <div className="bg-red-50 border border-red-200 rounded-xl p-4">
                  <p className="text-xs font-bold uppercase tracking-widest text-red-600 mb-1">Error</p>
                  <p className="text-sm text-red-700">{error}</p>
                </div>
              )}
              <div className="flex justify-between pt-2">
                <button className="btn-secondary" onClick={() => setStep(2)}>← Volver</button>
                <button className="btn-primary" onClick={handleCalcular}>
                  Calcular liquidación
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {/* Step 4 — Resultado y descarga */}
      {step === 4 && resultado && (
        <div className="space-y-5">
          <div className="flex items-center justify-between">
            <h2 className="font-bold text-lg text-brand-gray-500">Resultado</h2>
            <div className="flex gap-2">
              <button
                className="btn-primary"
                onClick={() => descargarPDF(resultado)}
              >
                Descargar PDF
              </button>
              <button className="btn-secondary" onClick={handleReset}>
                Nueva liquidación
              </button>
            </div>
          </div>
          <ResultadoCard resultado={resultado} />
        </div>
      )}
    </div>
  );
}
