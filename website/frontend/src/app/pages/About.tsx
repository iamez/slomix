import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { useBuildInfo, useOverview, useSystemOverview } from '../lib/queries';
import { API_PROBES, runProbes, type ProbeResult } from '../lib/probes';
import { Lbl, Pending, StatusDot, Unavailable, lblStyle, rowStyle } from '../components/ui';

/**
 * About (docs/design/12 row 21, route /admin) — the about.dc.html transfer.
 * The prose is the prototype's, taken verbatim: it was written against the
 * repo's actual parser/validation behaviour and read better than anything a
 * rewrite produced. What is NOT taken verbatim is every number the prototype
 * hardcoded (owner decision O6): its README-sourced figures count R0 summary
 * rows, so the headline and "counted" grids here read LIVE from
 * /api/stats/overview, and the prototype's static engineering grid
 * (tables/migrations/lines-of-code) is dropped rather than left to drift.
 * "This build" is live from /api/build, health rows from
 * /api/system/overview, and the probe table fires the legacy diagnostics.js
 * endpoint checks as real GETs on load.
 */

const PROBLEMS = [
  { n: '01', k: 'Round 2 is cumulative — but not entirely', body: 'The second-round file reports totals for the whole map, so the parser subtracts the matched round 1 field by field. Except that 23 of the 57 fields are already per-round, because the game resets those variables between rounds. Subtracting them would zero them out. The parser carries that list; nothing downstream recalculates a differential.' },
  { n: '02', k: 'A map is two files that have to find each other', body: 'Round 1 and round 2 arrive minutes apart as separate files. Pairing is by map and a 45-minute window, with the side swap accounted for — the team that defended first attacks second, so "winner" means nothing until both halves are known.' },
  { n: '03', k: 'A session is not a date', body: 'An evening that starts at 22:40 and ends at 01:30 is one session, not two. Grouping is by a 60-minute inactivity gap and stored as gaming_session_id; every session query keys on that id rather than a calendar date, which is what keeps midnight crossovers intact.' },
  { n: '04', k: 'A player is a GUID', body: 'Names change mid-evening and get reused. Every aggregate groups by player_guid, never by name, and display names are resolved separately at render time.' },
];

const PIPELINE = [
  { k: 'Game server', meta: 'et:legacy', body: 'Writes a stats file per round. The Lua tracker writes telemetry alongside it.', color: 'var(--color-accent)' },
  { k: 'Download', meta: 'ssh · 60 s poll', body: 'SFTP transfer with integrity check. A Lua webhook races it and usually wins by about a minute.', color: 'var(--color-accent)' },
  { k: 'Parse', meta: 'r2 differential', body: 'Round-2 subtraction, R1/R2 pairing, session grouping, substitution detection, bot-round exclusion.', color: 'var(--color-accent-warm)' },
  { k: 'Validate', meta: 'six checkpoints', body: 'Integrity, duplicates, types, a seven-check aggregate comparison, per-insert verification, constraints.', color: 'var(--color-accent-warm)' },
  { k: 'PostgreSQL', meta: '101 tables', body: 'Schema managed by committed migrations with a checksum ledger. Editing an applied migration is caught at startup.', color: 'var(--color-pos)' },
  { k: 'Out', meta: '~3 s end to end', body: 'Discord post, this website, and the background workers for analysis and rendering.', color: 'var(--color-pos)' },
];

const CHECKS = [
  { k: 'File transfer', state: 'blocks', ok: true },
  { k: 'Duplicate guard', state: 'blocks', ok: true },
  { k: 'Parser validation', state: 'blocks', ok: true },
  { k: 'Aggregate compare', state: 'warns', ok: false },
  { k: 'Per-insert verify', state: 'blocks', ok: true },
  { k: 'Constraints', state: 'blocks', ok: true },
];

