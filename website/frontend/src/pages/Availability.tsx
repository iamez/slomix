import { useState, useMemo, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../components/PageHeader';
import { GlassPanel } from '../components/GlassPanel';
import { GlassCard } from '../components/GlassCard';
import { Skeleton } from '../components/Skeleton';
import { api } from '../api/client';
import { useAvailabilityAccess, useAvailabilityRange, useAvailabilitySettings, usePlanningState, useAuthMe } from '../api/hooks';
import type { AvailabilityDay, AvailabilityDayCounts, PlanningParticipant } from '../api/types';

// ── Constants ────────────────────────────────────────────────────────────────

const STATUS_META = {
  LOOKING:     { label: 'Looking',     short: 'LFG',  emoji: '\u{1F50D}', color: 'text-cyan-400',    bg: 'bg-cyan-500',    border: 'border-cyan-500/50',    idle: 'border-white/15 text-slate-300 hover:border-cyan-500/40' },
  AVAILABLE:   { label: 'Available',   short: 'IN',   emoji: '\u2705',    color: 'text-emerald-400', bg: 'bg-emerald-500', border: 'border-emerald-500/50', idle: 'border-white/15 text-slate-300 hover:border-emerald-500/40' },
  MAYBE:       { label: 'Maybe',       short: 'Maybe',emoji: '\u{1F914}', color: 'text-amber-400',   bg: 'bg-amber-500',   border: 'border-amber-500/50',   idle: 'border-white/15 text-slate-300 hover:border-amber-500/40' },
  NOT_PLAYING: { label: 'Not Playing', short: 'Out',  emoji: '\u274C',    color: 'text-rose-400',    bg: 'bg-rose-500',    border: 'border-rose-500/50',    idle: 'border-white/15 text-slate-300 hover:border-rose-500/40' },
} as const;

const STATUS_KEYS = ['LOOKING', 'AVAILABLE', 'MAYBE', 'NOT_PLAYING'] as const;
type StatusKey = typeof STATUS_KEYS[number];
const UPCOMING_DAYS = 7;

// ── Date Helpers ─────────────────────────────────────────────────────────────

function toISO(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
function parseISO(s: string): Date | null {
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
}
function addDays(d: Date, n: number) {
  const c = new Date(d);
  c.setDate(c.getDate() + n);
  return c;
}
function startOfMonth(d: Date) { return new Date(d.getFullYear(), d.getMonth(), 1); }
function isPast(iso: string) {
  const d = parseISO(iso);
  if (!d) return true;
  const today = new Date();
  return d < new Date(today.getFullYear(), today.getMonth(), today.getDate());
}
function formatDate(iso: string, opts: Intl.DateTimeFormatOptions) {
  const d = parseISO(iso);
  return d ? d.toLocaleDateString(undefined, opts) : iso;
}

// ── Sub-components ───────────────────────────────────────────────────────────

function StackedBar({ counts, total, className = 'h-1.5' }: { counts: AvailabilityDayCounts; total: number; className?: string }) {
  if (!total) return <div className={`${className} rounded-full bg-slate-800`} />;
  return (
    <div className={`flex ${className} rounded-full overflow-hidden bg-slate-800`}>
      {STATUS_KEYS.map((k) => {
        const pct = ((counts[k] || 0) / total * 100).toFixed(1);
        return <div key={k} className={STATUS_META[k].bg} style={{ width: `${pct}%` }} />;
      })}
    </div>
  );
}

function StatusButtons({ selected, dateIso, disabled, onSet }: {
  selected: string | null | undefined;
  dateIso: string;
  disabled: boolean;
  onSet: (date: string, status: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {STATUS_KEYS.map((k) => {
        const meta = STATUS_META[k];
        const isActive = selected === k;
        return (
          <button
            key={k}
            disabled={disabled}
            onClick={() => onSet(dateIso, k)}
            className={`px-2.5 py-1.5 rounded-lg text-[11px] font-bold border transition ${
              isActive ? `${meta.border} ${meta.color} bg-white/5` : meta.idle
            } ${disabled ? 'opacity-60 cursor-not-allowed' : ''}`}
          >
            {meta.short}
          </button>
        );
      })}
    </div>
  );
}

// ── Calendar ─────────────────────────────────────────────────────────────────

function CalendarGrid({ month, days, selectedDate, onSelect }: {
  month: Date;
  days: Map<string, AvailabilityDay>;
  selectedDate: string;
  onSelect: (iso: string) => void;
}) {
  const cells = useMemo(() => {
    const ms = startOfMonth(month);
    const gridStart = addDays(ms, -ms.getDay());
    return Array.from({ length: 42 }, (_, i) => {
      const d = addDays(gridStart, i);
      const iso = toISO(d);
      const entry = days.get(iso);
      const inMonth = d.getMonth() === month.getMonth();
      const isToday = iso === toISO(new Date());
      return { date: d, iso, entry, inMonth, isToday };
    });
  }, [month, days]);

  return (
    <div className="grid grid-cols-7 gap-1">
      {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d) => (
        <div key={d} className="text-center text-[10px] text-slate-500 font-bold py-1">{d}</div>
      ))}
      {cells.map(({ iso, date, entry, inMonth, isToday }) => {
        const total = entry?.total ?? 0;
        const counts = entry?.counts ?? { LOOKING: 0, AVAILABLE: 0, MAYBE: 0, NOT_PLAYING: 0 };
        const sel = selectedDate === iso;
        return (
          <button
            key={iso}
            onClick={() => onSelect(iso)}
            className={`rounded-xl border p-2 text-left transition min-h-[80px] ${
              inMonth ? 'bg-slate-950/40 border-white/10 hover:border-cyan-500/40' : 'bg-slate-950/20 border-white/5'
            } ${sel ? 'ring-2 ring-cyan-500/50 border-cyan-500/50' : ''} ${isToday ? 'shadow-[0_0_0_1px_rgba(16,185,129,0.45)]' : ''}`}
          >
            <div className="flex items-center justify-between">
              <span className={`text-xs font-semibold ${inMonth ? 'text-slate-100' : 'text-slate-600'}`}>
                {date.getDate()}
              </span>
              {total > 0 && <span className="text-[10px] text-slate-400">{total}</span>}
            </div>
            <div className="mt-2">
              <StackedBar counts={counts} total={total} />
            </div>
          </button>
        );
      })}
    </div>
  );
}

// ── Quick View ───────────────────────────────────────────────────────────────

function QuickView({ days, selectedDate, onSelect }: {
  days: Map<string, AvailabilityDay>;
  selectedDate: string;
  onSelect: (iso: string) => void;
}) {
  const upcoming = useMemo(() =>
    Array.from({ length: UPCOMING_DAYS }, (_, i) => {
      const d = addDays(new Date(), i);
      const iso = toISO(d);
      return { iso, entry: days.get(iso) };
    }),
  [days]);

  return (
    <div className="space-y-2">
      {upcoming.map(({ iso, entry }) => {
        const counts = entry?.counts ?? { LOOKING: 0, AVAILABLE: 0, MAYBE: 0, NOT_PLAYING: 0 };
        const total = entry?.total ?? 0;
        const sel = selectedDate === iso;
        return (
          <button
            key={iso}
            onClick={() => onSelect(iso)}
            className={`w-full rounded-xl border p-3 text-left transition ${
              sel ? 'border-cyan-500/50 bg-cyan-500/10' : 'border-white/10 bg-slate-950/30 hover:border-cyan-500/35'
            }`}
          >
            <div className="flex items-center justify-between mb-1">
              <div>
                <div className="text-xs font-bold text-white">{formatDate(iso, { weekday: 'short' })}</div>
                <div className="text-[11px] text-slate-500">{formatDate(iso, { month: 'short', day: 'numeric' })}</div>
              </div>
              <div className="text-[11px] text-slate-300">{total} total</div>
            </div>
            <div className="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px]">
              <span className="text-cyan-400">Looking: {counts.LOOKING}</span>
              <span className="text-emerald-400">Available: {counts.AVAILABLE}</span>
              <span className="text-amber-400">Maybe: {counts.MAYBE}</span>
              <span className="text-rose-400">Not playing: {counts.NOT_PLAYING}</span>
            </div>
            <div className="mt-2"><StackedBar counts={counts} total={total} /></div>
          </button>
        );
      })}
    </div>
  );
}

// ── Day Detail Panel ─────────────────────────────────────────────────────────

function DayDetailPanel({ dateIso, entry, canSubmit, saving, onSetStatus }: {
  dateIso: string;
  entry: AvailabilityDay | undefined;
  canSubmit: boolean;
  saving: boolean;
  onSetStatus: (date: string, status: string) => void;
}) {
  const counts = entry?.counts ?? { LOOKING: 0, AVAILABLE: 0, MAYBE: 0, NOT_PLAYING: 0 };
  const total = entry?.total ?? 0;
  const myStatus = entry?.my_status ?? null;
  const users = entry?.users_by_status;
  const past = isPast(dateIso);
  const canAct = canSubmit && !past && !saving;

  return (
    <GlassPanel>
      <div className="text-lg font-bold text-white">
        {formatDate(dateIso, { weekday: 'long', month: 'long', day: 'numeric' })}
      </div>
      <div className="text-[11px] text-slate-500 mt-1">{dateIso} &middot; {total} response{total !== 1 ? 's' : ''}</div>

      <div className="grid grid-cols-4 gap-2 mt-4">
        {STATUS_KEYS.map((k) => (
          <div key={k} className="rounded-lg border border-white/10 bg-slate-950/40 p-3 text-center">
            <div className="text-[10px] text-slate-500">{STATUS_META[k].short}</div>
            <div className={`text-2xl font-black ${STATUS_META[k].color}`}>{counts[k]}</div>
          </div>
        ))}
      </div>

      {canAct && (
        <div className="mt-4">
          <div className="text-[11px] text-slate-500 mb-2">Set your status</div>
          <StatusButtons selected={myStatus} dateIso={dateIso} disabled={saving} onSet={onSetStatus} />
        </div>
      )}
      {past && <div className="mt-4 text-[11px] text-slate-500">Past days are read-only.</div>}
      {!canSubmit && !past && <div className="mt-4 text-[11px] text-amber-400">Log in and link Discord to set availability.</div>}

      {users && (
        <div className="mt-4 space-y-1 text-xs text-slate-400">
          {STATUS_KEYS.map((k) => {
            const list = users[k];
            if (!list?.length) return null;
            return (
              <div key={k}>
                <span className={STATUS_META[k].color}>{STATUS_META[k].emoji} {STATUS_META[k].short}:</span>{' '}
                {list.slice(0, 8).map((u) => u.display_name).join(', ')}
              </div>
            );
          })}
        </div>
      )}
    </GlassPanel>
  );
}

// ── Planning Room ────────────────────────────────────────────────────────────

function PlanningRoom({ canSubmit, canPromote }: { canSubmit: boolean; canPromote: boolean }) {
  const { data: planning, refetch } = usePlanningState(canSubmit);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [suggestion, setSuggestion] = useState('');
  const [assignments, setAssignments] = useState<Map<number, string>>(new Map());

  const session = planning?.session;
  const participants = planning?.participants ?? [];
  const unlocked = planning?.unlocked ?? false;

  const doAction = useCallback(async (fn: () => Promise<unknown>, successMsg: string) => {
    setBusy(true);
    setMsg('');
    try {
      await fn();
      setMsg(successMsg);
      refetch();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : 'Action failed');
    } finally {
      setBusy(false);
    }
  }, [refetch]);

  if (!canSubmit) return null;
  if (!session && !unlocked) {
    return (
      <GlassCard>
        <div className="text-xs text-slate-500">
          Planning room locked. Waiting for Looking threshold: {planning?.session_ready?.looking_count ?? 0}/{planning?.session_ready?.threshold ?? 6}
        </div>
      </GlassCard>
    );
  }

  const canManage = canSubmit && session && (canPromote || planning?.viewer?.website_user_id === session.created_by_user_id);

  function cycleAssignment(userId: number) {
    setAssignments((prev) => {
      const next = new Map(prev);
      const cur = next.get(userId) ?? '';
      if (cur === 'A') next.set(userId, 'B');
      else if (cur === 'B') next.delete(userId);
      else next.set(userId, 'A');
      return next;
    });
  }

  function autoDraft() {
    const pool = participants.map((p) => p.user_id).filter(Boolean);
    for (let i = pool.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [pool[i], pool[j]] = [pool[j], pool[i]];
    }
    const next = new Map<number, string>();
    pool.forEach((id, idx) => next.set(id, idx % 2 === 0 ? 'A' : 'B'));
    setAssignments(next);
    setMsg('Auto draft generated. Save to persist.');
  }

  return (
    <GlassPanel>
      <div className="flex items-center justify-between">
        <div className="text-xs font-bold uppercase tracking-widest text-purple-400">Planning Room</div>
        {!session ? (
          <button
            disabled={busy}
            onClick={() => doAction(() => api.postPlanning('/today/create', {}), 'Planning room created.')}
            className="px-3 py-1.5 rounded-lg text-xs font-bold border border-purple-500/50 text-purple-400 hover:bg-purple-500/10 transition disabled:opacity-60"
          >
            Create Room
          </button>
        ) : (
          <button onClick={() => setOpen(!open)} className="text-xs text-slate-400 hover:text-white transition">
            {open ? 'Hide' : 'Open'}
          </button>
        )}
      </div>

      {session && <div className="text-[11px] text-slate-400 mt-1">Session for {session.date} ({participants.length} participants)</div>}
      {msg && <div className="text-[11px] text-cyan-400 mt-2">{msg}</div>}

      {open && session && (
        <div className="mt-4 space-y-4">
          {/* Participants */}
          <div className="space-y-1">
            <div className="text-[11px] text-slate-500 font-bold">Participants</div>
            {participants.map((p: PlanningParticipant) => (
              <div key={p.user_id} className="flex items-center justify-between rounded-lg border border-white/10 bg-slate-950/35 px-2.5 py-1.5">
                <span className="text-xs text-slate-200">{p.display_name}</span>
                <span className={`text-[11px] font-semibold ${
                  p.status === 'LOOKING' ? 'text-cyan-400' : p.status === 'AVAILABLE' ? 'text-emerald-400' : 'text-amber-400'
                }`}>{p.status}</span>
              </div>
            ))}
          </div>

          {/* Suggestions */}
          <div className="space-y-1">
            <div className="text-[11px] text-slate-500 font-bold">Suggestions</div>
            {(session.suggestions ?? []).map((s) => (
              <div key={s.id} className="rounded-lg border border-white/10 bg-slate-950/30 px-2.5 py-2">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-semibold text-slate-100">{s.name}</div>
                    <div className="text-[11px] text-slate-500">by {s.suggested_by_name}</div>
                  </div>
                  <div className="text-xs text-slate-300 font-semibold">{s.votes} vote{s.votes !== 1 ? 's' : ''}</div>
                </div>
                <button
                  disabled={busy}
                  onClick={() => doAction(() => api.postPlanning('/today/vote', { suggestion_id: s.id }), 'Vote saved.')}
                  className={`mt-2 px-2.5 py-1 rounded-lg text-[11px] font-bold border transition ${
                    s.voted_by_me ? 'border-purple-500/50 text-purple-400 bg-purple-500/10' : 'border-white/15 text-slate-300 hover:border-purple-500/40'
                  }`}
                >
                  {s.voted_by_me ? 'Voted' : 'Vote'}
                </button>
              </div>
            ))}
            <div className="flex gap-2 mt-2">
              <input
                value={suggestion}
                onChange={(e) => setSuggestion(e.target.value)}
                placeholder="Suggest a map..."
                className="flex-1 rounded-lg border border-white/10 bg-slate-950/50 px-2.5 py-1.5 text-xs text-white placeholder-slate-500 outline-none focus:border-purple-500/50"
              />
              <button
                disabled={busy || suggestion.length < 2}
                onClick={() => {
                  doAction(() => api.postPlanning('/today/suggestions', { name: suggestion }), 'Suggestion added.');
                  setSuggestion('');
                }}
                className="px-3 py-1.5 rounded-lg text-xs font-bold border border-purple-500/50 text-purple-400 hover:bg-purple-500/10 transition disabled:opacity-60"
              >
                Add
              </button>
            </div>
          </div>

          {/* Team Draft */}
          {canManage && (
            <div className="space-y-2">
              <div className="text-[11px] text-slate-500 font-bold">Team Draft</div>
              <div className="flex flex-wrap gap-1.5">
                {participants.map((p: PlanningParticipant) => {
                  const side = assignments.get(p.user_id) ?? '';
                  return (
                    <button
                      key={p.user_id}
                      onClick={() => cycleAssignment(p.user_id)}
                      className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border transition ${
                        side === 'A' ? 'border-cyan-500/50 text-cyan-400 bg-cyan-500/10' :
                        side === 'B' ? 'border-emerald-500/50 text-emerald-400 bg-emerald-500/10' :
                        'border-white/15 text-slate-300 bg-slate-950/40'
                      }`}
                    >
                      {p.display_name}{side ? ` · ${side}` : ''}
                    </button>
                  );
                })}
              </div>
              <div className="flex gap-2">
                <button onClick={autoDraft} className="px-3 py-1.5 rounded-lg text-xs font-bold border border-white/10 text-slate-300 hover:border-cyan-500/40 transition">
                  Auto Draft
                </button>
                <button
                  disabled={busy}
                  onClick={() => {
                    const sideA = participants.filter((p: PlanningParticipant) => assignments.get(p.user_id) === 'A').map((p: PlanningParticipant) => p.user_id);
                    const sideB = participants.filter((p: PlanningParticipant) => assignments.get(p.user_id) === 'B').map((p: PlanningParticipant) => p.user_id);
                    doAction(() => api.postPlanning('/today/teams', {
                      side_a: sideA, side_b: sideB,
                      captain_a: sideA[0] ?? null, captain_b: sideB[0] ?? null,
                    }), 'Teams saved.');
                  }}
                  className="px-3 py-1.5 rounded-lg text-xs font-bold border border-emerald-500/50 text-emerald-400 hover:bg-emerald-500/10 transition disabled:opacity-60"
                >
                  Save Teams
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </GlassPanel>
  );
}

// ── Preferences ──────────────────────────────────────────────────────────────

function PreferencesSection({ canSubmit }: { canSubmit: boolean }) {
  const { data: settings, refetch } = useAvailabilitySettings(canSubmit);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [discord, setDiscord] = useState(true);
  const [sound, setSound] = useState(true);
  const [synced, setSynced] = useState(false);

  // Sync local state when settings arrive
  if (settings && !synced) {
    setDiscord(settings.discord_notify);
    setSound(settings.get_ready_sound);
    setSynced(true);
  }

  if (!canSubmit || !settings) return null;

  async function save() {
    setSaving(true);
    setMsg('');
    try {
      await api.saveAvailabilitySettings({
        sound_enabled: sound,
        sound_cooldown_seconds: settings!.sound_cooldown_seconds,
        availability_reminders_enabled: settings!.availability_reminders_enabled,
        timezone: settings!.timezone,
        discord_notify: discord,
        telegram_notify: settings!.telegram_notify,
        signal_notify: settings!.signal_notify,
      });
      setMsg('Settings saved.');
      refetch();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  }

  return (
    <GlassCard>
      <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">Preferences</div>
      <div className="space-y-2">
        <label className="flex items-center gap-2 text-xs text-slate-300">
          <input type="checkbox" checked={discord} onChange={(e) => setDiscord(e.target.checked)} className="rounded" />
          Discord notifications
        </label>
        <label className="flex items-center gap-2 text-xs text-slate-300">
          <input type="checkbox" checked={sound} onChange={(e) => setSound(e.target.checked)} className="rounded" />
          Get-ready sound
        </label>
      </div>
      <button
        disabled={saving}
        onClick={save}
        className="mt-3 px-4 py-1.5 rounded-lg text-xs font-bold border border-cyan-500/50 text-cyan-400 hover:bg-cyan-500/10 transition disabled:opacity-60"
      >
        Save
      </button>
      {msg && <div className="mt-2 text-[11px] text-cyan-400">{msg}</div>}
    </GlassCard>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function Availability() {
  const today = toISO(new Date());
  const rangeFrom = today;
  const rangeTo = toISO(addDays(new Date(), 60));

  const { data: access, isLoading: accessLoading } = useAvailabilityAccess();
  const { data: range, isLoading: rangeLoading, refetch: refetchRange } = useAvailabilityRange(rangeFrom, rangeTo, access?.can_submit ?? false);
  const { data: auth } = useAuthMe();
  const qc = useQueryClient();

  const [selectedDate, setSelectedDate] = useState(today);
  const [month, setMonth] = useState(startOfMonth(new Date()));
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{ text: string; error: boolean } | null>(null);

  const dayMap = useMemo(() => {
    const m = new Map<string, AvailabilityDay>();
    for (const d of range?.days ?? []) m.set(d.date, d);
    return m;
  }, [range]);

  const canSubmit = access?.can_submit ?? false;
  const sessionReady = range?.session_ready;

  const handleSetStatus = useCallback(async (dateIso: string, status: string) => {
    if (!canSubmit || saving) return;
    setSaving(true);
    setStatusMsg(null);
    try {
      await api.setAvailability(dateIso, status);
      setStatusMsg({ text: `Saved ${STATUS_META[status as StatusKey]?.label ?? status} for ${dateIso}.`, error: false });
      refetchRange();
      qc.invalidateQueries({ queryKey: ['planning-state'] });
    } catch (e: unknown) {
      setStatusMsg({ text: e instanceof Error ? e.message : 'Save failed', error: true });
    } finally {
      setSaving(false);
    }
  }, [canSubmit, saving, refetchRange, qc]);

  if (accessLoading || rangeLoading) return <Skeleton variant="card" count={3} />;

  // Not authenticated
  if (!access?.authenticated || !auth) {
    return (
      <>
        <PageHeader title="Availability" subtitle="See when players are looking to play" />
        <div className="text-center py-16">
          <div className="text-4xl mb-4">{'\u{1F512}'}</div>
          <p className="text-slate-400 text-lg mb-4">Log in with Discord to set your availability and view the queue.</p>
          <a
            href="/auth/discord"
            className="inline-block px-6 py-2 rounded-xl bg-indigo-600 text-white font-bold text-sm hover:bg-indigo-500 transition"
          >
            Login with Discord
          </a>
        </div>
      </>
    );
  }

  const todayEntry = dayMap.get(today);
  const tomorrowIso = toISO(addDays(new Date(), 1));
  const tomorrowEntry = dayMap.get(tomorrowIso);

  return (
    <>
      <PageHeader title="Availability" subtitle="Coordinate game sessions with the community" />

      {statusMsg && (
        <div className={`mb-4 rounded-xl border px-4 py-2 text-sm ${
          statusMsg.error ? 'border-rose-500/30 bg-rose-500/10 text-rose-400' : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
        }`}>
          {statusMsg.text}
        </div>
      )}

      {/* Session Ready Banner */}
      {sessionReady?.ready && (
        <div className="mb-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3">
          <div className="text-sm font-bold text-emerald-400">Session Ready!</div>
          <div className="text-xs text-slate-300 mt-1">
            {sessionReady.looking_count}/{sessionReady.threshold} players marked Looking for {sessionReady.date}
          </div>
        </div>
      )}

      {/* Today + Tomorrow Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <GlassCard>
          <div className="flex items-start justify-between mb-3">
            <div>
              <div className="text-sm font-bold text-white">Today</div>
              <div className="text-[11px] text-slate-500">{formatDate(today, { weekday: 'short', month: 'short', day: 'numeric' })}</div>
            </div>
            <div className="text-[11px] text-slate-400">
              {todayEntry?.my_status ? `${STATUS_META[todayEntry.my_status as StatusKey]?.emoji ?? ''} ${STATUS_META[todayEntry.my_status as StatusKey]?.label ?? todayEntry.my_status}` : 'Not set'}
            </div>
          </div>
          {canSubmit && <StatusButtons selected={todayEntry?.my_status} dateIso={today} disabled={saving} onSet={handleSetStatus} />}
          <div className="text-[11px] text-slate-500 mt-3">{todayEntry?.total ?? 0} responses</div>
        </GlassCard>

        <GlassCard>
          <div className="flex items-start justify-between mb-3">
            <div>
              <div className="text-sm font-bold text-white">Tomorrow</div>
              <div className="text-[11px] text-slate-500">{formatDate(tomorrowIso, { weekday: 'short', month: 'short', day: 'numeric' })}</div>
            </div>
            <div className="text-[11px] text-slate-400">
              {tomorrowEntry?.my_status ? `${STATUS_META[tomorrowEntry.my_status as StatusKey]?.emoji ?? ''} ${STATUS_META[tomorrowEntry.my_status as StatusKey]?.label ?? tomorrowEntry.my_status}` : 'Not set'}
            </div>
          </div>
          {canSubmit && <StatusButtons selected={tomorrowEntry?.my_status} dateIso={tomorrowIso} disabled={saving} onSet={handleSetStatus} />}
          <div className="text-[11px] text-slate-500 mt-3">{tomorrowEntry?.total ?? 0} responses</div>
        </GlassCard>
      </div>

      {/* Main Layout: Quick View + Day Detail + Calendar */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Quick View */}
        <div>
          <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">Upcoming {UPCOMING_DAYS} Days</div>
          <QuickView days={dayMap} selectedDate={selectedDate} onSelect={setSelectedDate} />
        </div>

        {/* Center: Day Detail */}
        <div>
          <DayDetailPanel
            dateIso={selectedDate}
            entry={dayMap.get(selectedDate)}
            canSubmit={canSubmit}
            saving={saving}
            onSetStatus={handleSetStatus}
          />
        </div>

        {/* Right: Calendar + Prefs */}
        <div className="space-y-4">
          <GlassCard>
            <div className="flex items-center justify-between mb-3">
              <button onClick={() => setCalendarOpen(!calendarOpen)} className="text-xs font-bold uppercase tracking-widest text-slate-400 hover:text-white transition">
                {calendarOpen ? 'Close Calendar' : 'Open Calendar'}
              </button>
            </div>
            {calendarOpen && (
              <>
                <div className="flex items-center justify-between mb-3">
                  <button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))} className="text-slate-400 hover:text-white text-sm">&larr;</button>
                  <span className="text-sm font-semibold text-white">
                    {month.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}
                  </span>
                  <button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))} className="text-slate-400 hover:text-white text-sm">&rarr;</button>
                </div>
                <CalendarGrid month={month} days={dayMap} selectedDate={selectedDate} onSelect={setSelectedDate} />
              </>
            )}
          </GlassCard>
          <PreferencesSection canSubmit={canSubmit} />
        </div>
      </div>

      {/* Planning Room */}
      <div className="mt-6">
        <PlanningRoom canSubmit={canSubmit} canPromote={access?.can_promote ?? false} />
      </div>

      {/* Not linked warning */}
      {access?.authenticated && !access?.linked_discord && (
        <div className="mt-6 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-400">
          Link your Discord account to set availability and participate in planning.
        </div>
      )}
    </>
  );
}
