import { useEffect, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';
import { Stack } from '../components/layout';
import { Absent, ActLink, Lbl, Pending, SectionHead, Unavailable } from '../components/ui';
import { useWrapped } from '../lib/queries';
import { CARD_H, CARD_W, drawWrapped, paletteFromDocument } from '../lib/wrappedCard';

/**
 * Slomix Wrapped (phase 7; legacy wrapped.js) — a season card a player can
 * paste into Discord. The legacy was an overlay opened from the profile;
 * this is a route, so the card has a link. The facts are drawn on a
 * 1080×1920 canvas (lib/wrappedCard.ts, the design rules pinned in its
 * test) AND listed as text beside it — the text is what a screen reader,
 * a test runner without a canvas, and a search engine get.
 *
 * Copy/download stay disabled until the card is drawn: a button that does
 * nothing must not look actionable (the legacy learned that the hard way).
 */
export function WrappedPage() {
  const { id = '' } = useParams();
  const [params] = useSearchParams();
  const season = params.get('season') || 'current';
  const wrapped = useWrapped(id, season);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [drawn, setDrawn] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const data = wrapped.isError ? undefined : wrapped.data;
  const hasCards = (data?.cards.length ?? 0) > 0;

  useEffect(() => {
    if (!data || !hasCards) { setDrawn(false); return; }
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) { setDrawn(false); return; }
    let cancelled = false;
    const paint = () => {
      if (cancelled) return;
      canvas.width = CARD_W;
      canvas.height = CARD_H;
      drawWrapped(ctx, data, paletteFromDocument(document));
      setDrawn(true);
    };
    // The card uses the page's fonts; drawing before they load bakes the
    // fallback face into the PNG.
    const fonts = (document as Document & { fonts?: { ready: Promise<unknown> } }).fonts;
    if (fonts?.ready) { void fonts.ready.then(paint); } else { paint(); }
    return () => { cancelled = true; };
  }, [data, hasCards]);

  const fileName = `slomix-wrapped-${(data?.player_name || id || 'player').replace(/\s+/g, '_')}.png`;
  const download = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const link = document.createElement('a');
    link.download = fileName;
    link.href = canvas.toDataURL('image/png');
    link.click();
    setStatus(`saved ${fileName}`);
  };
  const copy = async () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    try {
      const blob = await new Promise<Blob | null>((res) => { canvas.toBlob(res, 'image/png'); });
      if (!blob || typeof ClipboardItem === 'undefined') { setStatus('copy not supported here — use download'); return; }
      await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
      setStatus('copied — paste it into Discord');
    } catch {
      setStatus('copy not supported here — use download');
    }
  };

  return (
    <Stack gap={5} style={{ paddingTop: 'var(--space-6)' }}>
      <SectionHead
        label="wrapped"
        aside={<span className="lbl">{data?.season_name ?? season} · <Link to={`/profile/${encodeURIComponent(id)}`} style={{ color: 'inherit' }}>{data?.player_name ?? id}</Link></span>}
      />
      {wrapped.isPending && <Pending label="season card" />}
      {wrapped.isError && <Unavailable what="season card" />}
      {data && !hasCards && (
        <Absent block reason={`no season data for ${data.player_name || id} yet — the card needs at least one round in ${data.season_name || season}`} />
      )}
      {data && hasCards && (
        <div style={{ display: 'flex', gap: 'var(--space-7)', alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div data-parity="wrapped.card" style={{ flex: '0 1 360px' }}>
            <canvas
              ref={canvasRef}
              width={CARD_W}
              height={CARD_H}
              role="img"
              aria-label={`Slomix Wrapped card for ${data.player_name}`}
              style={{ width: '100%', height: 'auto', display: 'block', border: '1px solid var(--color-rule-700)' }}
            />
          </div>
          <Stack gap={3} style={{ flex: '1 1 280px' }}>
            <Stack gap={1} className="rows" parity="wrapped.facts">
              {data.cards.map((c) => (
                <div key={c.key} className="row" style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--space-3)', padding: 'var(--space-2) 0', borderBottom: '1px solid var(--color-rule-800)' }}>
                  <Lbl style={{ minWidth: 140 }}>{c.label}</Lbl>
                  <span className="m" style={{ fontSize: 'var(--fs-row-lg)' }}>{c.value}</span>
                  {c.sub && <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-accent)' }}>{c.sub}</span>}
                </div>
              ))}
            </Stack>
            <div data-parity="wrapped.actions" style={{ display: 'flex', gap: 'var(--space-4)', alignItems: 'baseline' }}>
              <button type="button" onClick={() => { void copy(); }} disabled={!drawn} className="lbl" style={{ background: 'none', border: '1px solid var(--color-rule-700)', color: 'var(--color-text-100)', padding: 'var(--space-2) var(--space-3)', cursor: drawn ? 'pointer' : 'not-allowed', opacity: drawn ? 1 : 0.4 }}>
                copy image
              </button>
              <button type="button" onClick={download} disabled={!drawn} className="lbl" style={{ background: 'none', border: '1px solid var(--color-rule-700)', color: 'var(--color-text-100)', padding: 'var(--space-2) var(--space-3)', cursor: drawn ? 'pointer' : 'not-allowed', opacity: drawn ? 1 : 0.4 }}>
                download png
              </button>
              <ActLink to={`/profile/${encodeURIComponent(id)}`}>profile →</ActLink>
            </div>
            {status && <Lbl>{status}</Lbl>}
            {!drawn && <Lbl>drawing the card…</Lbl>}
          </Stack>
        </div>
      )}
    </Stack>
  );
}