const SURFACES = [
  { k: 'Discord bot', meta: '107 commands · 21 cogs', body: 'Session summaries, per-player and per-map stats, head to head, availability polls, and the post-session digest.', color: 'var(--color-accent)' },
  { k: 'Website', meta: '247 endpoints · 48 routers', body: 'Player profiles, the session archive, a record book, the round replay, rivalries, and the rating.', color: 'var(--color-accent)' },
  { k: 'Lua webhook', meta: 'about 3 s', body: 'Round-end notification, real stopwatch timing on a surrender, team composition, pause tracking.', color: 'var(--color-accent-warm)' },
  { k: 'Proximity', meta: '29 tables · 1.26 gb', body: 'The 200 ms tracker and its analytics: engagements, crossfire, cohesion, trades, objective work.', color: 'var(--color-pos)' },
  { k: 'Greatshot', meta: 'demo pipeline', body: 'Upload a demo, get multi-kills and sprees detected, clips cut at exact timestamps, renders queued.', color: 'var(--color-accent-warm)' },
];

const PRINCIPLES = [
  { k: 'The session is the unit', body: 'Most surfaces answer "what happened last night" before "who is best ever".' },
  { k: 'Compared to your own baseline', body: 'Numbers are measured against your own recent form where possible, rather than ranking players against each other.' },
  { k: 'Sample size is respected', body: 'Ratings shrink toward the pool mean until there is enough evidence, so nobody reaches the top of a list on one good round.' },
];

const NOT_BUILT = [
  { k: 'A global all-time K/D ladder', why: 'a fixed group does not need a ranking that never moves' },
  { k: 'Web chat', why: 'conversation stays in Discord' },
  { k: 'Daily streaks and login rewards', why: 'nobody should be farming a website' },
  { k: 'Anything that needs manual feeding', why: 'if it goes stale when we stop typing, it does not belong here' },
];

const DEVS = [
  {
    who: 'ez / seareal', role: 'author · everything here',
    what: 'The whole thing: the parser and the validation layers, the round-2 differential and session logic, the proximity tracker with its analytics, the rating and scoring formulas, the Discord bot, the API and this website. Built one problem at a time.',
  },
  {
    who: 'slomix community', role: 'ideas · feedback · testing',
    what: 'Every surface here was argued about first. What gets built, what gets cut, and what was simply wrong comes out of the channel.',
  },
];

const THANKS = [
  { who: 'x0rnn (c0rn)', what: 'gamestats.lua and endstats — the source of the raw .txt files the parser reads.' },
  { who: 'Kimi (mittermichal)', what: 'Greatshot: the highlight detection and pipeline design that the demo analysis was adapted from.' },
  { who: 'ryzyk-krzysiek', what: 'ET:Legacy protocol 84/284 support in UberDemoTools.' },
  { who: 'mightycow', what: 'UberDemoTools itself, which reads every demo we analyse.' },
  { who: 'ET:Legacy team', what: 'keeping a twenty-two-year-old game alive and worth measuring.' },
];

const START = [
  { to: '/sessions2', k: 'Last night', body: 'The session that just happened, map by map, with who played.' },
  { to: '/profile', k: 'Your profile', body: 'Your own numbers against your own recent form, not a ladder.' },
  { to: '/proximity', k: 'Telemetry', body: 'The 200 ms feed: engagements, crossfire, trades, paths on the map.' },
  { to: '/uploads', k: 'Clips', body: 'Video from the group, plus what Greatshot cut out of uploaded demos.' },
];

const H2: React.CSSProperties = { fontSize: 26, letterSpacing: '0.03em', textTransform: 'uppercase', lineHeight: 1.1, margin: 0, fontWeight: 500 };
const P: React.CSSProperties = { fontSize: 16, lineHeight: 1.62, color: 'var(--color-text-300)', maxWidth: '62ch' };
const BOX: React.CSSProperties = { border: '1px solid var(--color-rule-700)', background: 'var(--color-ink-800)', padding: 14 };

