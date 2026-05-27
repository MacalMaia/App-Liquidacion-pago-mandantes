export default function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-12">
      <div className="relative w-14 h-14">
        <div className="absolute inset-0 rounded-full border-4 border-brand-gray-50" />
        <div className="absolute inset-0 rounded-full border-4 border-brand-orange-500 border-t-transparent animate-spin" />
      </div>
      <div className="text-center">
        <p className="font-semibold text-brand-gray-400">Procesando con IA</p>
        <p className="text-sm text-brand-gray-200 mt-1">
          Claude está leyendo los documentos y calculando la liquidación…
        </p>
        <p className="text-xs text-brand-gray-100 mt-1">Esto puede tardar entre 10 y 30 segundos.</p>
      </div>
    </div>
  );
}
