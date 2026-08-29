import { useState } from 'react';
import { Link } from 'react-router';
import { Cluster, Stack } from '../components/layout';
import { Chip, Lbl, Pending, SectionHead, Unavailable, figure } from '../components/ui';
import { useSkillFormula, useSkillLeaderboard, useSsr } from '../lib/queries';
import type { RatedPlayer, SsrPlayer } from '../lib/types';

/**
 * ET Rating (docs/design/12 row 24).
 *
 * Two formulas live on this page and the danger is that a reader takes a
 * number from one and compares it with a number from the other. ET Rating
 * v2.1 is the published one — the figure the profile shows. SSR v0.3 is a
 * second, session-scoped formula whose coverage is still partial: one of the
 * fifteen rated players has three of its eight components measured. They are
 * kept apart, labelled by version, and the SSR panel prints coverage beside
 * every score rather than under a footnote.
 *
 * WHAT THE COMPONENT PANEL SHOWS. `constant + Σ contribution` produces the
 * RAW score; the published rating is that shrunk toward the pool mean by
 * `(n·raw + k·pool_mean)/(n+k)`. The first version of this page called the
 * components "the sum the rating is", which skipped the second step — the
 * review was right to stop it. The panel now prints BOTH steps.
 *
 * ⚠️ A correction to my own earlier note, which claimed "only 12 of 31 rows
 * reconstruct" as evidence of inconsistent shrinkage. That was a bad read:
 * three rows in the table were four months stale and were poisoning the
 * pool mean I reconstructed with. With the cohort reconciled (see
 * skill_rating_service.compute_and_store_ratings) every published rating
 * reconstructs to within 0.0003 — the components' own rounding. Shrinkage
 * was consistent all along; my pool was not.
 */

const TIER_COLOUR = new Map<string, string>([
  ['veteran', 'var(--color-accent)'],
  ['experienced', 'var(--color-text-200)'],
  ['regular', 'var(--color-text-300)'],
  ['newcomer', 'var(--color-text-400)'],
]);

/** Positive contributions read up, negative down — dpr's weight is -0.08. */
function ContributionBar({ value, scale }: { value: number; scale: number }) {
  const width = Math.min(100, (Math.abs(value) / scale) * 100);
  const positive = value >= 0;
  return (
    <span style={{ display: 'flex', width: 120, height: 4, background: 'var(--color-rule-900)' }}>
      <span style={{ width: '50%', display: 'flex', justifyContent: 'flex-end' }}>
        {!positive && <span style={{ width: `${width}%`, background: 'var(--color-neg)' }} />}
      </span>
      <span style={{ width: '50%' }}>
        {positive && <span style={{ display: 'block', width: `${width}%`, height: '100%', background: 'var(--color-pos)' }} />}
      </span>
    </span>
  );
}

function Components({ player, constant, shrinkageK, poolMean }: {
  player: RatedPlayer; constant: number; shrinkageK: number; poolMean: number | null;
}) {
  const entries = Object.entries(player.components);
  const raw = constant + entries.reduce((sum, [, c]) => sum + c.contribution, 0);
  // The shrinkage weight, computed rather than read: `confidence` in the
  // payload is min(1, n/30), a different quantity that reads like this one.
  const weight = player.games_rated / (player.games_rated + shrinkageK);
  const shrunk = poolMean == null ? raw : weight * raw + (1 - weight) * poolMean;
  const scale = Math.max(...entries.map(([, c]) => Math.abs(c.contribution)), 0.01);
  const sorted = [...entries].sort((a, b) => Math.abs(b[1].contribution) - Math.abs(a[1].contribution));
  return (
    <Stack gap={1} className="rows" style={{ paddingTop: 'var(--space-2)', paddingBottom: 'var(--space-3)' }}>
      <Cluster gap={3} justify="between">
        <Lbl style={{ fontSize: 'var(--fs-caption)' }}>what the raw score is made of</Lbl>
        <Lbl style={{ fontSize: 'var(--fs-caption)' }}>measured · percentile · weight → contribution</Lbl>
      </Cluster>
      <Cluster gap={3} justify="between" className="row" style={{ padding: 'var(--space-1) 0' }}>
        <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-300)' }}>
          raw = constant + Σ = {raw.toFixed(4)}
        </span>
        {poolMean == null ? (
          <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-500)' }}>
            published {player.et_rating.toFixed(4)} · pool mean unavailable, so the
            shrinkage step cannot be shown
          </span>
        ) : (
          <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-500)' }}>
            × {weight.toFixed(3)} + pool {poolMean.toFixed(4)} × {(1 - weight).toFixed(3)}
            {' = '}{shrunk.toFixed(4)} → published {player.et_rating.toFixed(4)}
          </span>
        )}
      </Cluster>
      {sorted.map(([name, c]) => (
        <Cluster key={name} gap={3} justify="between" align="center" className="row" style={{ padding: 'var(--space-1) 0' }}>
          <span style={{ fontSize: 'var(--fs-small)' }}>{name.replace(/_/g, ' ')}</span>
          <Cluster gap={3} align="center">
            <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)', width: 72, textAlign: 'right' }}>
              {c.raw == null ? 'unmeasured' : figure(c.raw)}
            </span>
            <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)', width: 44, textAlign: 'right' }}>
              {c.percentile == null ? '—' : `${(c.percentile * 100).toFixed(0)}%`}
            </span>
            <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-500)', width: 48, textAlign: 'right' }}>
              {c.weight > 0 ? '+' : ''}{c.weight.toFixed(2)}
            </span>
            <ContributionBar value={c.contribution} scale={scale} />
            <span className="m" style={{ fontSize: 'var(--fs-small)', width: 56, textAlign: 'right' }}>
              {c.contribution >= 0 ? '+' : ''}{c.contribution.toFixed(4)}
            </span>
          </Cluster>
        </Cluster>
      ))}
    </Stack>
  );
}