function HeadlineFigures() {
  const overview = useOverview();
  if (overview.isPending) return <div style={{ padding: '20px 0' }}><Pending label="figures" /></div>;
  // isSuccess (not a null check the types already forbid): anything short
  // of a successful answer renders as unavailable.
  if (!overview.isSuccess) return <div style={{ padding: '20px 0' }}><Unavailable what="figures" /></div>;
  const d = overview.data;
  // _safe_val substitutes 0 per failed aggregate inside a 200 — same rule
  // as the landing figures: a zero renders as a dash, never as a count.
  const live = (n: number) => (n === 0 ? '—' : n.toLocaleString('en-US'));
  const tiles = [
    { k: 'rounds parsed', v: live(d.rounds) },
    { k: 'players known', v: live(d.players_all_time) },
    { k: 'fields per player, per round', v: '57' },
    { k: 'position samples', v: '200 ms' },
  ];
  return (
    <>
      {tiles.map((h) => (
        <div key={h.k} style={{ padding: '20px 0 18px' }}>
          <div className="m" style={{ fontSize: 32, lineHeight: 1 }}>{h.v}</div>
          <Lbl style={{ marginTop: 7 }}>{h.k}</Lbl>
        </div>
      ))}
    </>
  );
}

function Counted() {
  const overview = useOverview();
  if (overview.isPending) return <div style={{ padding: '18px 0' }}><Pending label="counted" /></div>;
  if (!overview.isSuccess) return <div style={{ padding: '18px 0' }}><Unavailable what="counted" /></div>;
  const d = overview.data;
  const live = (n: number) => (n === 0 ? '—' : n.toLocaleString('en-US'));
  const cells = [
    { k: 'kills', v: live(d.total_kills) },
    { k: 'rounds', v: live(d.rounds) },
    { k: 'sessions', v: live(d.sessions) },
    { k: 'players, all time', v: live(d.players_all_time) },
    { k: 'first round kept', v: d.rounds_since ?? '—' },
    { k: 'latest round', v: d.rounds_latest ?? '—' },
  ];
  return (
    <>
      {cells.map((c) => (
        <div key={c.k} style={{ padding: '18px 16px 16px 0', borderRight: '1px solid var(--color-rule-900)' }}>
          <div className="m" style={{ fontSize: 22, lineHeight: 1 }}>{c.v}</div>
          <Lbl style={{ fontSize: 9, marginTop: 6 }}>{c.k}</Lbl>
        </div>
      ))}
    </>
  );
}

function ThisBuild() {
  const build = useBuildInfo();
  return (
    <div data-parity="admin.build">
      <Lbl>this build</Lbl>
      <div style={{ ...BOX, marginTop: 12 }}>
        {build.isPending && <Pending label="build" />}
        {build.isError && <Unavailable what="build info" />}
        {build.data && (
          [
            // revision_short is null without a .git dir, the ledger null
            // when migrations are not packaged — a dash, not 'null'.
            { k: 'revision', v: build.data.revision_short ?? '—' },
            { k: 'started', v: build.data.started_at.replace('T', ' ').slice(0, 16) + ' utc' },
            { k: 'api contract', v: build.data.api_contract },
            { k: 'schema ledger', v: build.data.schema_ledger_max_file ?? '—' },
          ].map((b) => (
            <div key={b.k} style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, padding: '7px 0' }}>
              <Lbl style={{ fontSize: 9 }}>{b.k}</Lbl>
              <span className="m" style={{ fontSize: 12, color: 'var(--color-text-300)' }}>{b.v}</span>
            </div>
          ))
        )}
      </div>
      <Lbl style={{ fontSize: 9, marginTop: 10, lineHeight: 1.7 }}>
        the revision is the commit this process started from, frozen at import — so a checkout that
        moves underneath a running process cannot silently claim the new one. the contract hash is
        the live route table; two processes on different code get different hashes.
      </Lbl>
    </div>
  );
}

function Health() {
  const overview = useSystemOverview();
  // A failed 30 s poll must not keep green rows under the error message —
  // same derived-value rule as the full /system page.
  const data = overview.isError ? undefined : overview.data;
  return (
    <div data-parity="admin.health" style={{ marginTop: 26 }}>
      <Lbl>health</Lbl>
      <div style={{ marginTop: 12 }}>
        {overview.isPending && <Pending label="health" />}
        {overview.isError && <Unavailable what="health" />}
        {data?.stages.map((s) => (
          <div key={s.key} style={{ ...rowStyle, display: 'flex', alignItems: 'baseline', gap: 10, padding: '8px 0' }}>
            <StatusDot state={s.state === 'ok' ? 'ok' : s.state === 'warn' ? 'warn' : s.state === 'down' ? 'error' : 'idle'} />
            <span style={{ fontSize: 15, color: 'var(--color-text-300)' }}>{s.label}</span>
            <span className="m" style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--color-text-500)', textAlign: 'right' }}>{s.summary}</span>
          </div>
        ))}
      </div>
      <Link to="/system" style={{ ...lblStyle, fontSize: 9, display: 'inline-block', marginTop: 12, textDecoration: 'none' }}>
        full system page →
      </Link>
    </div>
  );
}

