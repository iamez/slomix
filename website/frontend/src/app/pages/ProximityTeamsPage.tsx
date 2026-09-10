/**
 * Phase 5 — the round team comparison (route proximity-teams,
 * /proximity/round/:roundId/teams). One wire call; its null-form covers
 * BOTH an uncaptured round and a nonexistent id (measured — the wire
 * cannot tell them apart), and the page says so instead of choosing.
 */
import { useParams } from 'react-router';
import { Cluster, Stack } from '../components/layout';
import { Absent, Lbl, Meta, Pending, SectionHead, Unavailable, figure } from '../components/ui';
import { useProxTeamComparison } from '../lib/queries';
import type { ProxTeamComparisonSide } from '../lib/types';
import { ProxRow } from './proximityShared';

function SideBlock({ team, side }: { team: string; side: ProxTeamComparisonSide }) {
  return (
    <Stack gap={1} style={{ minWidth: 220 }} className="rows">
      <Lbl>{team}</Lbl>
      <ProxRow name="dispersion" val={side.avg_dispersion != null ? `${figure(side.avg_dispersion)} u` : '—'} />
      <ProxRow name="max spread" val={side.avg_max_spread != null ? `${figure(side.avg_max_spread)} u` : '—'} />
      <ProxRow name="stragglers" val={side.avg_stragglers != null ? figure(side.avg_stragglers) : '—'} />
      <ProxRow name="samples" val={side.samples != null ? figure(side.samples) : '—'} />
    </Stack>
  );
}

export function ProximityTeamsPage() {
  const params = useParams();
  const roundId = params.roundId != null && /^\d+$/.test(params.roundId) ? Number(params.roundId) : null;
  const q = useProxTeamComparison(roundId);

  if (roundId == null) {
    return <Absent block reason="no round named — open a comparison from a round's engagement panel" />;
  }
  if (q.isPending) return <Pending label="team comparison" />;
  if (q.isError || !q.data) return <Unavailable what="team comparison" />;
  const d = q.data;
  const captured = d.cohesion.axis.samples != null || d.cohesion.allies.samples != null
    || d.pushes.axis.push_count != null || d.crossfire.length > 0;

  return (
    <Stack gap={7} style={{ paddingTop: 'var(--space-7)' }}>
      <Stack gap={2}>
        <Lbl>proximity · team comparison</Lbl>
        <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: 'var(--track-title)', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
          round #{figure(roundId)}
        </h1>
      </Stack>

      {!captured ? (
        <Absent block reason="no proximity capture for this round — either the tracker did not run, or no round has this id (the wire answers both the same way)" />
      ) : (
        <>
          <div data-parity="proximity-teams.cohesion">
            <SectionHead label="cohesion" aside={<span className="lbl">whole round</span>} />
            <Cluster gap={7} style={{ flexWrap: 'wrap', marginTop: 'var(--space-3)' }}>
              <SideBlock team="axis" side={d.cohesion.axis} />
              <SideBlock team="allies" side={d.cohesion.allies} />
            </Cluster>
          </div>

          <div data-parity="proximity-teams.pushes">
            <SectionHead label="pushes" />
            <Cluster gap={7} style={{ flexWrap: 'wrap', marginTop: 'var(--space-3)' }}>
              {(['axis', 'allies'] as const).map((team) => {
                const side = d.pushes[team];
                return (
                  <Stack key={team} gap={1} style={{ minWidth: 220 }} className="rows">
                    <Lbl>{team}</Lbl>
                    <ProxRow name="pushes" val={side.push_count != null ? figure(side.push_count) : '—'} />
                    <ProxRow name="quality" val={side.avg_quality != null ? figure(side.avg_quality) : '—'} />
                    <ProxRow name="alignment" val={side.avg_alignment != null ? figure(side.avg_alignment) : '—'} />
                  </Stack>
                );
              })}
            </Cluster>
          </div>

          <div data-parity="proximity-teams.crossfire">
            <SectionHead label="crossfire execution" aside={<span className="lbl">by target team</span>} />
            {d.crossfire.length === 0 ? (
              <div style={{ marginTop: 'var(--space-2)' }}>
                <Absent reason="no crossfire opportunities were detected this round" />
              </div>
            ) : (
              <Stack gap={1} className="rows" style={{ marginTop: 'var(--space-3)', maxWidth: 480 }}>
                {d.crossfire.map((c) => (
                  <ProxRow key={c.target_team}
                    name={`against ${c.target_team.toLowerCase()}`}
                    mid={`${figure(c.executed)} of ${figure(c.total_opportunities)} chances`}
                    val={`${figure(c.execution_rate)}%`} />
                ))}
              </Stack>
            )}
          </div>

          <Meta>
            dispersion and spread are averages over the round's cohesion
            samples; pushes carry the tracker's quality and lane-alignment
            scores
          </Meta>
        </>
      )}
    </Stack>
  );
}
