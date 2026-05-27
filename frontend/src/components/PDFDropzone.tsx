import { useCallback, useState } from "react";

interface Props {
  label: string;
  file: File | null;
  onChange: (f: File | null) => void;
}

export default function PDFDropzone({ label, file, onChange }: Props) {
  const [dragging, setDragging] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const dropped = e.dataTransfer.files[0];
      if (dropped && dropped.type === "application/pdf") onChange(dropped);
    },
    [onChange]
  );

  const handleInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(e.target.files?.[0] ?? null);
  };

  return (
    <label
      className={`relative flex flex-col items-center justify-center gap-2 w-full min-h-[120px] rounded-xl border-2 border-dashed cursor-pointer transition-colors ${
        dragging
          ? "border-brand-orange-500 bg-brand-orange-50"
          : file
          ? "border-brand-purple-500 bg-brand-purple-50"
          : "border-brand-gray-50 bg-white hover:border-brand-orange-300 hover:bg-brand-orange-50"
      }`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <input type="file" accept="application/pdf" className="sr-only" onChange={handleInput} />

      {file ? (
        <>
          <svg className="w-8 h-8 text-brand-purple-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-sm font-medium text-brand-purple-500">{file.name}</p>
          <p className="text-xs text-brand-gray-200">{(file.size / 1024).toFixed(1)} KB</p>
        </>
      ) : (
        <>
          <svg className="w-8 h-8 text-brand-gray-100" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <p className="text-sm font-semibold text-brand-gray-300">{label}</p>
          <p className="text-xs text-brand-gray-200">Arrastra aquí o haz clic para seleccionar</p>
        </>
      )}
    </label>
  );
}
