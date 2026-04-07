import { useState } from 'react';
import type { GravityResponse, SpaceCreatedResponse, EnablerResponse, LurkerResponse } from '../../api/types';

type Tab = 'gravity' | 'space' | 'enabler' | 'lurker';

const TABS: { key: Tab; label: string; color: string; activeBg: string }[] = [
  { key: 'gravity', label: 'GRAVITY', color: 'text-rose-400', activeBg: 'bg-rose-500/20 border-rose-400/40' },
  { key: 'space', label: 'SPACE', color: 'text-purple-400', activeBg: 'bg-purple-500/20 border-purple-400/40' },
  { key: 'enabler', label: 'ENABLER', color: 'text-teal-400', activeBg: 'bg-teal-500/20 border-teal-400/40' },
  { key: 'lurker', label: 'LURKER', color: 'text-cyan-400', activeBg: 'bg-cyan-500/20 border-cyan-400/40' },
];

function StatCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-white/[0.03] px-2 py-1.5">
      <div className="text-[10px] text-slate-500 uppercase tracking-wider">{label}</div>
      <div className="text-sm font-bold tabular-nums text-white">{value}</div>
    </div>
  );
}

function formatMs(ms: number): string {
  const s = Math.round(ms / 1000);
  const m = Math.floor(s / 60);
  return m > 0 ? `${m}m ${s % 60}s` : `${s}s`;
}

interface Props {
  gravity: GravityResponse | undefined;
  space: SpaceCreatedResponse | undefined;
  enabler: EnablerResponse | undefined;
  lurker: LurkerResponse | undefined;
}

export function InvisibleValuePanel({ gravity, space, enabler, lurker }: Props) {
  const [active, setActive] = useState<Tab>('gravity');

  const hasData =
    (gravity?.players?.length ?? 0) > 0 ||
    (space?.players?.length ?? 0) > 0 ||
    (enabler?.players?.length ?? 0) > 0 ||
    (lurker?.players?.length ?? 0) > 0;

  if (!hasData) return null;

  const activeTab = TABS.find((t) => t.key === active)!;

  return (
    <div>
      <div className="flex items-center gap-3 mb-3">
        <h3 className="text-xs text-slate-500 uppercase tracking-wider font-bold">Invisible Value</h3>
        <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${activeTab.activeBg} ${activeTab.color}`}>
          {activeTab.label}
        </span>
      </div>

      {/* Tabs */}
      <div className="flex gap-1.5 mb-4">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActive(tab.key)}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-all
              ${active === tab.key
                ? `${tab.activeBg} ${tab.color} border`
                : 'text-slate-500 hover:text-slate-300 bg-white/[0.02] border border-transparent hover:border-white/8'
              }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="glass-card rounded-[24px] p-5 border border-white/8">
        {active === 'gravity' && gravity?.players?.length ? (
          <div className="space-y-2">
            {gravity.players.map((p, i) => (
              <div
                key={p.guid_short}
                className="flex items-center gap-3 rounded-xl bg-white/[0.02] px-3 py-2.5 hover:bg-white/[0.04] transition-colors"
                style={{ animation: `fadeUp 0.3s ease-out ${i * 0.04}s both` }}
              >
                <span className="text-rose-400 font-bold text-lg tabular-nums w-12">{p.gravity_score.toFixed(0)}</span>
                <span className="text-sm text-white font-medium flex-1 truncate">{p.name}</span>
                <div className="flex gap-2">
                  <StatCell label="ENG" value={String(p.engagements)} />
                  <StatCell label="AVG ATK" value={p.avg_attackers.toFixed(1)} />
                  <StatCell label="ATTN" value={formatMs(p.total_attention_ms)} />
                </div>
              </div>
            ))}
          </div>
        ) : active === 'space' && space?.players?.length ? (
          <div className="space-y-2">
            {space.players.map((p, i) => (
              <div
                key={p.guid_short}
                className="flex items-center gap-3 rounded-xl bg-white/[0.02] px-3 py-2.5 hover:bg-white/[0.04] transition-colors"
                style={{ animation: `fadeUp 0.3s ease-out ${i * 0.04}s both` }}
              >
                <span className="text-purple-400 font-bold text-lg tabular-nums w-12">{(p.space_score * 100).toFixed(0)}%</span>
                <span className="text-sm text-white font-medium flex-1 truncate">{p.name}</span>
                <div className="flex gap-2">
                  <StatCell label="PROD" value={String(p.productive_deaths)} />
                  <StatCell label="WASTE" value={String(p.wasted_deaths)} />
                  <StatCell label="TM KILLS" value={String(p.teammate_kills_after)} />
                </div>
              </div>
            ))}
          </div>
        ) : active === 'enabler' && enabler?.players?.length ? (
          <div className="space-y-2">
            {enabler.players.map((p, i) => (
              <div
                key={p.guid_short}
                className="flex items-center gap-3 rounded-xl bg-white/[0.02] px-3 py-2.5 hover:bg-white/[0.04] transition-colors"
                style={{ animation: `fadeUp 0.3s ease-out ${i * 0.04}s both` }}
              >
                <span className="text-teal-400 font-bold text-lg tabular-nums w-12">{p.enabler_score.toFixed(1)}</span>
                <span className="text-sm text-white font-medium flex-1 truncate">{p.name}</span>
                <div className="flex gap-2">
                  <StatCell label="ENABLED" value={String(p.enabled_kills)} />
                  <StatCell label="CF" value={String(p.crossfire_assists)} />
                  <StatCell label="TRADE" value={String(p.trade_assists)} />
                </div>
              </div>
            ))}
          </div>
        ) : active === 'lurker' && lurker?.players?.length ? (
          <div className="space-y-2">
            {lurker.players.map((p, i) => (
              <div
                key={p.guid_short}
                className="flex items-center gap-3 rounded-xl bg-white/[0.02] px-3 py-2.5 hover:bg-white/[0.04] transition-colors"
                style={{ animation: `fadeUp 0.3s ease-out ${i * 0.04}s both` }}
              >
                <span className="text-cyan-400 font-bold text-lg tabular-nums w-12">{p.solo_pct.toFixed(0)}%</span>
                <span className="text-sm text-white font-medium flex-1 truncate">{p.name}</span>
                <div className="flex gap-2">
                  <StatCell label="SOLO" value={formatMs(p.solo_time_est_s * 1000)} />
                  <StatCell label="LIVES" value={String(p.tracks)} />
                  <StatCell label="ALIVE" value={formatMs(p.alive_ms)} />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500 text-center py-4">No data for this metric.</p>
        )}
      </div>
    </div>
  );
}
