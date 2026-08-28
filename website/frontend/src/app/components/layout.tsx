import type { CSSProperties, ReactNode } from 'react';

/**
 * Layout primitives (docs/design/11 §A, and the owner's 2026-08-28 word: the
 * theme stays, the arrangement gets reworked — repeatedly, and on every
 * future addition).
 *
 * The whole point is one rule: A COMPONENT NEVER SETS ITS OWN OUTER SPACING.
 * Distance between siblings belongs to the parent, expressed once as a `gap`
 * step. Measured on the 13 built pages before this file existed: 917 sizes
 * typed by hand and 236 style blocks that mix look with layout — those are
 * expensive precisely because a component that writes its own `margin`
 * cannot be moved without reading it first.
 *
 * `gap` is a STEP on the spacing scale (--space-1..8 = 4/8/12/16/22/28/40/56),
 * never a pixel. If a layout needs something between two steps, that is a
 * missing step in the scale, not a reason to reach past it.
 */

export type Space = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8;

/**
 * Written out rather than built with `var(--space-${step})`. A composed name
 * is invisible to every reader that is not a running browser — including the
 * token guard in tokens.test.ts, which exists because an undeclared token
 * fails silently. Eight literal strings cost nothing and keep the eight steps
 * greppable.
 */
const SPACE = new Map<Space, string>([
  [1, 'var(--space-1)'],
  [2, 'var(--space-2)'],
  [3, 'var(--space-3)'],
  [4, 'var(--space-4)'],
  [5, 'var(--space-5)'],
  [6, 'var(--space-6)'],
  [7, 'var(--space-7)'],
  [8, 'var(--space-8)'],
]);

/** A Map rather than an object: a lookup by variable key on a plain object is
 * an injection sink to every scanner that reads this code, and the shape it
 * asks for here is also the more honest one — these are eight fixed entries,
 * not a record someone may extend at a call site. */
const space = (step: Space) => SPACE.get(step) ?? SPACE.get(3)!;

export interface StackProps {
  /** Distance between children, as a scale step. */
  gap?: Space;
  /** Hairline between children — the design's only separator. */
  divided?: boolean;
  as?: 'div' | 'section' | 'ul' | 'ol' | 'nav';
  parity?: string;
  style?: CSSProperties;
  className?: string;
  children: ReactNode;
}

/** Children stacked vertically, one distance between them. */
export function Stack({
  gap = 3, divided = false, as: Tag = 'div', parity, style, className, children,
}: StackProps) {
  return (
    <Tag
      data-parity={parity}
      className={divided ? `stack-divided ${className ?? ''}`.trim() : className}
      style={{ display: 'grid', gap: space(gap), ...style }}
    >
      {children}
    </Tag>
  );
}

export interface ClusterProps {
  gap?: Space;
  /** Wrapping is the default: a row of chips must never overflow its column. */
  wrap?: boolean;
  align?: 'baseline' | 'center' | 'start' | 'end';
  justify?: 'start' | 'between' | 'end' | 'center';
  as?: 'div' | 'section' | 'ul' | 'nav';
  parity?: string;
  style?: CSSProperties;
  className?: string;
  children: ReactNode;
}

const JUSTIFY = new Map<NonNullable<ClusterProps['justify']>, string>([
  ['start', 'flex-start'],
  ['between', 'space-between'],
  ['end', 'flex-end'],
  ['center', 'center'],
]);

const ALIGN = new Map<NonNullable<ClusterProps['align']>, string>([
  ['baseline', 'baseline'],
  ['center', 'center'],
  ['start', 'flex-start'],
  ['end', 'flex-end'],
]);

/** Children in a row, wrapping, with one distance between them. */
export function Cluster({
  gap = 2, wrap = true, align = 'baseline', justify = 'start',
  as: Tag = 'div', parity, style, className, children,
}: ClusterProps) {
  return (
    <Tag
      data-parity={parity}
      className={className}
      style={{
        display: 'flex',
        flexWrap: wrap ? 'wrap' : 'nowrap',
        alignItems: ALIGN.get(align),
        justifyContent: JUSTIFY.get(justify),
        gap: space(gap),
        ...style,
      }}
    >
      {children}
    </Tag>
  );
}
