/**
 * Phase 7 — the season card (route `wrapped`).
 *
 * Legacy draws this into a 1080×1920 canvas inside a full-screen overlay
 * (wrapped.js:21-102), opened by a chip on the player profile
 * (player-profile.js:683). Here it is a PAGE: docs/design/12 states the
 * convention twice — the story details modal became a page, and so did
 * upload-detail — and the new app has no overlay primitive anywhere in 32
 * routes precisely because of that decision.
 *
 * ⭐ The canvas stays. The point of Wrapped is an image you paste into
 * Discord, so the page renders the same 1080×1920 card and keeps both
 * exports. What changes is that the numbers are ALSO readable as text: a
 * canvas is invisible to a screen reader, and legacy offered no other way to
 * read them.
 */
import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router';
import { Cluster, Stack } from '../components/layout';
import { Absent, Lbl, Meta, Pending, SectionHead, Unavailable } from '../components/ui';
import { useWrapped } from '../lib/queries';
import type { WrappedSeason } from '../lib/types';

const W = 1080;
const H = 1920;

/** Legacy's rounded-rect helper (wrapped.js:167), unchanged. */
function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

/** A faithful port of `_drawWrapped` (wrapped.js:104-165), including every
 *  truncation: the name at 22 characters, a label at 22, a value at 16, a sub
 *  at 26, and at most 8 cards in two columns. Those caps are what keep the
 *  card from overflowing, so they are behaviour, not styling. */
export function drawWrapped(canvas: HTMLCanvasElement, data: WrappedSeason): boolean {
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d');
  // jsdom has no 2d context unless `canvas` is installed, and the render must
  // survive that — the page still shows every number as text.
  if (!ctx) return false;

  const g = ctx.createLinearGradient(0, 0, 0, H);
  g.addColorStop(0, '#0b1220');
  g.addColorStop(1, '#1e1b4b');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, W, H);

  ctx.textAlign = 'center';
  ctx.fillStyle = '#22d3ee';
  ctx.font = 'bold 56px sans-serif';
  ctx.fillText('SLOMIX WRAPPED', W / 2, 150);

  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 72px sans-serif';
  ctx.fillText(String(data.player_name ?? '').slice(0, 22), W / 2, 250);

  ctx.fillStyle = '#94a3b8';
  ctx.font = '40px sans-serif';
  ctx.fillText(String(data.season_name ?? data.season_id ?? ''), W / 2, 320);

  const cards = data.cards.slice(0, 8);
  const cols = 2;
  const padX = 70;
  const tileW = (W - padX * 2 - 40) / cols;
  const tileH = 300;
  const top = 420;
  ctx.textAlign = 'left';
  cards.forEach((c, i) => {
    const x = padX + (i % cols) * (tileW + 40);
    const y = top + Math.floor(i / cols) * (tileH + 30);
    ctx.fillStyle = 'rgba(255,255,255,0.05)';
    roundRect(ctx, x, y, tileW, tileH, 24);
    ctx.fill();
    ctx.fillStyle = '#64748b';
    ctx.font = 'bold 30px sans-serif';
    ctx.fillText(String(c.label ?? '').toUpperCase().slice(0, 22), x + 36, y + 70);
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 64px sans-serif';
    ctx.fillText(String(c.value ?? '').slice(0, 16), x + 36, y + 160);
    if (c.sub) {
      ctx.fillStyle = '#22d3ee';
      ctx.font = '32px sans-serif';
      ctx.fillText(String(c.sub).slice(0, 26), x + 36, y + 220);
    }
  });

  ctx.textAlign = 'center';
  ctx.fillStyle = '#64748b';
  ctx.font = '34px sans-serif';
  ctx.fillText('slomix.fyi', W / 2, H - 80);
  return true;
}

const actionStyle = {
  all: 'unset' as const, cursor: 'pointer', fontSize: 'var(--fs-caption)',
  letterSpacing: '0.06em', textTransform: 'uppercase' as const, color: 'var(--color-accent)',
};

