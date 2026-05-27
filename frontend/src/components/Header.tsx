export default function Header() {
  return (
    <header className="bg-white border-b border-brand-gray-50 sticky top-0 z-10">
      <div className="max-w-5xl mx-auto px-6 py-3 flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-brand-orange-500 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">M</span>
          </div>
          <span className="font-bold text-brand-gray-500 text-base tracking-tight">Macal</span>
        </div>
        <div className="h-5 w-px bg-brand-gray-50" />
        <span className="text-brand-gray-300 text-sm font-medium">Liquidador de Pago a Mandantes</span>
      </div>
    </header>
  );
}