function RatedRow({ player, open, onToggle, ambiguous, constant, shrinkageK, poolMean }: {
  player: RatedPlayer; open: boolean; onToggle: () => void; ambiguous: boolean;
  constant: number; shrinkageK: number; poolMean: number | null;
}) {
  return (
    <Stack gap={1}>
      <Cluster gap={3} justify="between" align="center" className="row" style={{ padding: 'var(--space-2) 0' }}>
        <Cluster gap={3} align="baseline" style={{ minWidth: 0 }}>
          <span className="m lbl" style={{ width: 26 }}>{String(player.rank).padStart(2, '0')}</span>
          <Link to={`/profile/${player.player_guid}`} style={{ color: 'var(--color-text-100)', textDecoration: 'none', fontSize: 'var(--fs-row)' }}>
            {player.display_name}
          </Link>
          {/* Two GUIDs, one display name — `ownator` sits at rank 7 and rank 9
            * in the recording with different round counts. Identical names
            * against different ratings is a board contradicting itself. */}
          {ambiguous && <span className="m lbl" style={{ fontSize: 'var(--fs-caption)' }}>{player.player_guid}</span>}
          <span className="lbl" style={{ color: TIER_COLOUR.get(player.tier) ?? 'var(--color-text-500)' }}>
            {player.tier}
          </span>
        </Cluster>
        <Cluster gap={3} align="center">
          <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)', width: 84, textAlign: 'right' }}>
            {figure(player.games_rated)} rounds
          </span>
          {/* `confidence` is NOT the shrinkage weight, though it reads like
            * one: the backend defines it as min(1, n/30) (skill_router:107)
            * while shrinkage uses n/(n+k) with k=40. For a 22-round player
            * those are 0.73 and 0.355 — printing the first as "weight" was
            * wrong by a factor of two (Codex on #835). It is labelled as
            * what it is now: a sample-size confidence. */}
          <span className="m" style={{ fontSize: 'var(--fs-small)', color: player.confidence >= 1 ? 'var(--color-text-500)' : 'var(--color-accent-warm)', width: 128, textAlign: 'right' }}>
            {player.confidence >= 1 ? 'full sample' : `sample conf. ${(player.confidence * 100).toFixed(0)}%`}
          </span>
          <span className="m" style={{ fontSize: 'var(--fs-lead)', width: 68, textAlign: 'right' }}>
            {player.et_rating.toFixed(3)}
          </span>
          <button
            type="button"
            className="act"
            aria-expanded={open}
            onClick={onToggle}
            style={{ background: 'transparent', border: 0, cursor: 'pointer', fontSize: 'var(--fs-caption)' }}
          >
            {open ? 'hide' : 'why'}
          </button>
        </Cluster>
      </Cluster>
      {open && <Components player={player} constant={constant} shrinkageK={shrinkageK} poolMean={poolMean} />}
    </Stack>
  );
}

