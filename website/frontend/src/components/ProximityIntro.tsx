import { useState } from 'react';
import { ChevronDown, ChevronUp, Info } from 'lucide-react';

const STORAGE_KEY = 'proximity-intro-dismissed';

export function ProximityIntro() {
  const [dismissed, setDismissed] = useState(() => {
    try { return localStorage.getItem(STORAGE_KEY) === '1'; } catch { return false; }
  });

  const dismiss = () => {
    setDismissed(true);
    try { localStorage.setItem(STORAGE_KEY, '1'); } catch { /* noop */ }
  };

  const restore = () => {
    setDismissed(false);
    try { localStorage.removeItem(STORAGE_KEY); } catch { /* noop */ }
  };

  if (dismissed) {
    return (
      <button
        onClick={restore}
        className="flex items-center gap-1.5 text-[11px] text-slate-500 hover:text-cyan-400 transition-colors mb-3"
      >
        <Info className="w-3.5 h-3.5" />
        How proximity tracking works
      </button>
    );
  }

  return (
    <div className="rounded-2xl border border-blue-500/20 bg-blue-500/5 p-5 mb-4">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2 text-xs text-slate-300 leading-relaxed">
          <p className="text-sm font-bold text-white flex items-center gap-2">
            <Info className="w-4 h-4 text-blue-400 shrink-0" />
            How Proximity Tracking Works
          </p>
          <p>
            A <span className="text-cyan-400">Lua tracker</span> running on the game server records every damage event,
            kill, and player position in real time. This raw data is parsed and stored in the database, then aggregated
            into the metrics you see below.
          </p>
          <p>
            <strong className="text-white">What&apos;s an engagement?</strong> A combat encounter that starts when a player
            deals {'>'}1 HP damage. It ends when one player dies, escapes (moves 300+ units away for 5 seconds), or the 15-second
            timeout expires.
          </p>
          <p>
            <strong className="text-white">Distance units:</strong> ET:Legacy uses game units (u). Roughly{' '}
            <span className="text-cyan-400">300 units &asymp; 5 meters</span> (one sprint-second). Sprint speed is ~300 u/s.
          </p>
          <p>
            Look for the <span className="inline-flex items-center text-slate-400"><Info className="w-3 h-3 mx-0.5" /></span> icons
            next to metrics for detailed explanations of what each number means and how it&apos;s measured.
          </p>
        </div>
        <button
          onClick={dismiss}
          className="shrink-0 text-slate-500 hover:text-white transition-colors"
          aria-label="Dismiss intro"
        >
          <ChevronUp className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