function ProbeTable() {
  const [results, setResults] = useState<Map<string, ProbeResult>>(new Map());
  useEffect(() => {
    let cancelled = false;
    void runProbes((result) => {
      if (cancelled) return;
      setResults((prev) => new Map(prev).set(result.probe.endpoint, result));
    });
    return () => { cancelled = true; };
  }, []);
  return (
    <div data-parity="admin.probes" style={{ marginTop: 26 }}>
      <Lbl>endpoint probes · live, fired on load</Lbl>
      <div style={{ marginTop: 12 }}>
        {API_PROBES.map((probe) => {
          const r = results.get(probe.endpoint);
          return (
            <div key={probe.endpoint} style={{ ...rowStyle, display: 'flex', alignItems: 'baseline', gap: 10, padding: '7px 0' }}>
              <StatusDot state={r ? (r.state === 'ok' ? 'ok' : probe.required ? 'error' : 'warn') : 'idle'} />
              <span style={{ fontSize: 14, color: 'var(--color-text-300)' }}>{probe.name}</span>
              <span className="m" style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--color-text-500)' }}>
                {r ? (r.state === 'ok' ? `${r.status} · ${r.ms} ms` : (r.status ?? 'unreachable')) : '…'}
              </span>
            </div>
          );
        })}
      </div>
      <Lbl style={{ fontSize: 9, marginTop: 10, lineHeight: 1.7 }}>
        the legacy diagnostics checks, kept: each row is a real GET from your browser. probes
        report reachability only — they are not parity, and the endpoint ratchet does not count them.
      </Lbl>
    </div>
  );
}

