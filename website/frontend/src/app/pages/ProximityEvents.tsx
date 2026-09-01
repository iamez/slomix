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
import { Stack } from '../components/layout';
import { Lbl, Meta, Pending, Unavailable, figure } from '../components/ui';
import { mapLabel } from '../lib/maps';
import { stripEtColors } from '../lib/names';
import {
  useProxEngagements, useProxEventDetail, useProxEvents,
} from '../lib/queries';
import { ProxPanel, ProxRow } from './proximityShared';

const NO_ROWS = 'no rows in this scope — proximity capture only covers sessions where the tracker ran';

type PathPoint = { x: number; y: number; time: number; event: string | null };

/** The doubly-serialised path: a JSON string when recorded, `[]` when the
 *  column was empty. Parsed behind a guard — a malformed string is an
 *  absent path, never a crash. */
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
  return arr.filter((p): p is PathPoint => {
    const q = p as PathPoint | null;
    return q != null && Number.isFinite(q.x) && Number.isFinite(q.y);
  });
}

function EventDetail({ eventId }: { eventId: number }) {
  const q = useProxEventDetail(eventId);
  if (q.isPending) return <Pending label="engagement" />;
  if (q.isError || !q.data) return <Unavailable what="engagement" />;
  const d = q.data;
  const path = parsePath(d.position_path);
  // The short form (zero times) carries attackers as the raw DB string.
  const attackers = Array.isArray(d.attackers) ? d.attackers : [];
  return (
    <Stack gap={2} style={{ padding: 'var(--space-2) 0 var(--space-3) var(--space-5)' }}>
      <Meta>
        {d.outcome ?? 'unknown outcome'} · {figure(d.total_damage ?? 0)} dmg
        {' · '}{figure(Math.round((d.duration_ms ?? 0) / 100) / 10)} s
        {d.is_crossfire && ' · crossfire'}
        {d.distance_traveled != null && <> · moved {figure(Math.round(d.distance_traveled))} u</>}
      </Meta>
      {attackers.map((a, i) => (
        <Meta key={a.guid ?? i}>
          {a.name ? stripEtColors(a.name) : (a.guid?.slice(0, 8) ?? 'unknown')}
          {' · '}{figure(a.hits)} hits · {figure(a.damage)} dmg
        </Meta>
      ))}
      {path.length >= 2 ? (
        (() => {
          const xs = path.map((p) => p.x); const ys = path.map((p) => p.y);
          const minX = Math.min(...xs); const spanX = Math.max(...xs) - minX;
          const minY = Math.min(...ys); const spanY = Math.max(...ys) - minY;
          const w = 320; const h = 160;
          const nx = (x: number) => (spanX === 0 ? 0.5 : (x - minX) / spanX);
          const ny = (y: number) => (spanY === 0 ? 0.5 : (y - minY) / spanY);
          const px = (x: number) => nx(x) * (w - 16) + 8;
          const py = (y: number) => h - (ny(y) * (h - 16) + 8);
          const dd = path.map((p, i) => `${i === 0 ? 'M' : 'L'}${px(p.x).toFixed(1)} ${py(p.y).toFixed(1)}`).join(' ');
          return (
            <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', maxWidth: w, border: '1px solid var(--color-rule-900)' }} role="img" aria-label="engagement path">
              <path d={dd} fill="none" stroke="var(--color-accent)" strokeWidth="1.2" />
              {path.map((p, i) => (
                <circle key={i} cx={px(p.x)} cy={py(p.y)} r="3"
                  fill={p.event === 'escape' ? 'var(--color-pos)' : p.event === 'hit' ? 'var(--color-neg)' : 'var(--color-text-400)'} />
              ))}
            </svg>
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
  const engagements = useProxEngagements(sessionDate);
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
        <ProxPanel label="engagements" aside="newest first · click a row for its record" q={events} empty={NO_ROWS} isEmpty={(d) => d.events.length === 0}>
          {(d) => (
            <Stack gap={1} className="rows">
              {d.events.map((e) => (
                <div key={e.id}>
                  <button
                    type="button"
                    onClick={() => setOpenId(openId === e.id ? null : e.id)}
                    aria-expanded={openId === e.id}
                    style={{ all: 'unset', cursor: 'pointer', display: 'block', width: '100%' }}
                  >
                    <ProxRow
                      name={`${e.target_name ? stripEtColors(e.target_name) : 'unknown'} · ${mapLabel(e.map)} r${e.round}`}
                      mid={`${e.outcome ?? '—'}${e.crossfire ? ' · crossfire' : ''}${e.attackers != null && e.attackers > 1 ? ` · ${figure(e.attackers)} attackers` : ''}`}
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
