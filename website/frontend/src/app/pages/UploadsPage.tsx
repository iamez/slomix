/**
 * Phase 6 — the upload library (routes uploads, upload-detail).
 * Slice 1 (#888): the read surface — list with sort, popular tags, and the
 * detail with download/share links. Links are LINKS (the browser follows
 * them), never fetches.
 * Slice 2: uploading and deleting. The form checks the file against the
 * backend's own allowlist and per-category limits before a byte moves, then
 * takes the legacy split (uploads.js:341): at or under 50 MiB one POST with
 * XHR progress (the path that accepts a poster — slice 3), above it the
 * chunked uploader (lib/uploads/resumable.ts) with a cancel that DELETEs the
 * session. 401 on submit is the anonymous state, as on the greatshot page.
 * Delete on the detail is two clicks, inline — no window.confirm.
 */
import { useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router';
import { Cluster, Stack } from '../components/layout';
import { Absent, Lbl, Meta, Pending, Unavailable, figure } from '../components/ui';
import { ApiError } from '../lib/api';
import {
  deleteUpload, RESUMABLE_THRESHOLD, resumableUpload, uploadSingleShot,
  usePopularUploadTags, useUploadDetail, useUploadsList,
} from '../lib/queries';
import type { UploadCreated } from '../lib/types';

// Keys from the backend's own sort whitelist (uploads.py _UPLOAD_SORTS) —
// 'popular' was a guessed name and 400'd at runtime (Codex on #888).
const SORTS = [
  { key: 'newest', label: 'newest' },
  { key: 'downloads', label: 'most downloaded' },
  { key: 'size', label: 'largest' },
];

// Mirrors website/backend/services/upload_validators.py (ALLOWED_EXTENSIONS,
// SIZE_LIMITS) so the form can say no before a byte moves — the server is
// still the arbiter, and its sentence is what the user sees if they differ.
const CATEGORY_OF = new Map<string, string>([
  ['.cfg', 'config'], ['.hud', 'config'], ['.zip', 'archive'], ['.rar', 'archive'],
  ['.mp4', 'clip'], ['.avi', 'clip'], ['.mkv', 'clip'],
]);
const LIMIT_MB = new Map<string, number>([['config', 2], ['archive', 50], ['clip', 500]]);
const ALLOWED_SENTENCE = 'Allowed: .cfg .hud .zip .rar .mp4 .avi .mkv';
const RETENTION = [
  { value: '', label: 'keep forever' },
  { value: '7', label: '7 days' },
  { value: '30', label: '30 days' },
  { value: '90', label: '90 days' },
];

function bytes(n: number): string {
  if (n >= 1 << 30) return `${(n / (1 << 30)).toFixed(1)} GB`;
  if (n >= 1 << 20) return `${(n / (1 << 20)).toFixed(1)} MB`;
  if (n >= 1 << 10) return `${Math.round(n / (1 << 10))} KB`;
  return `${n} B`;
}

/** null when the file may go; otherwise the reason, in the backend's words
 *  where it has them (unsupported type) and a plain one where it does not
 *  (the size limit, which the server phrases with byte counts). */
export function preflight(file: File): string | null {
  const dot = file.name.lastIndexOf('.');
  const ext = dot >= 0 ? file.name.slice(dot).toLowerCase() : '';
  const category = CATEGORY_OF.get(ext);
  if (!category) return `Unsupported file type '${ext}'. ${ALLOWED_SENTENCE}`;
  if (file.size === 0) return 'Empty upload is not allowed.';
  const limitMb = LIMIT_MB.get(category) ?? 0;
  if (file.size > limitMb * 1024 * 1024) return `${bytes(file.size)} is over the ${limitMb} MB limit for ${category} files`;
  return null;
}

const actionStyle = {
  all: 'unset', cursor: 'pointer', fontSize: 'var(--fs-caption)', letterSpacing: '0.06em',
  textTransform: 'uppercase', padding: '0 var(--space-1)', color: 'var(--color-accent)',
} as const;
const fieldStyle = {
  background: 'transparent', border: '1px solid var(--color-rule-700)', color: 'var(--color-text-100)',
  fontSize: 'var(--fs-row)', padding: 'var(--space-1)', minWidth: 200,
} as const;

type Phase =
  | { kind: 'idle' }
  | { kind: 'uploading'; sent: number; total: number }
  | { kind: 'done'; result: UploadCreated }
  | { kind: 'failed'; words: string };

function UploadForm({ onUploaded }: { onUploaded: () => Promise<void> }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState('');
  const [retention, setRetention] = useState('');
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' });
  const abortRef = useRef<AbortController | null>(null);
  const problem = file ? preflight(file) : null;

  const submit = async () => {
    if (!file || problem) return;
    const ctl = new AbortController();
    abortRef.current = ctl;
    setPhase({ kind: 'uploading', sent: 0, total: file.size });
    const meta = { title, description, tags, retention_days: retention ? Number(retention) : null };
    const onProgress = (sent: number, total: number) => { setPhase({ kind: 'uploading', sent, total }); };
    try {
      const result = file.size > RESUMABLE_THRESHOLD
        ? await resumableUpload(file, meta, { onProgress, signal: ctl.signal })
        : await uploadSingleShot(file, meta, { onProgress, signal: ctl.signal });
      setPhase({ kind: 'done', result });
      setFile(null); setTitle(''); setDescription(''); setTags(''); setRetention('');
      if (fileRef.current) fileRef.current.value = '';
      await onUploaded();
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') {
        setPhase({ kind: 'failed', words: 'upload cancelled' });
      } else if (e instanceof ApiError) {
        setPhase({ kind: 'failed', words: e.detail ?? (e.status === 401 ? 'sign in with CONNECT ID to upload' : 'the upload did not go through') });
      } else {
        setPhase({ kind: 'failed', words: e instanceof Error && e.message ? e.message : 'the upload did not go through' });
      }
    } finally {
      abortRef.current = null;
    }
  };

  const uploading = phase.kind === 'uploading';
  return (
    <Stack gap={2} parity="uploads.form">
      <Cluster gap={3} align="baseline" style={{ flexWrap: 'wrap' }}>
        <input ref={fileRef} aria-label="file" type="file" disabled={uploading} style={{ fontSize: 'var(--fs-row)' }}
          onChange={(e) => { setFile(e.target.files?.[0] ?? null); setPhase({ kind: 'idle' }); }} />
        <input aria-label="title" placeholder="title" value={title} disabled={uploading} style={fieldStyle}
          onChange={(e) => { setTitle(e.target.value); }} />
        <input aria-label="tags" placeholder="tags, comma separated" value={tags} disabled={uploading} style={fieldStyle}
          onChange={(e) => { setTags(e.target.value); }} />
        <select aria-label="retention" value={retention} disabled={uploading} style={fieldStyle}
          onChange={(e) => { setRetention(e.target.value); }}>
          {RETENTION.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
        </select>
      </Cluster>
      <input aria-label="description" placeholder="description" value={description} disabled={uploading} style={{ ...fieldStyle, minWidth: 0 }}
        onChange={(e) => { setDescription(e.target.value); }} />
      <Cluster gap={4} align="baseline" style={{ flexWrap: 'wrap' }}>
        {file && !problem && !uploading && (
          <Meta>{file.name} · {bytes(file.size)} · {file.size > RESUMABLE_THRESHOLD ? 'in chunks' : 'in one go'}</Meta>
        )}
        {!uploading && (
          <button type="button" style={actionStyle} disabled={!file || problem != null}
            onClick={() => { void submit(); }} title="upload the chosen file">upload</button>
        )}
        {uploading && (
          <button type="button" style={actionStyle} onClick={() => { abortRef.current?.abort(); }} title="cancel this upload">cancel</button>
        )}
      </Cluster>
      {problem && <Absent reason={problem} />}
      {phase.kind === 'uploading' && (
        <Meta>
          uploading · {phase.total > 0 ? Math.round((phase.sent / phase.total) * 100) : 0} % · {bytes(phase.sent)} of {bytes(phase.total)}
        </Meta>
      )}
      {phase.kind === 'done' && (
        <Stack gap={1}>
          <Meta>
            uploaded {phase.result.filename} · <Link to={`/uploads/${encodeURIComponent(phase.result.upload_id)}`} style={{ color: 'var(--color-accent)' }}>open it →</Link>
          </Meta>
          {phase.result.warning && <Absent reason={phase.result.warning} />}
        </Stack>
      )}
      {phase.kind === 'failed' && <Absent reason={phase.words} />}
    </Stack>
  );
}

export function UploadsPage() {
  const qc = useQueryClient();
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
        <Meta>demos, configs and clips the community left here</Meta>
      </Stack>

      <UploadForm onUploaded={async () => { await qc.invalidateQueries({ queryKey: ['uploads'] }); }} />

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

function DeleteControl({ uploadId, label }: { uploadId: string; label: string }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [words, setWords] = useState<string | null>(null);
  const run = async () => {
    setBusy(true); setWords(null);
    try {
      await deleteUpload(uploadId);
      await qc.invalidateQueries({ queryKey: ['uploads'] });
      navigate('/uploads');
    } catch (e) {
      setWords(e instanceof ApiError && e.detail ? e.detail : 'the server did not delete it');
      setArmed(false);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Stack gap={1} parity="uploads.delete">
      <Cluster gap={3} align="baseline">
        {!armed
          ? <button type="button" style={actionStyle} onClick={() => { setArmed(true); }} title={`delete ${label}`}>delete</button>
          : (
            <>
              <button type="button" style={actionStyle} disabled={busy} onClick={() => { void run(); }} title="confirm the delete">really delete</button>
              <button type="button" style={actionStyle} disabled={busy} onClick={() => { setArmed(false); }} title="keep it">keep</button>
              <Meta>this cannot be undone</Meta>
            </>
          )}
      </Cluster>
      {words && <Absent reason={words} />}
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
      {d.can_delete && <DeleteControl uploadId={d.id} label={d.title || d.filename} />}
    </Stack>
  );
}
