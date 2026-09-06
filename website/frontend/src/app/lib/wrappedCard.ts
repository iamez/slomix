/**
 * The Wrapped share card, drawn (docs/design/22? no — phase 7, docs/design/08;
 * legacy wrapped.js). A pure function over a minimal canvas-like context so
 * the drawing is testable without a browser canvas, and so the design rules
 * of docs/design/03 can be pinned: near-black ground, hairlines instead of
 * cards, radius 0, NO gradients, NO shadows, condensed labels, mono numerals.
 * The legacy card was a gradient with rounded tiles — the one thing the new
 * site does not do.
 */
import type { Wrapped } from './types';

export const CARD_W = 1080;
export const CARD_H = 1920;

/** What the drawing needs from a 2D context — and nothing it must not use. */
export interface CardContext {
  fillStyle: string | CanvasGradient | CanvasPattern;
  font: string;
  textAlign: CanvasTextAlign;
  fillRect(x: number, y: number, w: number, h: number): void;
  fillText(text: string, x: number, y: number, maxWidth?: number): void;
}

export interface CardPalette {
  ground: string;
  rule: string;
  label: string;
  text: string;
  accent: string;
  muted: string;
  cond: string;
  mono: string;
}

/** The token values the card is drawn with. A canvas cannot read CSS custom
 *  properties by itself, so the page resolves them from the document and
 *  hands them over; the defaults are tokens.css's light-on-dark values. */
export const DEFAULT_PALETTE: CardPalette = {
  ground: '#0b0b0a',
  rule: '#2a2a27',
  label: '#7a7a74',
  text: '#f2f2ee',
  accent: '#e0a33b',
  muted: '#a3a39c',
  cond: "'Barlow Condensed', system-ui, sans-serif",
  mono: "'IBM Plex Mono', ui-monospace, monospace",
};

export function drawWrapped(ctx: CardContext, data: Wrapped, palette: CardPalette = DEFAULT_PALETTE): void {
  const W = CARD_W;
  const H = CARD_H;
  ctx.fillStyle = palette.ground;
  ctx.fillRect(0, 0, W, H);

  ctx.textAlign = 'left';
  ctx.fillStyle = palette.label;
  ctx.font = `500 44px ${palette.cond}`;
  ctx.fillText('SLOMIX WRAPPED', 72, 150);
  ctx.fillStyle = palette.text;
  ctx.font = `500 96px ${palette.cond}`;
  ctx.fillText(String(data.player_name || data.guid || '').toUpperCase().slice(0, 22), 72, 262);
  ctx.fillStyle = palette.muted;
  ctx.font = `36px ${palette.mono}`;
  ctx.fillText(String(data.season_name || data.season_id || ''), 72, 324);
  // One hairline under the head — the only separator the design allows.
  ctx.fillStyle = palette.rule;
  ctx.fillRect(72, 372, W - 144, 1);

  const cards = data.cards.slice(0, 8);
  const cols = 2;
  const padX = 72;
  const gutter = 48;
  const tileW = (W - padX * 2 - gutter) / cols;
  const tileH = 300;
  const top = 430;
  cards.forEach((c, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const x = padX + col * (tileW + gutter);
    const y = top + row * tileH;
    ctx.textAlign = 'left';
    ctx.fillStyle = palette.label;
    ctx.font = `500 30px ${palette.cond}`;
    ctx.fillText(String(c.label || '').toUpperCase().slice(0, 24), x, y + 48);
    ctx.fillStyle = palette.text;
    ctx.font = `500 72px ${palette.mono}`;
    ctx.fillText(String(c.value || '').slice(0, 14), x, y + 140, tileW);
    if (c.sub) {
      ctx.fillStyle = palette.accent;
      ctx.font = `30px ${palette.mono}`;
      ctx.fillText(String(c.sub).slice(0, 30), x, y + 196, tileW);
    }
    // hairline under every tile, full tile width
    ctx.fillStyle = palette.rule;
    ctx.fillRect(x, y + tileH - 40, tileW, 1);
  });

  ctx.textAlign = 'left';
  ctx.fillStyle = palette.label;
  ctx.font = `32px ${palette.mono}`;
  ctx.fillText('slomix.fyi', 72, H - 80);
}

/** Read the palette off the live document so the card matches the page's
 *  tokens; falls back to the defaults where a token is missing. */
export function paletteFromDocument(doc: Document | undefined): CardPalette {
  if (!doc?.documentElement) return DEFAULT_PALETTE;
  const cs = doc.defaultView?.getComputedStyle(doc.documentElement);
  const read = (name: string, fallback: string) => {
    const v = cs?.getPropertyValue(name).trim();
    return v ? v : fallback;
  };
  return {
    ground: read('--color-ink-950', DEFAULT_PALETTE.ground),
    rule: read('--color-rule-700', DEFAULT_PALETTE.rule),
    label: read('--color-text-500', DEFAULT_PALETTE.label),
    text: read('--color-text-100', DEFAULT_PALETTE.text),
    accent: read('--color-accent', DEFAULT_PALETTE.accent),
    muted: read('--color-text-400', DEFAULT_PALETTE.muted),
    cond: read('--font-cond', DEFAULT_PALETTE.cond),
    mono: read('--font-mono', DEFAULT_PALETTE.mono),
  };
}
