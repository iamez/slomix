import { render, screen, waitFor, within } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { PlayerProfilePage } from './PlayerProfile';
import profile from './__fixtures__/api_players_identifier_profile.json';
import skillForm from './__fixtures__/api_skill_player_identifier_form.json';
import skillHistory from './__fixtures__/api_skill_player_identifier_history.json';
import memoryCard from './__fixtures__/api_players_identifier_memory_card.json';

/** The player page against the RECORDED profile (vid, sections=all). */
function fixtureFetch(input: RequestInfo | URL): Promise<Response> {
  const path = String(input).split('?')[0];
  if (/^\/api\/players\/[^/]+\/profile$/.test(path)) {
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(profile) } as Response);
  }
  // Phase 7: the two rating trends, recorded from the dev server.
  if (/^\/api\/skill\/player\/[^/]+\/form$/.test(path)) {
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(skillForm) } as Response);
  }
  if (/^\/api\/skill\/player\/[^/]+\/history$/.test(path)) {
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(skillHistory) } as Response);
  }
  if (/^\/api\/players\/[^/]+\/memory-card$/.test(path)) {
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(memoryCard) } as Response);
  }
  return Promise.reject(new Error(`unexpected endpoint: ${path}`));
}

function renderProfile(id: string | null, fetchImpl = fixtureFetch) {
  vi.stubGlobal('fetch', vi.fn(fetchImpl));
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[id === null ? '/profile' : `/profile/${id}`]}>
        <Routes>
          <Route path="/profile" element={<PlayerProfilePage />} />
          <Route path="/profile/:id" element={<PlayerProfilePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('PlayerProfilePage', () => {
  it('renders the recorded player: identity, rating and lifetime figures', async () => {
    renderProfile('D8423F90');
    await waitFor(() => expect(screen.getByText('vid')).toBeInTheDocument());
    // ET rating from the recording, three decimals (a rank, not a rounding).
    expect(screen.getByText('0.747')).toBeInTheDocument();
    expect(screen.getByText(/veteran/)).toBeInTheDocument();
    // Lifetime: 1,760 rounds and the 874 — 875 split.
    expect(screen.getAllByText('1,760').length).toBeGreaterThan(0);
    expect(screen.getByText('874 — 875')).toBeInTheDocument();
    // DPM is derived from damage/time, not invented: 3,575,214 / (683785/60).
    expect(screen.getByText('314')).toBeInTheDocument();
  });

  it('weapon rows keep the head-hit wording and the recorded ordering', async () => {
    renderProfile('D8423F90');
    await waitFor(() => expect(screen.getByText('Mp40')).toBeInTheDocument());
    expect(screen.getByText(/head hits, not headshot kills/)).toBeInTheDocument();
    // Recorded Mp40: 8,306 kills, 42.7% accuracy, 9,910 head hits.
    expect(screen.getByText('8,306')).toBeInTheDocument();
    expect(screen.getAllByText('42.7%').length).toBeGreaterThan(0);
  });

  it('a section that is unavailable says so instead of rendering an empty shape', async () => {
    const noMovement = {
      ...(profile as object),
      movement: { available: false, tracks: 0, avg_speed: null, peak_speed: null, sprint_pct: null, avg_distance_per_life: null, stance: null },
    };
    renderProfile('D8423F90', (input) => {
      const path = String(input).split('?')[0];
      if (/^\/api\/players\/[^/]+\/profile$/.test(path)) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(noMovement) } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByText('movement: unavailable')).toBeInTheDocument());
    // …and an AVAILABLE-but-empty section reads differently (no data, not broken).
    expect(screen.queryByText('no movement recorded yet')).toBeNull();
  });

  it('an available but empty section reads as no data', async () => {
    const noMaps = { ...(profile as object), maps: { available: true, maps: [] } };
    renderProfile('D8423F90', (input) => {
      const path = String(input).split('?')[0];
      if (/^\/api\/players\/[^/]+\/profile$/.test(path)) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(noMaps) } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByText('no map history recorded yet')).toBeInTheDocument());
    expect(screen.queryByText('map history: unavailable')).toBeNull();
  });

  it('a round with no attributed winner shows a dash, never a loss', async () => {
    const rows = (profile as { recent_matches: { matches: Record<string, unknown>[] } }).recent_matches.matches;
    const undecided = {
      ...(profile as object),
      recent_matches: { available: true, matches: [{ ...rows[0], round_id: 99999, result: null }] },
    };
    renderProfile('D8423F90', (input) => {
      const path = String(input).split('?')[0];
      if (/^\/api\/players\/[^/]+\/profile$/.test(path)) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(undecided) } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByText(/last rounds/)).toBeInTheDocument());
    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBeGreaterThan(0);
  });

  it('without an id the page asks for one and calls nothing', async () => {
    const spy = vi.fn(fixtureFetch);
    renderProfile(null, spy);
    await waitFor(() => expect(screen.getByText(/Pick a player/)).toBeInTheDocument());
    expect(spy).not.toHaveBeenCalled();
  });

  it('nemeses and victims lead with the figure each list ranks by', async () => {
    renderProfile('D8423F90');
    await waitFor(() => expect(screen.getByText(/the people/)).toBeInTheDocument());
    // The recorded pair tops BOTH lists (.olz kills vid most AND is killed
    // most) — legitimate, since the backend sorts the same pairs two ways.
    // Nemeses must lead with kills ON the player (872), victims with kills
    // BY the player (1096); printing one fixed order made them look alike.
    // The caption must name the right actor: the nemesis figure is what THEY
    // did to this player (rivalries_service's player-as-victim query), the
    // victim figure what this player did to them.
    expect(screen.getByText('their kills on this player')).toBeInTheDocument();
    expect(screen.getByText("this player's kills on them")).toBeInTheDocument();
    expect(screen.getAllByText('872').length).toBeGreaterThan(0);
    expect(screen.getAllByText('1096').length).toBeGreaterThan(0);
  });

  it('a section that is unavailable carries NO list — the page must not crash', async () => {
    // The real shape of an unavailable/failed section: {available:false,
    // reason} and nothing else (players_profile_router `_ok`). The first
    // version spread `.weapons` before SectionBody ever rendered.
    const stripped = {
      ...(profile as object),
      weapons: { available: false, reason: 'error' },
      relationships: { available: false, reason: 'error' },
      maps: { available: false, reason: 'error' },
      recent_matches: { available: false, reason: 'error' },
      hit_regions: { available: false, reason: 'error' },
      movement: { available: false, reason: 'error' },
    };
    renderProfile('D8423F90', (input) => {
      const path = String(input).split('?')[0];
      if (/^\/api\/players\/[^/]+\/profile$/.test(path)) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(stripped) } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByText('vid')).toBeInTheDocument());
    expect(screen.getByText('weapon stats: unavailable')).toBeInTheDocument();
    expect(screen.getByText('map history: unavailable')).toBeInTheDocument();
    expect(screen.getByText('recent rounds: unavailable')).toBeInTheDocument();
  });

  it('requests only the sections it renders, never the heavy pair', async () => {
    const spy = vi.fn(fixtureFetch);
    renderProfile('D8423F90', spy);
    await waitFor(() => expect(screen.getByText('vid')).toBeInTheDocument());
    const url = String(spy.mock.calls[0][0]);
    // aim (16.9 s cold) and advanced (11.1 s cold) are not on this page.
    expect(url).toContain('sections=');
    expect(url).not.toContain('all');
    expect(url).not.toContain('aim');
    expect(url).not.toContain('advanced');
    expect(url).toContain('weapons');
  });

  it('teammate rows lead with synergy, the metric the list is ordered by', async () => {
    renderProfile('D8423F90');
    await waitFor(() => expect(screen.getByText(/best alongside/)).toBeInTheDocument());
    expect(screen.getByText(/synergy = dpm delta together/)).toBeInTheDocument();
    // Recorded top teammate: synergy 82 over 6 rounds at 66.7% together.
    expect(screen.getAllByText('+82').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/6 rd · 66\.7%/).length).toBeGreaterThan(0);
  });

  it('an unavailable identity still identifies the player by guid', async () => {
    const noIdentity = { ...(profile as object), identity: { available: false, reason: 'error' } };
    renderProfile('D8423F90', (input) => {
      const path = String(input).split('?')[0];
      if (/^\/api\/players\/[^/]+\/profile$/.test(path)) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(noIdentity) } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByText('identity: unavailable')).toBeInTheDocument());
    // The top-level guid always exists, so the page never renders a nameless
    // header — and the rest of the profile still draws.
    expect(screen.getAllByText(/D8423F90/).length).toBeGreaterThan(0);
    expect(screen.getByText('Mp40')).toBeInTheDocument();
  });

  it('the display name is not listed as an alias of itself', async () => {
    renderProfile('D8423F90');
    await waitFor(() => expect(screen.getByText('vid')).toBeInTheDocument());
    // The recording carries `vid` as both the name and the only alias.
    expect(screen.queryByText(/also vid/)).toBeNull();
  });

  it('an unrated player and an undecided record are named, not hidden', async () => {
    const bare = {
      ...(profile as object),
      skill: { available: false, reason: 'not rated' },
      streaks: { available: false, reason: 'no decided rounds' },
    };
    renderProfile('D8423F90', (input) => {
      const path = String(input).split('?')[0];
      if (/^\/api\/players\/[^/]+\/profile$/.test(path)) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(bare) } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByText('vid')).toBeInTheDocument());
    // The rating area stays put and explains itself instead of vanishing.
    expect(screen.getByText('not rated yet')).toBeInTheDocument();
    expect(screen.getByText('no decided rounds yet')).toBeInTheDocument();
    expect(screen.getAllByText('et rating').length).toBe(1);
  });

  it('an alt names its primary, and a spent leave does not', async () => {
    const withLink = (link: unknown) => ({
      ...(profile as object),
      identity: { ...(profile as { identity: object }).identity, identity_link: link },
    });
    const active = { role: 'alt', link_type: 'sick_leave', primary_guid: 'FB0EC840', primary_name: 'ownator', active: true, since: '2026-08-11' };
    renderProfile('D8423F90', (input) => {
      const path = String(input).split('?')[0];
      if (/^\/api\/players\/[^/]+\/profile$/.test(path)) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(withLink(active)) } as Response);
      }
      return fixtureFetch(input);
    });
    // The attribution is followable: the response carries the primary's guid,
    // so the name IS that profile's link, not a name to go search for by hand
    // (which is also why the wording is asserted apart from the name — the
    // name now lives in a child element).
    await waitFor(() => expect(screen.getByRole('link', { name: 'ownator' })).toBeInTheDocument());
    expect(screen.getByRole('link', { name: 'ownator' })).toHaveAttribute('href', '/profile/FB0EC840');
    expect(screen.getByText(/alt of/)).toBeInTheDocument();
    expect(screen.getByText(/on sick leave/)).toBeInTheDocument();
  });

  it('an attributed name without a guid stays plain text, not a dead link', async () => {
    const noGuid = { role: 'alt', link_type: 'sick_leave', primary_name: 'ownator', active: true };
    renderProfile('D8423F90', (input) => {
      const path = String(input).split('?')[0];
      if (/^\/api\/players\/[^/]+\/profile$/.test(path)) {
        return Promise.resolve({
          ok: true, status: 200,
          json: () => Promise.resolve({
            ...(profile as object),
            identity: { ...(profile as { identity: object }).identity, identity_link: noGuid },
          }),
        } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByText(/alt of ownator/)).toBeInTheDocument());
    expect(screen.queryByRole('link', { name: 'ownator' })).toBeNull();
  });

  it('a primary names its active alts only', async () => {
    const primary = {
      role: 'primary',
      alts: [
        { alt_guid: 'EF561EAA', alt_name: 'carniee', link_type: 'sick_leave', active: true, since: '2026-08-11' },
        { alt_guid: 'AAAA1111', alt_name: 'oldalt', link_type: 'sick_leave', active: false, since: '2026-01-01' },
      ],
    };
    renderProfile('D8423F90', (input) => {
      const path = String(input).split('?')[0];
      if (/^\/api\/players\/[^/]+\/profile$/.test(path)) {
        return Promise.resolve({
          ok: true, status: 200,
          json: () => Promise.resolve({
            ...(profile as object),
            identity: { ...(profile as { identity: object }).identity, identity_link: primary },
          }),
        } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByRole('link', { name: 'carniee' })).toBeInTheDocument());
    expect(screen.getByRole('link', { name: 'carniee' })).toHaveAttribute('href', '/profile/EF561EAA');
    expect(screen.getByText(/also plays as/)).toBeInTheDocument();
    expect(screen.queryByText(/oldalt/)).toBeNull();
  });

  it('a failed streak query is not reported as an undecided record', async () => {
    const shapes = [
      { reason: 'error', expect: 'streaks: unavailable' },
      { reason: 'no decided rounds', expect: 'no decided rounds yet' },
    ];
    for (const s of shapes) {
      const body = { ...(profile as object), streaks: { available: false, reason: s.reason } };
      const view = renderProfile('D8423F90', (input) => {
        const path = String(input).split('?')[0];
        if (/^\/api\/players\/[^/]+\/profile$/.test(path)) {
          return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
        }
        return fixtureFetch(input);
      });
      await waitFor(() => expect(screen.getByText(s.expect)).toBeInTheDocument());
      view.unmount();
      vi.restoreAllMocks();
    }
  });
});

// ---------------------------------------------------------------------------
// phase 7 — the two rating trends
//
// The header showed a rating with no history behind it: legacy has both a
// "your form" block (player-profile.js:696) and an ET-Rating timeline
// (:772), and neither had been migrated.

describe('PlayerProfile — rating trends', () => {
  it('form is rank-vs-self, and says so in the server\'s own words', async () => {
    renderProfile('AAAA1111');
    // 86.5 against a 100 baseline: the composite headline and its delta.
    await waitFor(() => expect(screen.getByText('86.5')).toBeInTheDocument());
    expect(screen.getByText('▼ 13.5%')).toBeInTheDocument();
    // ⛔ The sentence is the server's, not a paraphrase. A form number that
    // reads as a ladder position is the single misreading this endpoint
    // exists to prevent, and the page must not invent softer wording for it.
    expect(screen.getByText(/rank-vs-self/)).toBeInTheDocument();
    // Every breakdown row, with its own baseline beside it.
    expect(screen.getByText('Damage / min')).toBeInTheDocument();
    expect(screen.getByText('vs 276')).toBeInTheDocument();
  });

  it('⛔ each breakdown row draws its OWN series, not just the composite', async () => {
    // The series arrived on every load and went nowhere: the page read
    // `composite` and ignored the `metrics` block beside it. One sparkline for
    // the composite plus one per breakdown row that has a series.
    const { container } = renderProfile('AAAA1111');
    await waitFor(() => expect(screen.getByText('86.5')).toBeInTheDocument());
    const section = container.querySelector('[data-parity="profile.form"]');
    expect(section).not.toBeNull();
    const sparks = within(section as HTMLElement).getAllByRole('img', { name: 'trend' });
    // composite + the six metrics the recording carries.
    expect(sparks.length).toBe(1 + skillForm.composite.breakdown.length);
  });

  it('the rating timeline is newest first and shows the running figure', async () => {
    renderProfile('AAAA1111');
    // ⚠️ Wait on the DATA, not on the heading: the SectionHead renders while
    // the query is still in flight, so waiting for it proves nothing and the
    // assertions below then run against an empty section.
    await waitFor(() => expect(screen.getByText('0.6042')).toBeInTheDocument());  // last session
    expect(screen.getByText('-0.0077')).toBeInTheDocument();  // its delta
    expect(screen.getByText('6 sessions · 30d')).toBeInTheDocument();
  });

  it('⛔ the timeline is newest first — an order nobody asserted is an order that drifts', async () => {
    // The previous test only proved both figures EXIST. Reversing the list
    // leaves both on the page, so it survived a mutation until this ran.
    const { container } = renderProfile('AAAA1111');
    await waitFor(() => expect(screen.getByText('0.6042')).toBeInTheDocument());
    // ⚠️ Scoped to the section: the profile shows dates elsewhere too (last
    // seen, the recent-rounds table), and a page-wide query silently mixed
    // them in — the first version of this assertion failed on a date from
    // another panel, which is a false alarm, not a finding.
    const section = container.querySelector('[data-parity="profile.rating-history"]');
    expect(section).not.toBeNull();
    const dates = within(section as HTMLElement)
      .getAllByText(/^2026-\d\d-\d\d$/).map((el) => el.textContent);
    expect(dates[0]).toBe('2026-09-01');
    expect(dates[dates.length - 1]).toBe('2026-08-17');
  });

  it('⛔ a newcomer has NO baseline, which is not a zero delta', async () => {
    // ⚠️ SYNTHETIC, and deliberately so: the recorded player has a baseline
    // for every metric, so the recording cannot exercise `delta_pct: null` —
    // the state the type documents and `is_new` names. A corpus that contains
    // only one side of a two-sided field cannot fail on the other, which is
    // exactly how "±0%" survived a mutation here.
    const newcomer = {
      ...skillForm,
      composite: { ...skillForm.composite, delta_pct: null, baseline: null, is_new: true },
    };
    renderProfile('AAAA1111', (input) => {
      const path = String(input).split('?')[0];
      if (/skill\/player\/[^/]+\/form$/.test(path)) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(newcomer) } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByText('no baseline yet')).toBeInTheDocument());
    expect(screen.queryByText('±0%')).not.toBeInTheDocument();
  });

  it('⛔ a null delta is the FIRST session, not a flat one', async () => {
    // The oldest row carries delta: null. Rendering it as 0 would claim the
    // player's rating did not move that night, which is a different fact from
    // "there was nothing to move from" — the same null-is-not-zero split the
    // form's `no baseline yet` makes one section above.
    renderProfile('AAAA1111');
    await waitFor(() => expect(screen.getByText('2026-08-17')).toBeInTheDocument());
    expect(screen.getByText('first')).toBeInTheDocument();
    expect(screen.queryByText('+0')).not.toBeInTheDocument();
  });

  it('a failed trend is unavailable and does not take the page with it', async () => {
    renderProfile('AAAA1111', (input) => {
      const path = String(input).split('?')[0];
      if (/skill\/player/.test(path)) {
        return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({ detail: 'x' }) } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByText(/form: unavailable/i)).toBeInTheDocument());
    expect(screen.getByText(/rating history: unavailable/i)).toBeInTheDocument();
    // The rest of the profile is untouched — five instruments, five states.
    expect(screen.getByText('rating over time')).toBeInTheDocument();
  });
});

describe('PlayerProfile — memory card', () => {
  it('renders every fact the server sends, with its sub-line', async () => {
    renderProfile('AAAA1111');
    await waitFor(() => expect(screen.getByText('Best round ever')).toBeInTheDocument());
    expect(screen.getByText('28 kills')).toBeInTheDocument();
    expect(screen.getByText('etl_sp_delivery · 2025-03-23')).toBeInTheDocument();
    expect(screen.getByText('Longest killing spree')).toBeInTheDocument();
    expect(screen.getByText(/never a ladder/)).toBeInTheDocument();
  });

  it('⛔ these are CAREER facts, not the season ones wrapped shows', async () => {
    // The recorded career best round is 28 KILLS on etl_sp_delivery; wrapped's
    // same-named card is a best DPM for the season. If someone ever wires this
    // section to the wrapped payload because the labels match, this fails.
    const { container } = renderProfile('AAAA1111');
    await waitFor(() => expect(screen.getByText('Signature map')).toBeInTheDocument());
    // ⚠️ Scoped: the Maps section lists `supply` too, so a page-wide query
    // finds two and fails on the ambiguity rather than on the code.
    const section = container.querySelector('[data-parity="profile.memory-card"]');
    expect(within(section as HTMLElement).getByText('supply')).toBeInTheDocument();
    // career signature = lift over the player's own average, not win rate
    expect(screen.getByText('+50% vs your average · 218 rounds')).toBeInTheDocument();
  });

  it('a failed keepsake says so instead of vanishing', async () => {
    // ⛔ Legacy renders nothing at all on failure. A section that disappears
    // silently is indistinguishable from one that has no data, and the new
    // convention is that a missing thing names itself.
    renderProfile('AAAA1111', (input) => {
      const path = String(input).split('?')[0];
      if (/memory-card$/.test(path)) {
        return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({ detail: 'x' }) } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByText(/memory card: unavailable/i)).toBeInTheDocument());
  });
});

/** The three cheap sections the legacy profile drew and the new page never
 *  requested (ledger 2026-09-08): name history, gathers, combat timing.
 *  Asserted against the recording, not a paraphrase of it. */
it('shows the recorded name history, gather record and combat timing', async () => {
  renderProfile('D8423F90');
  const rec = profile as unknown as {
    nick_history: { names: { name: string; uses: number }[] };
    gather_summary: { wins: number; losses: number; gathers: number };
    combat_timing: { time_to_kill: { median_ms: number; kills: number }; return_fire: { median_ms: number; coverage_pct: number } };
  };
  await waitFor(() => expect(screen.getByText(/known as/)).toBeInTheDocument());
  const top = rec.nick_history.names[0];
  expect(screen.getByText(`${top.name} · ${top.uses.toLocaleString('en-US')} rounds`)).toBeInTheDocument();
  expect(screen.getByText(`${rec.gather_summary.gathers} played`)).toBeInTheDocument();
  expect(screen.getByText(new RegExp(`^${rec.gather_summary.wins}–${rec.gather_summary.losses}`))).toBeInTheDocument();
  expect(screen.getByText(`${(rec.combat_timing.time_to_kill.median_ms / 1000).toFixed(2)} s`)).toBeInTheDocument();
  expect(screen.getByText(new RegExp(`over ${rec.combat_timing.time_to_kill.kills.toLocaleString('en-US')} kills`))).toBeInTheDocument();
  expect(screen.getByText(new RegExp(`covers ${rec.combat_timing.return_fire.coverage_pct} % of deaths`))).toBeInTheDocument();
});
