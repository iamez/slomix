interface Props {
  narrative: string;
}

export function NarrativePanel({ narrative }: Props) {
  if (!narrative) return null;

  return (
    <div
      className="rounded-2xl border-l-4 border-amber-500/60 bg-amber-950/10 px-6 py-5"
      style={{ animation: 'fadeUp 0.5s ease-out both' }}
    >
      <h3 className="text-xs text-amber-400/70 uppercase tracking-wider font-bold mb-2">
        Session Summary
      </h3>
      <p className="text-sm text-slate-300 italic leading-relaxed">
        {narrative}
      </p>
    </div>
  );
}