export function WrappedPage() {
  const { guid } = useParams();
  const wrapped = useWrapped(guid);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [drawn, setDrawn] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const data = wrapped.data;
  const hasCards = data != null && data.cards.length > 0;

  useEffect(() => {
    if (!hasCards || canvasRef.current == null || data == null) return;
    setDrawn(drawWrapped(canvasRef.current, data));
  }, [data, hasCards]);

  // ⛔ Exports stay disabled until the canvas actually holds a card. Legacy
  // learnt this the same way (`_setExportEnabled(false)` before the fetch,
  // wrapped.js:65): a Download that produces a blank PNG is worse than no
  // button, because the user only finds out after pasting it.
  const canExport = hasCards && drawn;

  const download = () => {
    const canvas = canvasRef.current;
    if (canvas == null || data == null) return;
    const a = document.createElement('a');
    a.download = `slomix-wrapped-${(data.player_name ?? 'player').replace(/\s+/g, '_')}.png`;
    a.href = canvas.toDataURL('image/png');
    a.click();
  };

  const copy = async () => {
    const canvas = canvasRef.current;
    if (canvas == null) return;
    try {
      const blob = await new Promise<Blob | null>((res) => canvas.toBlob(res, 'image/png'));
      if (blob == null) { setNote('could not export the image — use download instead'); return; }
      await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
      setNote('copied — paste it into Discord');
    } catch {
      setNote('copy is not supported in this browser — use download instead');
    }
  };

  return (
    <Stack gap={6} style={{ paddingTop: 'var(--space-7)' }}>
      <Stack gap={2}>
        <Lbl>wrapped · season card</Lbl>
        <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: 'var(--track-title)', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
          {data?.player_name ?? 'a season, on one card'}
        </h1>
        {data?.season_name != null && <Meta>{data.season_name}</Meta>}
      </Stack>

      {wrapped.isPending && <Pending label="season card" />}
      {wrapped.isError && <Unavailable what="season card" />}
      {data != null && !hasCards && (
        <Absent block reason="no season data for this player yet — the card needs rounds played this season" />
      )}

      {hasCards && (
        <>
          {/* ⭐ The numbers as TEXT, first. A canvas is a picture to a screen
              reader; legacy offered no other way to read these. */}
          <div data-parity="wrapped.cards">
            <SectionHead label="the season" />
            <Stack gap={1} className="rows" style={{ marginTop: 'var(--space-2)' }}>
              {data.cards.map((c) => (
                <Cluster key={c.key} gap={4} justify="between" align="baseline" className="row" style={{ padding: 'var(--space-2) 0', flexWrap: 'wrap' }}>
                  <Lbl>{c.label}</Lbl>
                  <Cluster gap={3} align="baseline">
                    <span className="m" style={{ fontSize: 'var(--fs-row)' }}>{c.value}</span>
                    {c.sub != null && c.sub !== '' && <Meta>{c.sub}</Meta>}
                  </Cluster>
                </Cluster>
              ))}
            </Stack>
          </div>

          <div data-parity="wrapped.card">
            <SectionHead label="the shareable card" />
            <canvas ref={canvasRef} aria-label="Slomix Wrapped season card"
              style={{ width: '100%', maxWidth: 360, marginTop: 'var(--space-3)', borderRadius: 12, display: 'block' }} />
            <Cluster gap={4} align="baseline" style={{ marginTop: 'var(--space-3)', flexWrap: 'wrap' }}>
              <button type="button" style={actionStyle} disabled={!canExport} onClick={() => { void copy(); }}>copy image</button>
              <button type="button" style={actionStyle} disabled={!canExport} onClick={download}>download</button>
              {data.guid != null && <Link to={`/profile/${data.guid}`} style={actionStyle}>back to profile →</Link>}
            </Cluster>
            {!drawn && <Meta>the image could not be drawn here — the numbers above are the same card</Meta>}
            {note != null && <div style={{ marginTop: 'var(--space-2)' }}><Absent reason={note} /></div>}
          </div>
        </>
      )}
    </Stack>
  );
}
