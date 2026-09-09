/**
 * Phase 6 — greatshot (routes greatshot, greatshot-demo): per-user demo
 * analysis. The whole surface is auth-gated — 401 renders the sign-in
 * STATE, not a failure. The upload is the core write: a rejected demo
 * shows the scanner's OWN words verbatim (the 500 this used to be was
 * fixed on this branch and proven live with a junk file), and an accepted
 * one polls its status until the analysis lands.
 */
import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { Cluster, Stack } from '../components/layout';
import { Absent, Lbl, Meta, Pending, SectionHead, Unavailable, figure } from '../components/ui';
import { Panel } from '../components/Panel';
import { ApiError } from '../lib/api';
import { mapLabel } from '../lib/maps';
import {
  uploadGreatshotDemo, useGreatshotDetail, useGreatshotList, useGreatshotStatus,
  useGreatshotCrossref,
} from '../lib/queries';
import type { GreatshotCrossref, GreatshotItem } from '../lib/types';
import { utcStamp } from '../lib/utcStamp';

function fmtClock(ms: number): string {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}


// ---------------------------------------------------------------------------
// the section hubs
//
// The route has carried `:section?` since phase 6, but the page ignored it and
// always rendered the demo list — so `/greatshot/clips` and `/greatshot/renders`
// were reachable URLs showing the wrong thing. Legacy has four hubs
// (greatshot.js:77-95 normalises the section, :136/:160/:183 render them).
//
// ⭐ None of this needs a new endpoint. `GreatshotItem` already carries
// `highlight_count`, `render_job_count` and `rendered_count`, so every hub is a
// filtered view over the list the page already fetches. That is why this is a
// small change and not a slice: the data was there, the surface was not.
const SECTIONS = ['demos', 'highlights', 'clips', 'renders'] as const;
type Section = (typeof SECTIONS)[number];

function normaliseSection(raw: string | undefined): Section {
  return (SECTIONS as readonly string[]).includes(raw ?? '') ? (raw as Section) : 'demos';
}

/** One hub row: the demo, a count, and a way into it. Legacy caps every hub at
 *  12 (`.slice(0, 12)`) and so does this — a hub is a shortcut, not a list. */
