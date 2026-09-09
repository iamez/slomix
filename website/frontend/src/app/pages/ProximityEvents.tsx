/**
 * Phase 5, slice 6 — the engagement record (07 §B.2's last A-class
 * panels): the dispersion buckets, the events list, and the per-event
 * drill-down. One row opens at a time — a second open row would be a
 * second fetch for a comparison the panel does not draw. The position
 * path arrives as a JSON STRING inside the JSON —
 * parsed behind a guard, because a malformed string is an absent path,
 * never a crash.
 */
import { useState } from 'react';
import { Link } from 'react-router';
import { Stack } from '../components/layout';
import { Lbl, Meta, Pending, Unavailable, figure } from '../components/ui';
import { mapLabel } from '../lib/maps';
import { mmss } from '../components/RoundsTable';
import { stripEtColors } from '../lib/names';
import {
  useProxEngagements, useProxEventDetail, useProxEvents,
} from '../lib/queries';
import type { ProxEventAttacker } from '../lib/types';
import { ProxPanel, ProxRow } from './proximityShared';
import { utcStamp } from '../lib/utcStamp';

const NO_ROWS = 'no rows in this scope — proximity capture only covers sessions where the tracker ran';

/** round_time in its two live spellings ('215233' and '21:52:33') — strip
 *  the colons FIRST, then pad ('4918' means 0:49:18), the order the
 *  round_time RCA fixed four times the other way around. */
function fmtRoundTime(raw: string | null): string | null {
  if (!raw) return null;
  const digits = raw.replace(/\D/g, '');
  if (digits.length < 3 || digits.length > 6) return null;
  const s = digits.padStart(6, '0');
  return `${s.slice(0, 2)}:${s.slice(2, 4)}`;
}

type PathPoint = { x: number; y: number; event: string | null; time: number | null; z: number | null; health: number | null; speed: number | null; sprint: number | null; stance: number | null; weapon: number | null };

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);

/** The doubly-serialised path: a JSON string when recorded, `[]` when the
 *  column was empty. Parsed behind a guard — a malformed string is an
 *  absent path, never a crash. The output claims exactly what was
 *  checked: finite x/y, event normalised to string-or-null. */
function parsePath(raw: string | unknown[]): PathPoint[] {
  let arr: unknown;
  if (Array.isArray(raw)) {
    arr = raw;
  } else {
    try {
      arr = JSON.parse(raw);
    } catch {
      return [];
    }
  }
  if (!Array.isArray(arr)) return [];
  return arr.flatMap((p) => {
    const q = p as { x?: unknown; y?: unknown; event?: unknown; time?: unknown; z?: unknown; health?: unknown; speed?: unknown; sprint?: unknown; stance?: unknown; weapon?: unknown } | null;
    if (q == null || typeof q.x !== 'number' || !Number.isFinite(q.x)
      || typeof q.y !== 'number' || !Number.isFinite(q.y)) return [];
    // The track-derived paths carry the sample's state too (ledger 2026-09-10).
    return [{ x: q.x, y: q.y, event: typeof q.event === 'string' ? q.event : null,
      time: num(q.time), z: num(q.z), health: num(q.health), speed: num(q.speed), sprint: num(q.sprint), stance: num(q.stance), weapon: num(q.weapon) }];
  });
}

/** The short form (zero-length times) skips the handler's parse branch and
 *  ships `attackers` as the raw DB string — with real attacker records
 *  inside (recorded: event 306062). Parse it the way position_path is
 *  parsed, normalising only the fields this panel draws. */
function parseAttackers(raw: string | ProxEventAttacker[]): ProxEventAttacker[] {
  let arr: unknown;
  if (Array.isArray(raw)) {
    arr = raw;
  } else {
    try {
      arr = JSON.parse(raw);
    } catch {
      return [];
    }
  }
  if (!Array.isArray(arr)) return [];
  return arr.flatMap((a) => {
    const o = a as Partial<ProxEventAttacker> | null;
    if (o == null || typeof o !== 'object') return [];
    return [{
      guid: typeof o.guid === 'string' ? o.guid : null,
      name: typeof o.name === 'string' ? o.name : null,
      team: typeof o.team === 'string' ? o.team : null,
      hits: typeof o.hits === 'number' ? o.hits : 0,
      damage: typeof o.damage === 'number' ? o.damage : 0,
      weapons: o.weapons != null && typeof o.weapons === 'object' ? o.weapons : {},
      // the hit window and the kill flag travel on both wire shapes (Codex on #1004)
      first_hit_ms: typeof o.first_hit_ms === 'number' ? o.first_hit_ms : null,
      last_hit_ms: typeof o.last_hit_ms === 'number' ? o.last_hit_ms : null,
      got_kill: typeof o.got_kill === 'boolean' ? o.got_kill : undefined,
    }];
  });
}

