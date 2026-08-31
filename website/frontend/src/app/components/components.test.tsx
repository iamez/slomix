import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import { Cluster, Stack } from './layout';
import { Absent, Chip, KpiTile, Lbl, Meta, SectionHead, StatusDot, Tabs, Unavailable, figure } from './ui';

/**
 * The first tests the component layer has ever had. Until now every one of
 * these was exercised only sideways, through a page test asserting on
 * rendered text — which means the one behaviour with real coverage was the
 * word "unavailable", and things like figure()'s formatting rule or
 * StatusDot's colour mapping had none at all.
 *
 * What is worth asserting here is not that they render, but the RULES they
 * exist to enforce, because those rules are what the pages stop having to
 * remember.
 */

function renderIn(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe('layout primitives', () => {
  it('spend spacing from the scale, never in pixels', () => {
    // The whole point of the primitives: the owner reworks arrangement
    // repeatedly, so distance has to be a named step that a stylesheet can
    // redefine — not a number frozen into a hundred call sites.
    renderIn(
      <Stack gap={5} parity="probe.stack">
        <span>a</span>
        <span>b</span>
      </Stack>,
    );
    expect(document.querySelector('[data-parity="probe.stack"]')).toHaveStyle({
      gap: 'var(--space-5)',
      display: 'grid',
    });
  });

  it('put the hairline between children, not after the last one', () => {
    renderIn(
      <Stack divided parity="probe.divided">
        <span>a</span>
      </Stack>,
    );
    // The rule lives in CSS (`.stack-divided > * + *`) because an inline
    // style cannot express "every child after the first".
    expect(document.querySelector('[data-parity="probe.divided"]')).toHaveClass('stack-divided');
  });

  it('wrap a cluster by default so a row of chips cannot overflow', () => {
    renderIn(
      <Cluster gap={2} parity="probe.cluster">
        <span>a</span>
      </Cluster>,
    );
    expect(document.querySelector('[data-parity="probe.cluster"]')).toHaveStyle({
      flexWrap: 'wrap',
      gap: 'var(--space-2)',
      alignItems: 'baseline',
    });
  });

  it('carry a parity key when given one, since the sweep reads those', () => {
    renderIn(<Stack parity="sessions2.lineups"><span>a</span></Stack>);
    expect(document.querySelector('[data-parity="sessions2.lineups"]')).not.toBeNull();
  });
});

describe('Chip', () => {
  it('says what it is pressed, so the screen reader and the eye agree', () => {
    // This shape used to be five byte-identical copies of a local `Pill`
    // whose active state existed only as a colour — invisible to anything
    // that is not an eye.
    renderIn(<Chip active label="DPM" onClick={() => {}} />);
    expect(screen.getByRole('button', { name: 'DPM' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('reports its own press exactly once', () => {
    const onClick = vi.fn();
    renderIn(<Chip active={false} label="Kills" onClick={onClick} />);
    screen.getByRole('button', { name: 'Kills' }).click();
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});

describe('Tabs', () => {
  const TABS = [
    { key: 'summary', label: 'Summary' },
    { key: 'players', label: 'Players' },
  ] as const;

  it('announce themselves as one set with one chosen member', () => {
    renderIn(<Tabs tabs={TABS} current="players" onSelect={() => {}} />);
    expect(screen.getByRole('tablist')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Players' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: 'Summary' })).toHaveAttribute('aria-selected', 'false');
  });

  it('report the tab that was chosen, not the one that was current', () => {
    const onSelect = vi.fn();
    renderIn(<Tabs tabs={TABS} current="summary" onSelect={onSelect} />);
    screen.getByRole('tab', { name: 'Players' }).click();
    expect(onSelect).toHaveBeenCalledWith('players');
  });
});

describe('figure', () => {
  it('groups integers and holds non-integers to one decimal', () => {
    // Columns must not dance: 1,760 and 314.2 have to occupy predictable
    // width, which is why this rule exists rather than toLocaleString alone.
    expect(figure(1760)).toBe('1,760');
    expect(figure(314.159)).toBe('314.2');
    expect(figure(0)).toBe('0');
    expect(figure(-12.5)).toBe('-12.5');
  });
});

describe('StatusDot', () => {
  it('maps each state to its own meaning, and anything unknown to idle', () => {
    // Colour means one of four things in this design; a state nobody
    // anticipated must not borrow "ok" green.
    const cases: [string, string][] = [
      ['ok', 'var(--color-pos)'],
      ['warn', 'var(--color-accent-warm)'],
      ['error', 'var(--color-neg)'],
      ['something-new', 'var(--color-idle)'],
    ];
    for (const [state, expected] of cases) {
      const view = renderIn(
        <Stack parity="probe.dot">
          <StatusDot state={state} />
        </Stack>,
      );
      const dot = document.querySelector('[data-parity="probe.dot"] > span');
      expect(dot).toHaveStyle({ background: expected });
      view.unmount();
    }
  });
});

describe('the small text components', () => {
  it('render a label, a section head with its parity key, and a KPI', () => {
    renderIn(
      <>
        <Lbl>played</Lbl>
        <SectionHead label="the maps" parity="maps.list" />
        <KpiTile value="1,760" label="rounds" />
      </>,
    );
    expect(screen.getByText('played')).toBeInTheDocument();
    expect(screen.getByText('rounds')).toBeInTheDocument();
    expect(document.querySelector('[data-parity="maps.list"]')).not.toBeNull();
    expect(screen.getByText('1,760')).toBeInTheDocument();
  });

  it('name what is unavailable instead of leaving a blank', () => {
    renderIn(<Unavailable what="weapon stats" />);
    expect(screen.getByText('weapon stats: unavailable')).toBeInTheDocument();
  });
});

describe('Absent holds its identity against its callers', () => {
  // Both guards below were seen failing against the pre-review component:
  // with the caller's spread LAST, the hostile style repainted absence red,
  // and with `reason: ReactNode`, `undefined` rendered an empty grey span —
  // a reason-less absence, the exact thing the component exists to end.

  it('keeps the grey even when a caller tries to repaint it', () => {
    render(<Absent reason="no rounds in this window" style={{ color: 'red', fontSize: '30px' }} />);
    const el = screen.getByText('no rounds in this window');
    expect(el.style.color).toBe('var(--color-text-500)');
    expect(el.style.fontSize).toBe('var(--fs-micro)');
  });

  it('still lets layout through — spacing is the caller\'s to vary', () => {
    render(<Absent reason="no records yet" style={{ marginTop: '7px' }} />);
    expect(screen.getByText('no records yet').style.marginTop).toBe('7px');
  });

  it('names the bug out loud when a page forwards an empty reason', () => {
    // The type forbids null/undefined; the runtime half catches what the
    // type system cannot — a forwarded empty string, or a boolean.
    render(<Absent reason={'' as unknown as string} />);
    expect(screen.getByText(/page gave no reason/)).toBeTruthy();
    render(<Absent reason={false as unknown as string} />);
    expect(screen.getAllByText(/page gave no reason/).length).toBe(2);
  });

  it('Meta keeps its grey the same way', () => {
    render(<Meta style={{ color: 'red' }}>43 ms</Meta>);
    expect(screen.getByText('43 ms').style.color).toBe('var(--color-text-500)');
  });
});
