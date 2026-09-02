/**
 * Phase 6 — greatshot (routes greatshot, greatshot-demo): per-user demo
 * analysis. The whole surface is auth-gated — 401 renders the sign-in
 * STATE, not a failure. The upload is the core write: a rejected demo
 * shows the scanner's OWN words verbatim (the 500 this used to be was
 * fixed on this branch and proven live with a junk file), and an accepted
 * one polls its status until the analysis lands.
 */
import { useRef, useState } from 'react';
import { Link, useParams } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { Cluster, Stack } from '../components/layout';
import { Absent, Lbl, Meta, Pending, SectionHead, Unavailable, figure } from '../components/ui';
import { ApiError } from '../lib/api';
import { mapLabel } from '../lib/maps';
import {
  uploadGreatshotDemo, useGreatshotDetail, useGreatshotList, useGreatshotStatus,
} from '../lib/queries';

function fmtClock(ms: number): string {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

export function GreatshotPage() {
  const qc = useQueryClient();
  const list = useGreatshotList();
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [pollingId, setPollingId] = useState<string | null>(null);
  const status = useGreatshotStatus(pollingId, pollingId != null);

  if (status.data && pollingId != null && !['uploaded', 'processing'].includes(status.data.status)) {
    setPollingId(null);
    void qc.invalidateQueries({ queryKey: ['greatshot-list'] });
  }

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
          <div data-parity="greatshot.upload">
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

          <div data-parity="greatshot.list">
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
