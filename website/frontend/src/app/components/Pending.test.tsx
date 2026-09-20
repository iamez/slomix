import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Pending } from './ui';

describe('Pending', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it('is just the label at first, counts after three seconds, and says why after fifteen', () => {
    render(<Pending label="proximity players" />);
    expect(screen.getByText(/^proximity players…$/)).toBeInTheDocument();
    act(() => { vi.advanceTimersByTime(3_500); });
    expect(screen.getByText(/proximity players… 3 s so far/)).toBeInTheDocument();
    expect(screen.queryByText(/cache window/)).toBeNull();
    act(() => { vi.advanceTimersByTime(12_000); });
    expect(screen.getByText(/15 s so far — the first query of a cache window computes from the tables/)).toBeInTheDocument();
  });

  it('stops its clock when unmounted', () => {
    const { unmount } = render(<Pending label="x" />);
    unmount();
    act(() => { vi.advanceTimersByTime(5_000); });
    expect(screen.queryByText(/s so far/)).toBeNull();
  });
});