function HubRows({ items, count, unit, empty }: {
  items: GreatshotItem[];
  count: (d: GreatshotItem) => number;
  unit: (d: GreatshotItem) => string;
  empty: string;
}) {
  const shown = items.filter((d) => count(d) > 0);
  if (shown.length === 0) return <div style={{ marginTop: 'var(--space-2)' }}><Absent reason={empty} /></div>;
  return (
    <Stack gap={1} className="rows" style={{ marginTop: 'var(--space-2)' }}>
      {shown.slice(0, 12).map((d) => (
        <Cluster key={d.id} gap={3} justify="between" align="baseline" className="row"
          style={{ padding: 'var(--space-2) 0', flexWrap: 'wrap' }}>
          <span className="m" style={{ minWidth: 0, overflowWrap: 'anywhere' }}>{d.filename || d.id}</span>
          <Cluster gap={4} align="baseline">
            <Lbl>{unit(d)}</Lbl>
            <Link to={`/greatshot/demo/${d.id}`} style={{ fontSize: 'var(--fs-caption)', letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--color-accent)' }}>
              open →
            </Link>
          </Cluster>
        </Cluster>
      ))}
    </Stack>
  );
}

export function GreatshotPage() {
  const qc = useQueryClient();
  const { section: rawSection } = useParams();
  const section = normaliseSection(rawSection);
  const list = useGreatshotList();
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [pollingId, setPollingId] = useState<string | null>(null);
  const status = useGreatshotStatus(pollingId, pollingId != null);
  const statusData = status.data;

  // A state transition is a commit-time event, not a render computation —
  // setState during render loops under StrictMode.
  useEffect(() => {
    if (statusData && pollingId != null && !['uploaded', 'processing'].includes(statusData.status)) {
      setPollingId(null);
      void qc.invalidateQueries({ queryKey: ['greatshot-list'] });
    }
  }, [statusData, pollingId, qc]);

  const anonymous = list.error instanceof ApiError && list.error.status === 401;

  const onUpload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploadError(null);
    try {
      const r = await uploadGreatshotDemo(file);
      setPollingId(r.demo_id);
      await qc.invalidateQueries({ queryKey: ['greatshot-list'] });
    } catch (e) {
      // The scanner's own rejection, verbatim (400); anything else honest.
      setUploadError(e instanceof ApiError && e.detail ? e.detail
        : e instanceof ApiError && e.status === 401 ? 'sign in with CONNECT ID to upload demos'
        : 'the upload did not go through');
    }
  };

  return (
    <Stack gap={6} style={{ paddingTop: 'var(--space-7)' }}>
      <Stack gap={2}>
        <Lbl>greatshot · demo analysis</Lbl>
        <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: 'var(--track-title)', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
          your demos, read closely
        </h1>
      </Stack>

      {anonymous ? (
        <Absent block reason="sign in with CONNECT ID — greatshot analyses YOUR demos, so it needs to know who you are" />
      ) : (
        <>
          {/* Legacy keeps the upload form INSIDE the demos panel
              (index.html:3450-3455), so it is not a page-level control and the
              other three sections must not show it. Checked in the markup
              rather than assumed — the first draft left it above the tabs. */}
          <div data-parity="greatshot.upload" hidden={section !== 'demos'}>
            <SectionHead label="add a demo" />
            <Cluster gap={4} align="baseline" style={{ marginTop: 'var(--space-3)' }}>
              <input ref={fileRef} type="file" accept=".dm_84,.dm_60" aria-label="demo file"
                style={{ fontSize: 'var(--fs-caption)' }} />
              <button type="button" onClick={onUpload}
                style={{ all: 'unset', cursor: 'pointer', fontSize: 'var(--fs-caption)', letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--color-accent)' }}>
                upload →
              </button>
            </Cluster>
            {uploadError && <div style={{ marginTop: 'var(--space-2)' }}><Absent reason={uploadError} /></div>}
            {pollingId != null && <Meta>analyzing… the list refreshes when the scanner is done</Meta>}
          </div>

          <div data-parity="greatshot.sections">
            <Cluster gap={4} align="baseline" style={{ flexWrap: 'wrap' }}>
              {SECTIONS.map((s) => (
                <Link key={s} to={s === 'demos' ? '/greatshot' : `/greatshot/${s}`}
                  aria-current={s === section ? 'page' : undefined}
                  style={{ fontSize: 'var(--fs-caption)', letterSpacing: '0.06em', textTransform: 'uppercase',
                    color: s === section ? 'var(--color-accent)' : 'var(--color-text-500)' }}>
                  {s}
                </Link>
              ))}
            </Cluster>
          </div>

          {section === 'highlights' && (
            <div data-parity="greatshot.highlights-hub">
              <SectionHead label="detected highlights" />
              {list.isPending && <Pending label="demos" />}
              {list.isError && <Unavailable what="demos" />}
              {list.data && <HubRows items={list.data.items} count={(d) => d.highlight_count}
                unit={(d) => `${figure(d.highlight_count)} highlights`}
                empty="no detected highlights yet — analyse a demo first" />}
            </div>
          )}

          {section === 'clips' && (
            <div data-parity="greatshot.clips-hub">
              <SectionHead label="clip candidates" />
              {list.isPending && <Pending label="demos" />}
              {list.isError && <Unavailable what="demos" />}
              {list.data && <HubRows items={list.data.items} count={(d) => d.highlight_count}
                unit={(d) => `${figure(d.highlight_count)} clip windows`}
                empty="no clip candidates yet — highlights appear after analysis" />}
            </div>
          )}

          {section === 'renders' && (
            <div data-parity="greatshot.renders-hub">
              <SectionHead label="render jobs" />
              {list.isPending && <Pending label="demos" />}
              {list.isError && <Unavailable what="demos" />}
              {list.data && <HubRows items={list.data.items} count={(d) => d.render_job_count}
                unit={(d) => `${figure(d.rendered_count)} rendered · ${figure(d.render_job_count)} jobs`}
                empty="no render jobs yet — queue rendering from a demo highlight" />}
            </div>
          )}

          <div data-parity="greatshot.list" hidden={section !== 'demos'}>
            <SectionHead label="the analyses" />
            {list.isPending && <Pending label="demos" />}
            {list.isError && !anonymous && <Unavailable what="demos" />}
            {list.data && (list.data.items.length === 0 ? (
              <div style={{ marginTop: 'var(--space-2)' }}>
                <Absent reason="no demos yet — upload one above and the scanner takes it from there" />
              </div>
            ) : (
              <Stack gap={1} className="rows" style={{ marginTop: 'var(--space-2)' }}>
                {list.data.items.map((d) => (
                  <Cluster key={d.id} gap={3} justify="between" align="baseline" className="row" style={{ padding: 'var(--space-2) 0', flexWrap: 'wrap' }}>
                    <Stack gap={1} style={{ minWidth: 0 }}>
                      <Link to={`/greatshot/demo/${d.id}`} style={{ fontSize: 'var(--fs-row)', color: 'inherit', textDecoration: 'none' }}>
                        {d.map != null ? mapLabel(d.map) : d.filename}
                      </Link>
                      <Meta>
                        {d.filename}
                        {d.duration_ms != null && <> · {fmtClock(d.duration_ms)}</>}
                        {d.mod != null && <> · {d.mod}</>}
                      </Meta>
                    </Stack>
                    <Meta>
                      {d.status}
                      {d.error != null && <> — {d.error}</>}
                      {d.highlight_count > 0 && <> · {figure(d.highlight_count)} highlights</>}
                    </Meta>
                  </Cluster>
                ))}
              </Stack>
            ))}
          </div>
        </>
      )}
    </Stack>
  );
}

/** The demo against the database: which round the matcher picked, how
 *  sure it is and on what, and one row per player with the demo's numbers
 *  beside the database's. The matcher goes by map, duration, winner and
 *  player overlap — not by date — so the recorded fixture pairs a demo
 *  named 2026-02-03 with a round of 2026-08-18 at 90 %; the panel shows the
 *  criteria so a reader can judge the match, not just its verdict. Demo
 *  numbers the scanner does not carry (damage, accuracy) come back null or
 *  0 and are printed as "—", never as measured. */
function Crossref({ demoId }: { demoId: string }) {
  const q = useGreatshotCrossref(demoId);
  const n = (v: number | null | undefined) => (v == null ? '—' : figure(v));
  return (
    <div data-parity="greatshot.crossref">
      <Panel<GreatshotCrossref>
        label="against the database"
        q={q}
        empty={q.data != null && !q.data.matched ? q.data.reason : 'no players to compare'}
        isEmpty={(d) => !d.matched || d.comparison.length === 0}
      >
        {(d) => d.matched ? (
          <Stack gap={2}>
            <Meta>
              {d.round.map_name != null ? mapLabel(d.round.map_name) : 'unknown map'} R{d.round.round_number}
              {d.round.round_date != null && <> · {d.round.round_date}</>}
              {d.round.gaming_session_id != null && <> · <Link to={`/session-detail/${d.round.gaming_session_id}`} style={{ color: 'var(--color-accent)' }}>session {d.round.gaming_session_id}</Link></>}
              {' · '}{figure(d.round.confidence)} % on {d.round.match_details.join(', ')}
              {/* the matched round's own facts (ledger 2026-09-09) */}
              {d.round.round_time != null && <> · file {String(d.round.round_time).length === 6 ? `${String(d.round.round_time).slice(0, 2)}:${String(d.round.round_time).slice(2, 4)}` : String(d.round.round_time)}</>}
              {d.round.duration_seconds != null && <> · {fmtClock(d.round.duration_seconds * 1000)} long</>}
              {d.round.player_count != null && <> · {figure(d.round.player_count)} players in the db</>}
              {d.round.winner_team != null && <> · won by {d.round.winner_team === 1 ? 'axis' : d.round.winner_team === 2 ? 'allies' : `team ${String(d.round.winner_team)}`}</>}
              {d.round.demo_round_index != null && <> · demo round #{figure(d.round.demo_round_index + 1)}</>}
            </Meta>
            <Stack gap={1} className="rows">
              {d.comparison.map((c, i) => (
                <Cluster key={`${c.demo_name ?? ''}:${c.db_name ?? ''}:${i}`} gap={3} justify="between" align="baseline" className="row" style={{ padding: 'var(--space-1) 0' }}>
                  <span style={{ fontSize: 'var(--fs-row)' }}>{c.demo_name ?? c.db_name}</span>
                  <Cluster gap={3} align="baseline">
                    <Meta>demo {n(c.demo_stats?.kills)} / {n(c.demo_stats?.deaths)}</Meta>
                    <span className="m" style={{ fontSize: 'var(--fs-small)' }}>db {n(c.db_stats?.kills)} / {n(c.db_stats?.deaths)}</span>
                    {!c.matched && <Meta>{c.db_stats == null ? 'not in the round' : 'not in the demo'}</Meta>}
                  </Cluster>
                </Cluster>
              ))}
            </Stack>
          </Stack>
        ) : null}
      </Panel>
    </div>
  );
}

export function GreatshotDemoPage() {
  const params = useParams();
  const demoId = params.demoId ?? null;
  const q = useGreatshotDetail(demoId);

  if (demoId == null) return <Absent block reason="no demo named" />;
  if (q.isPending) return <Pending label="analysis" />;
  if (q.isError || !q.data) {
    if (q.error instanceof ApiError && q.error.status === 401) {
      return <Absent block reason="sign in with CONNECT ID — this analysis belongs to its uploader" />;
    }
    return q.error instanceof ApiError && q.error.status === 404
      ? <Absent block reason="no analysis has this id" />
      : <Unavailable what="analysis" />;
  }
  const d = q.data;
  return (
    <Stack gap={6} style={{ paddingTop: 'var(--space-7)' }}>
      <Stack gap={2}>
        <Lbl>greatshot · {d.status}</Lbl>
        <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: 'var(--track-title)', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
          {typeof d.metadata.map === 'string' ? mapLabel(d.metadata.map) : d.filename}
        </h1>
        <Meta>
          {d.filename}
          {typeof d.metadata.duration_ms === 'number' && <> · {fmtClock(d.metadata.duration_ms)}</>}
          {typeof d.metadata.gametype_short === 'string' && <> · {d.metadata.gametype_short}</>}
        </Meta>
        {/* The rest of the header the scanner wrote (fetched and dropped until
            2026-09-09): the mod, the profile, the extension, the cross-reference
            to a stored round with its confidence and the evidence, the scan
            timings and the event count. */}
        <Meta>
          {typeof d.metadata.gametype === 'string' && <>{d.metadata.gametype} · </>}
          {typeof d.metadata.profile === 'string' && <>profile {d.metadata.profile} · </>}
          {typeof d.metadata.file_size_bytes === 'number' && <>{(d.metadata.file_size_bytes / 1048576).toFixed(1)} MB · </>}
          {d.metadata.header != null && typeof d.metadata.header === 'object' && typeof (d.metadata.header as { sequence?: unknown }).sequence === 'number' && <>header seq {figure((d.metadata.header as { sequence: number }).sequence)} · </>}
          {Array.isArray(d.metadata.rounds) && d.metadata.rounds.length > 0 && <>{figure(d.metadata.rounds.length)} round{d.metadata.rounds.length === 1 ? '' : 's'} in the demo ({(d.metadata.rounds as { winner?: string }[]).map((r) => r.winner ?? '?').join(', ')}) · </>}
          {typeof d.metadata.mod_version === 'string' && <>mod {d.metadata.mod_version} · </>}
          {typeof d.metadata.profile_name === 'string' && <>{d.metadata.profile_name} · </>}
          {typeof d.metadata.extension === 'string' && <>{d.metadata.extension} · </>}
          {/* "No round matched" is a RESULT of a finished analysis; before it
            * ran (uploaded, scanning) or after it failed the same absence means
            * "not measured" (Codex on #1003). */}
          {typeof d.metadata.matched_round_id === 'number'
            ? <>matched round #{figure(d.metadata.matched_round_id)}{typeof d.metadata.crossref_confidence === 'number' ? ` · crossref ${figure(d.metadata.crossref_confidence)} %` : ''}{Array.isArray(d.metadata.crossref_match_details) ? ` (${(d.metadata.crossref_match_details as string[]).join(', ')})` : ''}</>
            : d.status === 'analyzed' || d.status === 'analysed' || d.status === 'done'
              ? <>no stored round matched</>
              : d.status === 'failed' || d.error != null
                ? <>round match unavailable (the analysis failed)</>
                : <>round match pending ({d.status})</>}
          {d.processing_started_at != null && d.processing_finished_at != null && (
            <> · scanned in {figure(Math.round((Date.parse(d.processing_finished_at.replace(' ', 'T')) - Date.parse(d.processing_started_at.replace(' ', 'T'))) / 100) / 10)} s</>
          )}
          {d.analysis != null && typeof d.analysis.events_total === 'number' && <> · {figure(d.analysis.events_total)} events</>}
          {d.created_at != null && <> · uploaded {utcStamp(String(d.created_at))}</>}
          {d.analysis?.created_at != null && <> · analysed {utcStamp(String(d.analysis.created_at))}</>}
        </Meta>
        {/* The scanner's own counts and the events it listed (ledger 2026-09-09). */}
        {d.analysis?.stats != null && (
          <Meta>
            scanner counted {figure(Number((d.analysis.stats as { kill_count?: number }).kill_count ?? 0))} kills · {figure(Number((d.analysis.stats as { chat_count?: number }).chat_count ?? 0))} chat lines · {figure(Number((d.analysis.stats as { event_count?: number }).event_count ?? 0))} events
            {Array.isArray((d.analysis.stats as { top_killers?: { player: string; kills: number }[] }).top_killers) && <> · top killers {((d.analysis.stats as { top_killers: { player: string; kills: number }[] }).top_killers).slice(0, 3).map((k) => `${k.player} ${figure(k.kills)}`).join(', ')}</>}
          </Meta>
        )}
        {Array.isArray(d.analysis?.events) && d.analysis!.events.length > 0 && (
          <Meta>
            first events: {(d.analysis!.events as { type?: string; t_ms?: number; attacker?: string; message?: string; victim?: string }[]).slice(0, 5).map((e) => `${e.t_ms != null ? fmtClock(e.t_ms) : '?'} ${e.type ?? 'event'}${e.attacker ? ` ${e.attacker}` : ''}${e.victim ? ` → ${e.victim}` : ''}${e.message ? ` "${e.message}"` : ''}`).join(' · ')}
            {d.analysis!.events.length > 5 ? ` · +${figure(d.analysis!.events.length - 5)} more` : ''}
          </Meta>
        )}
        {d.error != null && <Absent reason={`the scanner stopped: ${d.error}`} />}
        {d.warnings.length > 0 && d.warnings.map((w) => <Meta key={w}>⚠ {w}</Meta>)}
      </Stack>

      <div data-parity="greatshot.highlights">
        <SectionHead label="highlights" aside={<span className="lbl">{figure(d.highlights.length)} found</span>} />
        {d.highlights.length === 0 ? (
          <div style={{ marginTop: 'var(--space-2)' }}>
            <Absent reason="the scanner found nothing highlight-worthy in this demo" />
          </div>
        ) : (
          <Stack gap={1} className="rows" style={{ marginTop: 'var(--space-2)' }}>
            {d.highlights.map((h) => (
              <Cluster key={h.id} gap={3} justify="between" align="baseline" className="row" style={{ padding: 'var(--space-1) 0', flexWrap: 'wrap' }}>
                <Stack gap={1} style={{ minWidth: 0 }}>
                  <span style={{ fontSize: 'var(--fs-row)' }}>
                    {h.type.replace(/_/g, ' ')}{h.player != null && <> · {h.player}</>}
                  </span>
                  {h.explanation != null && <Meta>{h.explanation}</Meta>}
                </Stack>
                <Cluster gap={3} align="baseline">
                  <Meta>{fmtClock(h.start_ms)}–{fmtClock(h.end_ms)}{h.score != null && <> · score {figure(h.score)}</>}{h.created_at != null && <> · cut {utcStamp(String(h.created_at))}</>}</Meta>
                  {/* clip_download and clip_demo_path come from the same row
                    * (greatshot.py get_greatshot_demo): both set or both null,
                    * so a "cut, not served" state cannot occur — the path is a
                    * ledger decision, not a branch (Codex on #1003). */}
                  {h.clip_download != null && (
                    <a href={h.clip_download} className="lbl" style={{ color: 'var(--color-accent)', textDecoration: 'none' }} title={h.clip_demo_path ?? undefined}>clip →</a>
                  )}
                </Cluster>
              </Cluster>
            ))}
          </Stack>
        )}
      </div>

      <div data-parity="greatshot.player-stats">
        <SectionHead label="players in the demo" aside={<span className="lbl">{figure(Object.keys(d.player_stats ?? {}).length)} seen</span>} />
        {Object.keys(d.player_stats ?? {}).length === 0 ? (
          <div style={{ marginTop: 'var(--space-2)' }}><Absent reason="the scanner recorded no per-player block for this demo" /></div>
        ) : (
          <Stack gap={1} className="rows" style={{ marginTop: 'var(--space-2)' }}>
            {Object.entries(d.player_stats ?? {}).map(([name, stats]) => (
              <Cluster key={name} gap={3} justify="between" align="baseline" className="row" style={{ padding: 'var(--space-1) 0', flexWrap: 'wrap' }}>
                <span style={{ fontSize: 'var(--fs-row)' }}>{name}</span>
                <Meta>
                  {/* A zero damage total beside a double-digit kill count is the
                    * scanner not recording damage for that player (the recording
                    * has .olz: 15 kills, 0 damage while others carry damage) —
                    * printed as "not recorded", never as a measured 0. */}
                  {Object.entries((stats ?? {}) as Record<string, unknown>)
                    .filter(([, v]) => typeof v === 'number' || typeof v === 'string')
                    .slice(0, 8)
                    .map(([k, v]) => {
                      const s = stats as Record<string, unknown>;
                      const fought = (typeof s.kills === 'number' && s.kills > 0) || (typeof s.deaths === 'number' && s.deaths > 0);
                      if (k.startsWith('damage') && v === 0 && fought) return `${k.replace(/_/g, ' ')} not recorded`;
                      return `${k.replace(/_/g, ' ')} ${typeof v === 'number' ? figure(v) : String(v)}`;
                    })
                    .join(' · ')}
                </Meta>
              </Cluster>
            ))}
          </Stack>
        )}
      </div>

      <Crossref demoId={d.id} />

      <Cluster gap={5}>
        <a href={d.downloads.json} className="m" style={{ color: 'var(--color-accent)', textDecoration: 'none', fontSize: 'var(--fs-caption)' }}>report.json →</a>
        <a href={d.downloads.txt} className="m" style={{ color: 'var(--color-text-400)', textDecoration: 'none', fontSize: 'var(--fs-caption)' }}>report.txt →</a>
      </Cluster>
    </Stack>
  );
}
