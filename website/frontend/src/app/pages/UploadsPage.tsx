/**
 * Phase 6 — the upload library, slice 1 (routes uploads, upload-detail):
 * the read surface — list with sort and category, popular tags, and the
 * detail with download/share links. Links are LINKS (the browser follows
 * them), never fetches. The resumable upload flow and delete are slice 2;
 * can_delete is still read and rendered honestly so an uploader sees the
 * button-to-come exactly where it will live.
 */
import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { Cluster, Stack } from '../components/layout';
import { Absent, Lbl, Meta, Pending, Unavailable, figure } from '../components/ui';
import { ApiError } from '../lib/api';
import { usePopularUploadTags, useUploadDetail, useUploadsList } from '../lib/queries';

// Keys from the backend's own sort whitelist (uploads.py _UPLOAD_SORTS) —
// 'popular' was a guessed name and 400'd at runtime (Codex on #888).
const SORTS = [
  { key: 'newest', label: 'newest' },
  { key: 'downloads', label: 'most downloaded' },
  { key: 'size', label: 'largest' },
];

function bytes(n: number): string {
  if (n >= 1 << 30) return `${(n / (1 << 30)).toFixed(1)} GB`;
  if (n >= 1 << 20) return `${(n / (1 << 20)).toFixed(1)} MB`;
  if (n >= 1 << 10) return `${Math.round(n / (1 << 10))} KB`;
  return `${n} B`;
}

export function UploadsPage() {
  const [sort, setSort] = useState('newest');
  const [offset, setOffset] = useState(0);
  // No category UI in slice 1 — wiring state a user could never set was
  // an unreachable feature, not a feature (Codex on #888).
  const list = useUploadsList(sort, offset, null);
  const tags = usePopularUploadTags();

  return (
    <Stack gap={6} style={{ paddingTop: 'var(--space-7)' }}>
      <Stack gap={2}>
        <Lbl>library · uploads</Lbl>
        <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: 'var(--track-title)', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
          the shared shelf
        </h1>
        <Meta>demos, configs and clips the community left here — uploading arrives in slice 2</Meta>
      </Stack>

      <Cluster gap={4} align="baseline" style={{ flexWrap: 'wrap' }}>
        {SORTS.map((s) => (
          <button key={s.key} type="button" onClick={() => { setSort(s.key); setOffset(0); }} aria-pressed={sort === s.key}
            style={{ all: 'unset', cursor: 'pointer', fontSize: 'var(--fs-caption)', letterSpacing: '0.06em', textTransform: 'uppercase', color: sort === s.key ? 'var(--color-text-100)' : 'var(--color-text-400)' }}>
            {s.label}
          </button>
        ))}
      </Cluster>

      <div data-parity="uploads.list">
        {list.isPending && <Pending label="uploads" />}
        {list.isError && <Unavailable what="uploads" />}
        {list.data && (list.data.items.length === 0 ? (
          <Absent block reason="nothing on the shelf in this view" />
        ) : (
          <Stack gap={1} className="rows">
            {list.data.items.map((u) => (
              <Cluster key={u.id} gap={3} justify="between" align="baseline" className="row" style={{ padding: 'var(--space-2) 0', flexWrap: 'wrap' }}>
                <Stack gap={1} style={{ minWidth: 0 }}>
                  <Link to={`/uploads/${encodeURIComponent(u.id)}`} style={{ fontSize: 'var(--fs-row)', color: 'inherit', textDecoration: 'none' }}>
                    {u.title || u.filename}
                  </Link>
                  <Meta>
                    {u.category} · {bytes(u.file_size_bytes)} · {u.uploader_name}
                    {u.created_at != null && <> · {u.created_at.slice(0, 10)}</>}
                  </Meta>
                </Stack>
                <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-400)' }}>
                  {u.download_count != null ? `${figure(u.download_count)} downloads` : '—'}
                </span>
              </Cluster>
            ))}
            <Cluster gap={4} style={{ marginTop: 'var(--space-3)' }}>
              {offset > 0 && (
                <button type="button" onClick={() => setOffset(Math.max(0, offset - list.data!.limit))}
                  style={{ all: 'unset', cursor: 'pointer', fontSize: 'var(--fs-caption)', color: 'var(--color-accent)' }}>← newer</button>
              )}
              {offset + list.data.limit < list.data.total && (
                <button type="button" onClick={() => setOffset(offset + list.data!.limit)}
                  style={{ all: 'unset', cursor: 'pointer', fontSize: 'var(--fs-caption)', color: 'var(--color-accent)' }}>older →</button>
              )}
              <Meta>{figure(list.data.total)} files</Meta>
            </Cluster>
          </Stack>
        ))}
      </div>

      <div data-parity="uploads.tags">
        {tags.data && tags.data.length > 0 && (
          <Cluster gap={3} style={{ flexWrap: 'wrap' }}>
            {tags.data.map((t) => (
              <span key={t.tag} className="lbl" style={{ fontSize: 'var(--fs-caption)' }}>{t.tag} ({figure(t.count)})</span>
            ))}
          </Cluster>
        )}
      </div>
    </Stack>
  );
}

export function UploadDetailPage() {
  const params = useParams();
  const uploadId = params.uploadId ?? null;
  const q = useUploadDetail(uploadId);

  if (uploadId == null) return <Absent block reason="no upload named" />;
  if (q.isPending) return <Pending label="upload" />;
  if (q.isError || !q.data) {
    return q.error instanceof ApiError && q.error.status === 404
      ? <Absent block reason="no upload has this id — it may have expired and been cleaned up" />
      : <Unavailable what="upload" />;
  }
  const d = q.data;
  return (
    <Stack gap={5} style={{ paddingTop: 'var(--space-7)' }}>
      <Stack gap={2}>
        <Lbl>library · {d.category}</Lbl>
        <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: 'var(--track-title)', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
          {d.title || d.filename}
        </h1>
        <Meta>
          {d.filename} · {bytes(d.file_size_bytes)}
          {d.created_at != null && <> · uploaded {d.created_at.slice(0, 10)}</>} by {d.uploader_name}
          {d.download_count != null && <> · {figure(d.download_count)} downloads</>}
          {d.expires_at != null && <> · expires {d.expires_at.slice(0, 10)}</>}
        </Meta>
      </Stack>
      {d.description && <p style={{ maxWidth: '44em', margin: 0 }}>{d.description}</p>}
      {d.tags.length > 0 && (
        <Cluster gap={3} style={{ flexWrap: 'wrap' }}>
          {d.tags.map((t) => <span key={t} className="lbl" style={{ fontSize: 'var(--fs-caption)' }}>{t}</span>)}
        </Cluster>
      )}
      <Cluster gap={5}>
        <a href={d.download_url} className="m" style={{ color: 'var(--color-accent)', textDecoration: 'none' }}>download →</a>
        <a href={d.share_url} className="m" style={{ color: 'var(--color-text-400)', textDecoration: 'none' }}>share link</a>
      </Cluster>
      {d.can_delete && (
        <Meta>you uploaded this — deleting arrives with slice 2, in this exact spot</Meta>
      )}
    </Stack>
  );
}
