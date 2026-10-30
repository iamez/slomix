export function journeyPointAt<T extends {
    t: number; x: number | null; y: number | null;
    break_before?: boolean; event?: string | null;
}>(path: readonly T[], time: number): (T & { x: number; y: number }) | null;