function SsrRow({ player }: { player: SsrPlayer }) {
  const [have, total] = player.coverage.split('/').map(Number);
  const partial = Number.isFinite(have) && Number.isFinite(total) && have < total;
  return (
    <Cluster gap={3} justify="between" align="center" className="row" style={{ padding: 'var(--space-2) 0' }}>
      <Link to={`/profile/${player.player_guid}`} style={{ color: 'var(--color-text-100)', textDecoration: 'none', fontSize: 'var(--fs-row)' }}>
        {player.name}
      </Link>
      <Cluster gap={3} align="center">
        <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)', width: 78, textAlign: 'right' }}>
          {figure(player.n_sessions)} sessions
        </span>
        {/* Coverage sits BESIDE the score, not in a footnote: a score built
          * on three of eight components is not the same measurement as one
          * built on eight, and the two must not read alike. */}
        <span
          className="m"
          style={{ fontSize: 'var(--fs-small)', width: 56, textAlign: 'right', color: partial ? 'var(--color-accent-warm)' : 'var(--color-text-500)' }}
        >
          {player.coverage}
        </span>
        <span className="m" style={{ fontSize: 'var(--fs-value)', width: 60, textAlign: 'right' }}>
          {player.ssr.toFixed(4)}
        </span>
      </Cluster>
    </Cluster>
  );
}

export function SkillRating() {
  const [open, setOpen] = useState<string | null>(null);
  const [showSsr, setShowSsr] = useState(false);
  const board = useSkillLeaderboard(30);
  const formula = useSkillFormula();
  const ssr = useSsr(showSsr);

  const nameCounts = new Map<string, number>();
  for (const p of board.data?.players ?? []) {
    nameCounts.set(p.display_name, (nameCounts.get(p.display_name) ?? 0) + 1);
  }

  return (
    <div style={{ paddingTop: 'var(--space-7)', paddingBottom: 'var(--space-8)' }}>
      <Lbl>et rating · how the number is built</Lbl>
      <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: 'var(--track-title)', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
        Every rank, with its reasons.
      </h1>

      <Stack gap={2} parity="skill.formula" style={{ paddingTop: 'var(--space-4)' }}>
        {formula.isPending && <Pending label="formula" />}
        {formula.isError && <Unavailable what="formula" />}
        {formula.data && (
          <>
            <SectionHead
              label={`${formula.data.name} · v${formula.data.version}`}
              aside={<span className="lbl">{formula.data.range}</span>}
            />
            <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-300)' }}>
              {formula.data.formula}
            </span>
            <span className="lbl" style={{ fontSize: 'var(--fs-caption)' }}>
              {formula.data.normalization} · at least {formula.data.min_rounds} rounds · shrinkage k={formula.data.shrinkage_k}
            </span>
          </>
        )}
      </Stack>

      <Stack gap={2} parity="skill.leaderboard" style={{ paddingTop: 'var(--space-6)' }}>
        <SectionHead label="rated players" aside={<span className="lbl">rounds · weight · rating</span>} />
        {board.isPending && <Pending label="ratings" />}
        {board.isError && <Unavailable what="ratings" />}
        {board.data && board.data.players.length === 0 && (
          <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
            nobody has played the {board.data.meta.min_rounds} rounds a rating needs yet
          </span>
        )}
        {board.data && board.data.players.length > 0 && (
          <Stack gap={1} className="rows">
            {board.data.players.map((p) => (
              <RatedRow
                key={p.player_guid}
                player={p}
                open={open === p.player_guid}
                onToggle={() => { setOpen(open === p.player_guid ? null : p.player_guid); }}
                ambiguous={(nameCounts.get(p.display_name) ?? 0) > 1}
                constant={board.data.meta.constant}
                shrinkageK={board.data.meta.shrinkage_k}
                poolMean={board.data.meta.pool_mean ?? null}
              />
            ))}
          </Stack>
        )}
      </Stack>

      <Stack gap={2} parity="skill.ssr" style={{ paddingTop: 'var(--space-6)' }}>
        <SectionHead
          label="a second formula, still filling in"
          aside={
            <Chip
              active={showSsr}
              label={showSsr ? 'hide ssr' : 'show ssr'}
              onClick={() => { setShowSsr(!showSsr); }}
            />
          }
        />
        <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
          SSR is session-scoped and separate from the rating above — the two
          numbers are not comparable, and neither is a player rated on three
          components with one rated on eight.
        </span>
        {showSsr && (
          <>
            {ssr.isPending && <Pending label="ssr" />}
            {ssr.isError && <Unavailable what="ssr" />}
            {ssr.data && (
              <>
                <span className="lbl" style={{ fontSize: 'var(--fs-caption)' }}>
                  {ssr.data.formula_version} · {figure(ssr.data.rated)} rated ·
                  {' '}needs {ssr.data.min_sessions} sessions and {ssr.data.min_components} measured components
                </span>
                <Stack gap={1} className="rows">
                  {ssr.data.players.map((p) => <SsrRow key={p.player_guid} player={p} />)}
                </Stack>
              </>
            )}
          </>
        )}
      </Stack>
    </div>
  );
}
