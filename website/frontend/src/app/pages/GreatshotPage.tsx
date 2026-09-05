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
import { ApiError } from '../lib/api';
import { mapLabel } from '../lib/maps';
import {
  uploadGreatshotDemo, useGreatshotDetail, useGreatshotList, useGreatshotStatus,
} from '../lib/queries';
import type { GreatshotItem } from '../lib/types';

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
                  <Meta>{fmtClock(h.start_ms)}–{fmtClock(h.end_ms)}{h.score != null && <> · score {figure(h.score)}</>}</Meta>
                  {h.clip_download != null && (
                    <a href={h.clip_download} className="lbl" style={{ color: 'var(--color-accent)', textDecoration: 'none' }}>clip →</a>
                  )}
                </Cluster>
              </Cluster>
            ))}
          </Stack>
        )}
      </div>

      <Cluster gap={5}>
        <a href={d.downloads.json} className="m" style={{ color: 'var(--color-accent)', textDecoration: 'none', fontSize: 'var(--fs-caption)' }}>report.json →</a>
        <a href={d.downloads.txt} className="m" style={{ color: 'var(--color-text-400)', textDecoration: 'none', fontSize: 'var(--fs-caption)' }}>report.txt →</a>
      </Cluster>
    </Stack>
  );
}