function EventDetail({ eventId }: { eventId: number }) {
  const q = useProxEventDetail(eventId);
  if (q.isPending) return <Pending label="engagement" />;
  if (q.isError || !q.data) return <Unavailable what="engagement" />;
  const d = q.data;
  // The legacy drill-down's precedence: the track-derived target_path when
  // the backend computed a nonempty one, else the stored position_path.
  const path = parsePath(
    Array.isArray(d.target_path) && d.target_path.length > 0 ? d.target_path : d.position_path,
  );
  const attackerPath = parsePath(Array.isArray(d.attacker_path) ? d.attacker_path : []);
  const attackers = parseAttackers(d.attackers);
  const strafe = d.strafe ?? null;
  const strafeMoved = strafe != null
    && (strafe.target.total_distance > 0 || strafe.attacker.total_distance > 0);
  return (
    <Stack gap={2} style={{ padding: 'var(--space-2) 0 var(--space-3) var(--space-5)' }}>
      <Meta>
        {d.outcome ?? 'unknown outcome'} · {figure(d.total_damage ?? 0)} dmg
        {' · '}{figure(Math.round((d.duration_ms ?? 0) / 100) / 10)} s
        {d.is_crossfire && ' · crossfire'}
        {d.distance_traveled != null && <> · moved {figure(Math.round(d.distance_traveled))} u</>}
      </Meta>
      {/* The engagement's frame the drill-down used to drop (ledger 2026-09-10):
          who was targeted and on which side, when it ran on the round clock,
          from where to where, how many attackers, and the round's own date. */}
      <Meta>
        {d.target_name ? stripEtColors(d.target_name) : (d.target_guid?.slice(0, 8) ?? 'target unknown')}{d.target_team ? ` (${d.target_team.toLowerCase()})` : ''}
        {d.start_time_ms != null && d.end_time_ms != null && <> · {mmss(d.start_time_ms / 1000)}–{mmss(d.end_time_ms / 1000)} on the round clock</>}
        {d.start_x != null && d.start_y != null && d.end_x != null && d.end_y != null && <> · from {figure(Math.round(d.start_x))}, {figure(Math.round(d.start_y))} to {figure(Math.round(d.end_x))}, {figure(Math.round(d.end_y))}</>}
        {d.num_attackers != null && <> · {figure(d.num_attackers)} attacker{d.num_attackers === 1 ? '' : 's'}</>}
        {d.round_date != null && <> · {d.round_date}</>}
        {d.round_duration_seconds != null && <> · round lasted {mmss(d.round_duration_seconds)}</>}
      </Meta>
      {attackers.map((a, i) => (
        <Meta key={a.guid ?? i}>
          {a.name ? stripEtColors(a.name) : (a.guid?.slice(0, 8) ?? 'unknown')}
          {' · '}{figure(a.hits)} hits · {figure(a.damage)} dmg
          {a.first_hit_ms != null && a.last_hit_ms != null && <> · hit from {mmss(a.first_hit_ms / 1000)} to {mmss(a.last_hit_ms / 1000)}</>}
          {a.got_kill != null && <> · {a.got_kill ? 'got the kill' : 'no kill'}</>}
        </Meta>
      ))}
      {/* the same summary for both tracks: the target's samples carry the
        * same fields and were never printed (Codex on #1004) */}
      {[['target', path], ['attacker', attackerPath]].filter(([, pts]) => (pts as PathPoint[]).some((pt) => pt.health != null || pt.speed != null)).map(([who, pts]) => (
        <Meta key={who as string}>
          {who as string}'s samples — health {figure(Math.min(...(pts as PathPoint[]).filter((pt) => pt.health != null).map((pt) => pt.health!)))}–{figure(Math.max(...(pts as PathPoint[]).filter((pt) => pt.health != null).map((pt) => pt.health!)))}
          {' · '}speed up to {figure(Math.round(Math.max(0, ...(pts as PathPoint[]).filter((pt) => pt.speed != null).map((pt) => pt.speed!))))} u/s
          {' · '}sprinting {figure(Math.round(100 * (pts as PathPoint[]).filter((pt) => pt.sprint === 1).length / Math.max(1, (pts as PathPoint[]).filter((pt) => pt.sprint != null).length)))} % of samples
          {' · '}stance {Array.from(new Set((pts as PathPoint[]).map((pt) => pt.stance).filter((v): v is number => v != null))).map((v) => ({ 0: 'standing', 1: 'crouching', 2: 'prone' } as Record<number, string>)[v] ?? String(v)).join('/') || '—'}
          {' · '}weapons {Array.from(new Set((pts as PathPoint[]).map((pt) => pt.weapon).filter((v): v is number => v != null))).map((v) => `#${String(v)}`).join(' ') || '—'}
          {(() => { const zs = (pts as PathPoint[]).map((pt) => pt.z).filter((v): v is number => v != null); return zs.length > 0 ? ` · height ${figure(Math.round(Math.min(...zs)))}–${figure(Math.round(Math.max(...zs)))}` : ''; })()}
          {(() => { const ts = (pts as PathPoint[]).map((pt) => pt.time).filter((v): v is number => v != null); return ts.length > 1 ? ` · ${figure(ts.length)} samples over ${figure(Math.round((Math.max(...ts) - Math.min(...ts)) / 100) / 10)} s` : ''; })()}
        </Meta>
      ))}
      {strafeMoved && strafe != null && (
        <Meta>
          movement — target {figure(Math.round(strafe.target.avg_speed))} u/s
          {' · '}{figure(strafe.target.turn_count)} turns; attacker{' '}
          {figure(Math.round(strafe.attacker.avg_speed))} u/s
          {' · '}{figure(strafe.attacker.turn_count)} turns
        </Meta>
      )}
      {path.length >= 2 ? (
        (() => {
          // Both tracks share ONE normalisation — separate bounds would
          // make the target and attacker incomparable on the same canvas.
          const all = attackerPath.length >= 2 ? [...path, ...attackerPath] : path;
          const xs = all.map((p) => p.x); const ys = all.map((p) => p.y);
          const minX = Math.min(...xs); const spanX = Math.max(...xs) - minX;
          const minY = Math.min(...ys); const spanY = Math.max(...ys) - minY;
          const w = 320; const h = 160;
          const nx = (x: number) => (spanX === 0 ? 0.5 : (x - minX) / spanX);
          const ny = (y: number) => (spanY === 0 ? 0.5 : (y - minY) / spanY);
          const px = (x: number) => nx(x) * (w - 16) + 8;
          const py = (y: number) => h - (ny(y) * (h - 16) + 8);
          const dFor = (pts: PathPoint[]) => pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${px(p.x).toFixed(1)} ${py(p.y).toFixed(1)}`).join(' ');
          return (
            <>
              <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', maxWidth: w, border: '1px solid var(--color-rule-900)' }} role="img" aria-label="engagement path">
                <path d={dFor(path)} fill="none" stroke="var(--color-accent)" strokeWidth="1.2" />
                {attackerPath.length >= 2 && (
                  <path d={dFor(attackerPath)} fill="none" stroke="var(--color-text-400)" strokeWidth="1" strokeDasharray="4 3" />
                )}
                {path.map((p, i) => (
                  <circle key={i} cx={px(p.x)} cy={py(p.y)} r="3"
                    fill={p.event === 'escape' ? 'var(--color-pos)' : p.event === 'hit' ? 'var(--color-neg)' : 'var(--color-text-400)'} />
                ))}
              </svg>
              {attackerPath.length >= 2 && (
                <Lbl style={{ fontSize: 'var(--fs-caption)' }}>solid — target · dashed — attacker</Lbl>
              )}
            </>
          );
        })()
      ) : (
        <Meta>no position path was recorded for this engagement</Meta>
      )}
    </Stack>
  );
}

export function ProximityEvents({ sessionDate, mapName, roundNumber, roundStartUnix }: {
  sessionDate: string | null;
  mapName: string | null;
  roundNumber: number | null;
  roundStartUnix: number | null;
}) {
  const events = useProxEvents(sessionDate, mapName, roundNumber, roundStartUnix);
  const engagements = useProxEngagements(sessionDate, mapName, roundNumber, roundStartUnix);
  const [openId, setOpenId] = useState<number | null>(null);
  return (
    <Stack gap={6} style={{ marginTop: 'var(--space-6)' }}>
      <div data-parity="proximity.dispersion">
        <ProxPanel label="engagement volume" aside="per day, with crossfires" q={engagements} empty={NO_ROWS} isEmpty={(d) => d.buckets.length === 0}>
          {(d) => (
            <Stack gap={1} className="rows">
              {d.buckets.slice(0, 8).map((b) => (
                <ProxRow key={b.date} name={b.date} mid={`${figure(b.crossfires)} crossfires`} val={`${figure(b.engagements)} engagements`} />
              ))}
            </Stack>
          )}
        </ProxPanel>
      </div>

      <div data-parity="proximity.events">
        {/* The comparison link needs a round_id, which the scopes hierarchy
            does not carry — the events rows do. Derived, not re-fetched. */}
        {roundNumber != null && (() => {
          const rid = events.data?.events.find((e) => e.round_id != null)?.round_id ?? null;
          return rid != null ? (
            <div style={{ marginBottom: 'var(--space-2)' }}>
              <Link to={`/proximity/round/${rid}`} className="lbl" style={{ color: 'var(--color-accent)', textDecoration: 'none', marginRight: 'var(--space-4)' }}>
                round replay →
              </Link>
              <Link to={`/proximity/round/${rid}/teams`} className="lbl" style={{ color: 'var(--color-accent)', textDecoration: 'none' }}>
                team comparison for this round →
              </Link>
            </div>
          ) : null;
        })()}
        <ProxPanel label="engagements" aside="by round, latest in-round moments first · click a row for its record" q={events} empty={NO_ROWS} isEmpty={(d) => d.events.length === 0}>
          {(d) => (
            <Stack gap={1} className="rows">
              {(!d.ready && d.message) || d.generated_at ? <Meta>{!d.ready && d.message ? `${d.message} · ` : ''}{d.generated_at ? `computed ${utcStamp(d.generated_at)}` : ''}</Meta> : null}
              {d.events.map((e) => (
                <div key={e.id}>
                  <button
                    type="button"
                    onClick={() => setOpenId(openId === e.id ? null : e.id)}
                    aria-expanded={openId === e.id}
                    style={{ all: 'unset', cursor: 'pointer', display: 'block', width: '100%' }}
                  >
                    <ProxRow
                      name={`${e.target_name ? stripEtColors(e.target_name) : 'unknown'} · ${mapLabel(e.map)} r${e.round}${fmtRoundTime(e.round_time) != null ? ` · ${fmtRoundTime(e.round_time)}` : ''}`}
                      mid={`${e.outcome ?? '—'}${e.crossfire ? ' · crossfire' : ''}${e.attackers != null && e.attackers > 1 ? ` · ${figure(e.attackers)} attackers` : ''}${e.attacker_name ? ` · by ${stripEtColors(e.attacker_name)}${e.attacker_team ? ` (${e.attacker_team.toLowerCase()})` : ''}` : ''}${e.distance != null && e.distance > 0 ? ` · ${figure(Math.round(e.distance))} u` : ''}${e.reaction_ms != null && e.reaction_ms > 0 ? ` · reacted in ${figure(e.reaction_ms)} ms` : ''}`}
                      val={e.duration_ms != null ? `${figure(Math.round(e.duration_ms / 100) / 10)} s` : '—'}
                    />
                  </button>
                  {openId === e.id && <EventDetail eventId={e.id} />}
                </div>
              ))}
            </Stack>
          )}
        </ProxPanel>
      </div>
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
        the drill-down opens one engagement at a time — its path draws only
        when the tracker recorded one, and says so when it did not
      </Lbl>
    </Stack>
  );
}