export function About() {
  return (
    <div style={{ paddingBottom: 40 }}>
      <div data-parity="admin.hero" style={{ paddingTop: 52, maxWidth: '74ch' }}>
        <Lbl>about</Lbl>
        <h1 style={{ fontSize: 44, letterSpacing: '0.02em', textTransform: 'uppercase', lineHeight: 1.08, margin: '14px 0 0', fontWeight: 500 }}>
          Slomix keeps the record of our games.
        </h1>
        <p style={{ ...P, marginTop: 22, maxWidth: '70ch' }}>
          ET:Legacy writes a file after every round. Slomix reads it, sorts out what stopwatch makes
          messy, and stores it — match stats plus a position feed from the server. Teams are whatever
          turns up, three a side or six, and the scoring grows with them. Three parts, one database:
          a Discord bot, this website, and a Lua tracker. The name is an old IRC channel where
          players from different Slovenian groups met up to play.
        </p>
      </div>

      <div data-parity="admin.figures" className="about-grid-4" style={{ marginTop: 44, borderTop: '1px solid var(--color-rule-700)', borderBottom: '1px solid var(--color-rule-900)' }}>
        <HeadlineFigures />
      </div>

      <div data-parity="admin.what-it-does" className="about-cols" style={{ marginTop: 52 }}>
        <div>
          <h2 style={H2}>What it does</h2>
          <p style={{ ...P, marginTop: 14 }}>
            ET:Legacy writes a stats file at the end of every round. Slomix reads those files,
            reconciles them into matches, and keeps them — 57 fields per player per round. That much
            is ordinary. What makes the dataset unusual is the second source: a Lua tracker samples
            every player's position, health, weapon, stance and speed every 200 ms, alongside
            per-shot hit regions, engagements, revives and objective work. A four-minute round
            produces roughly 3,400 records.
          </p>
          <p style={{ ...P, marginTop: 12 }}>
            A round ends, the server writes the file, and about three seconds later the result is in
            PostgreSQL and posted to Discord. Two paths feed it: SSH polling on a sixty-second
            cycle, and a Lua webhook that fires the moment the round ends. Whichever arrives first
            wins.
          </p>

          <div data-parity="admin.problems" style={{ marginTop: 34 }}>
            <Lbl>the four things stopwatch makes hard</Lbl>
            <div style={{ marginTop: 14 }}>
              {PROBLEMS.map((p) => (
                <div key={p.n} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: '34px 1fr', gap: 16, padding: '14px 0' }}>
                  <span className="m" style={{ fontSize: 13, color: 'var(--color-text-500)' }}>{p.n}</span>
                  <span>
                    <span style={{ display: 'block', fontSize: 18, letterSpacing: '0.03em', textTransform: 'uppercase', color: 'var(--color-text-100)' }}>{p.k}</span>
                    <span style={{ ...P, display: 'block', fontSize: 15, marginTop: 6 }}>{p.body}</span>
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div data-parity="admin.pipeline">
          <Lbl>the pipeline</Lbl>
          <div style={{ marginTop: 14 }}>
            {PIPELINE.map((s) => (
              <div key={s.k} style={{ ...BOX, marginBottom: 6, borderLeft: `2px solid ${s.color}` }}>
                <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
                  <span style={{ fontSize: 15, letterSpacing: '0.04em', textTransform: 'uppercase' }}>{s.k}</span>
                  <span className="m" style={{ fontSize: 11, color: 'var(--color-text-500)' }}>{s.meta}</span>
                </div>
                <div className="m" style={{ fontSize: 11, color: 'var(--color-text-400)', marginTop: 5, lineHeight: 1.6 }}>{s.body}</div>
              </div>
            ))}
          </div>

          <Lbl style={{ marginTop: 26 }}>six checks before a row is kept</Lbl>
          <div data-parity="admin.checks" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 6, marginTop: 12 }}>
            {CHECKS.map((c) => (
              <div key={c.k} style={{ ...BOX, padding: 10 }}>
                <div className="m" style={{ fontSize: 11, color: c.ok ? 'var(--color-pos)' : 'var(--color-accent-warm)' }}>{c.state}</div>
                <div style={{ fontSize: 14, letterSpacing: '0.03em', textTransform: 'uppercase', marginTop: 4 }}>{c.k}</div>
              </div>
            ))}
          </div>
          <Lbl style={{ fontSize: 9, marginTop: 10, lineHeight: 1.7 }}>
            four of the six block the import. the aggregate comparison warns instead — a mismatch
            there is usually a parser question, not a corrupt file.
          </Lbl>
        </div>
      </div>

      <div style={{ marginTop: 56, paddingTop: 26, borderTop: '1px solid var(--color-rule-900)' }}>
        <h2 style={H2} data-parity="admin.surfaces">The five surfaces</h2>
        <div className="about-grid-5" style={{ marginTop: 18 }}>
          {SURFACES.map((s) => (
            <div key={s.k}>
              <div style={{ height: 2, background: s.color }} />
              <div style={{ fontSize: 17, letterSpacing: '0.04em', textTransform: 'uppercase', marginTop: 10 }}>{s.k}</div>
              <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)', marginTop: 5 }}>{s.meta}</div>
              <div style={{ ...P, fontSize: 14, marginTop: 8 }}>{s.body}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 56, marginTop: 56, paddingTop: 26, borderTop: '1px solid var(--color-rule-900)' }}>
        <div>
          <h2 style={H2} data-parity="admin.principles">What we built on purpose</h2>
          <p style={{ ...P, marginTop: 14 }}>
            The project is built for a fixed group of players, not for growth, and that shapes what
            gets built.
          </p>
          <div style={{ marginTop: 16 }}>
            {PRINCIPLES.map((p) => (
              <div key={p.k} style={{ ...rowStyle, padding: '12px 0' }}>
                <div style={{ fontSize: 17, letterSpacing: '0.03em', textTransform: 'uppercase', color: 'var(--color-text-100)' }}>{p.k}</div>
                <div style={{ ...P, fontSize: 15, marginTop: 5 }}>{p.body}</div>
              </div>
            ))}
          </div>
        </div>
        <div>
          <h2 style={H2} data-parity="admin.not-built">And what we left out</h2>
          <p style={{ ...P, marginTop: 14 }}>
            Removing a page is as valuable as adding one, so these were decided against rather than
            postponed.
          </p>
          <div style={{ marginTop: 16 }}>
            {NOT_BUILT.map((n) => (
              <div key={n.k} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: '18px 1fr', gap: 12, padding: '11px 0', alignItems: 'baseline' }}>
                <span className="m" style={{ fontSize: 13, color: 'var(--color-neg)' }}>—</span>
                <span>
                  <span style={{ display: 'block', fontSize: 16, letterSpacing: '0.03em', textTransform: 'uppercase', color: 'var(--color-text-300)' }}>{n.k}</span>
                  <span className="m" style={{ display: 'block', fontSize: 11, color: 'var(--color-text-500)', marginTop: 3 }}>{n.why}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ marginTop: 56, paddingTop: 26, borderTop: '1px solid var(--color-rule-900)' }}>
        <h2 style={H2} data-parity="admin.counted">Counted, live</h2>
        <Lbl style={{ marginTop: 6 }}>
          not a public dataset — one group's games, straight from the database as you read this
        </Lbl>
        <div className="about-grid-6" style={{ marginTop: 20, borderTop: '1px solid var(--color-rule-700)' }}>
          <Counted />
        </div>
      </div>

      <div className="about-cols" style={{ marginTop: 56, paddingTop: 26, borderTop: '1px solid var(--color-rule-900)' }}>
        <div>
          <h2 style={H2} data-parity="admin.development">Development</h2>
          <p style={{ ...P, marginTop: 14 }}>
            Written and run by one person, with the group testing it every time we play.
          </p>
          <div style={{ marginTop: 16 }}>
            {DEVS.map((d) => (
              <div key={d.who} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: '150px 1fr', gap: 20, padding: '12px 0', alignItems: 'baseline' }}>
                <span>
                  <span className="m" style={{ display: 'block', fontSize: 14, color: 'var(--color-text-100)' }}>{d.who}</span>
                  <Lbl style={{ fontSize: 9, marginTop: 4 }}>{d.role}</Lbl>
                </span>
                <span style={{ ...P, fontSize: 15 }}>{d.what}</span>
              </div>
            ))}
          </div>

          <h2 style={{ ...H2, marginTop: 34 }} data-parity="admin.thanks">Thanks</h2>
          <p style={{ ...P, marginTop: 14 }}>For the pieces this was built on top of.</p>
          <div style={{ marginTop: 16 }}>
            {THANKS.map((t) => (
              <div key={t.who} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: '150px 1fr', gap: 20, padding: '12px 0', alignItems: 'baseline' }}>
                <span className="m" style={{ fontSize: 14, color: 'var(--color-text-100)' }}>{t.who}</span>
                <span style={{ ...P, fontSize: 15 }}>{t.what}</span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <ThisBuild />
          <Health />
          <ProbeTable />
        </div>
      </div>

      <div style={{ marginTop: 56, paddingTop: 26, borderTop: '1px solid var(--color-rule-900)' }}>
        <h2 style={H2} data-parity="admin.start">Where to start</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 20, marginTop: 18 }}>
          {START.map((s) => (
            <Link key={s.k} to={s.to} style={{ display: 'block', textDecoration: 'none', color: 'var(--color-text-100)' }}>
              <div style={{ height: 2, background: '#33322c' }} />
              <div style={{ fontSize: 17, letterSpacing: '0.04em', textTransform: 'uppercase', marginTop: 10 }}>{s.k}</div>
              <div style={{ ...P, fontSize: 14, marginTop: 6 }}>{s.body}</div>
            </Link>
          ))}
        </div>
      </div>

      <div className="m" style={{ display: 'flex', justifyContent: 'space-between', marginTop: 52, paddingTop: 14, borderTop: '1px solid var(--color-rule-900)', fontSize: 10, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--color-text-600, #4d4a44)' }}>
        <span>slomix · built for the et:legacy community</span>
        <span>github.com/iamez/slomix</span>
      </div>
    </div>
  );
}
