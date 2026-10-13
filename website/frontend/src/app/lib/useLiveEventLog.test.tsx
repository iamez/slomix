import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { useLiveEventLog } from './useLiveEventLog';

beforeEach(() => vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'performance', 'Date'] }));
afterEach(() => { cleanup(); vi.useRealTimers(); });

it('expires on monotonic elapsed time despite browser wall-clock changes, without ticking renders', () => {
  let renders = 0;
  const { result } = renderHook(() => { renders++; return useLiveEventLog(); });
  act(() => result.current.append([{ seq: 1, type: 'ANNOUNCE', received_at: 1000 }], 1000));
  const before = renders;
  vi.setSystemTime(new Date('2040-01-01'));
  act(() => vi.advanceTimersByTime(599000));
  expect(result.current.log).toHaveLength(1);
  expect(renders).toBe(before);
  vi.setSystemTime(new Date('1990-01-01'));
  act(() => vi.advanceTimersByTime(1001));
  expect(result.current.log).toHaveLength(0);
  expect(vi.getTimerCount()).toBe(0);
});

it('reanchors on recovery, expires each row, and clears old worker deadlines on reset', () => {
  const { result } = renderHook(() => useLiveEventLog());
  act(() => result.current.append([{ seq: 1, type: 'ANNOUNCE', received_at: 1000 }], 1000));
  act(() => vi.advanceTimersByTime(300000));
  act(() => result.current.append([{ seq: 2, type: 'ANNOUNCE', received_at: 1400 }], 1400));
  act(() => vi.advanceTimersByTime(200001));
  expect(result.current.log.map(e => e.seq)).toEqual([2]);
  act(() => result.current.clear());
  expect(vi.getTimerCount()).toBe(0);
  act(() => result.current.append([{ seq: 1, type: 'ROUND_START' }], 50));
  act(() => vi.advanceTimersByTime(400000));
  expect(result.current.log.map(e => e.seq)).toEqual([1]);
  act(() => vi.advanceTimersByTime(200001));
  expect(result.current.log).toHaveLength(0);
});

it('keeps compatibility envelope first-seen ages monotonic and cleans up on unmount', () => {
  const { result, unmount } = renderHook(() => useLiveEventLog());
  act(() => result.current.append([{ seq: 1, type: 'ROUND_START' }]));
  const first = result.current.log[0].received_at as number;
  act(() => vi.advanceTimersByTime(300000));
  vi.setSystemTime(new Date('1990-01-01'));
  act(() => result.current.append([{ seq: 2, type: 'ROUND_END' }]));
  expect(result.current.log[1].received_at).toBe(first + 300);
  act(() => vi.advanceTimersByTime(300001));
  expect(result.current.log.map(e => e.seq)).toEqual([2]);
  expect(vi.getTimerCount()).toBe(1);
  unmount();
  expect(vi.getTimerCount()).toBe(0);
});


it.each(['1960-01-01', '2040-01-01'])('anchors compatibility event timestamps independently of browser time %s', (date) => {
  vi.setSystemTime(new Date(date));
  const { result } = renderHook(() => useLiveEventLog());
  act(() => result.current.append([{ seq: 1, type: 'ANNOUNCE', received_at: 1000 }]));
  expect(result.current.log.map(e => e.seq)).toEqual([1]);
  act(() => vi.advanceTimersByTime(300000));
  act(() => result.current.append([{ seq: 1, type: 'ANNOUNCE', received_at: 1000 }]));
  act(() => vi.advanceTimersByTime(300001));
  expect(result.current.log).toHaveLength(0);
});

it('adopts a source clock after untimed compatibility rows without renewing their age', () => {
  vi.setSystemTime(new Date('2040-01-01'));
  const { result } = renderHook(() => useLiveEventLog());
  act(() => result.current.append([{ seq: 1, type: 'ROUND_START' }]));
  act(() => vi.advanceTimersByTime(300000));
  act(() => result.current.append([{ seq: 2, type: 'ANNOUNCE', received_at: 1000 }]));
  expect(result.current.log.map(e => e.received_at)).toEqual([700, 1000]);
  act(() => vi.advanceTimersByTime(300001));
  expect(result.current.log.map(e => e.seq)).toEqual([2]);
  act(() => result.current.append([], 1300.001));
  act(() => vi.advanceTimersByTime(300000));
  expect(result.current.log).toHaveLength(0);
});
