/**
 * Phase 6 — availability (route availability). The surface has THREE auth
 * tiers and the page renders each as a STATE, never a failure: anonymous
 * (sign in), authenticated-but-unlinked (the backend's own words: "Linked
 * Discord account required"), and linked. The write is the core interaction
 * — my status per day — and it fails closed with the tier prompt instead of
 * a dead button (slice 1, #887).
 *
 * Slice 2 adds the linked forms and the market, each following the legacy
 * state machine rather than porting its markup (docs/design/12 route 20):
 *  - settings: five toggles + save; a 403 on an unverified channel is the
 *    backend's sentence, verbatim;
 *  - channels: telegram/signal link through a one-time token the user hands
 *    to the bot (`/link <token>`); 429 inside the minimum interval is the
 *    backend's "Try again in Ns", verbatim; unlink is a DELETE;
 *  - promotions: campaign status with its jobs; for a promoter, the preview
 *    (including the recipient list the legacy modal threw away) and the
 *    schedule action, 409 verbatim;
 *  - the market: pools, implied multiplier, my bet, and a stake — only while
 *    the market is 'open' and only for a signed-in viewer. No admin
 *    controls (owner, 2026-09-02): opening and settling stay in legacy.
 */
import { useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Cluster, Stack } from '../components/layout';
import { Absent, Chip, Lbl, Meta, Pending, SectionHead, Unavailable, figure } from '../components/ui';
import { ApiError } from '../lib/api';
import {
  deleteSubscription, postAvailabilitySettings, postBet, postCampaign, postLinkToken,
  postMyAvailability, useAvailabilityAccess, useAvailabilitySettings,
  useAvailabilitySubscriptions, useAvailabilityWeek, useBetsMarketCurrent, useBetsWallet,
  usePlanningToday, usePromotionCampaign, usePromotionPreferences, usePromotionPreview,
} from '../lib/queries';
import type { AvailabilitySettingsWrite } from '../lib/queries';
import type {
  AvailabilitySettings, AvailabilityStatus, AvailabilitySubscription, BetsMarket,
  BetsWallet, CampaignCreateResponse, LinkTokenResponse, PromotionCampaignPayload,
} from '../lib/types';

const STATUSES: { key: AvailabilityStatus; label: string }[] = [
  { key: 'LOOKING', label: 'looking' },
  { key: 'AVAILABLE', label: 'available' },
  { key: 'MAYBE', label: 'maybe' },
  { key: 'NOT_PLAYING', label: 'out' },
];

const LINKABLE = ['telegram', 'signal'] as const;
type Linkable = (typeof LINKABLE)[number];

function isoPlus(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function tierOf(error: unknown): 'anonymous' | 'unlinked' | null {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'anonymous';
    if (error.status === 403) return 'unlinked';
  }
  return null;
}

/** The backend's own sentence when it sent one; otherwise the tier prompt;
 *  otherwise a flat honest fallback. Never a paraphrase of a detail. */
function wordsOf(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.detail) return error.detail;
    if (error.status === 401) return 'sign in with CONNECT ID first';
    if (error.status === 403) return 'Linked Discord account required';
  }
  return fallback;
}

function TierNote({ error, what }: { error: unknown; what: string }) {
  const tier = tierOf(error);
  if (tier === 'anonymous') return <Absent reason={`sign in with CONNECT ID to see ${what}`} />;
  if (tier === 'unlinked') {
    // The backend's OWN words, verbatim — the fallback only covers a 403
    // whose body carried no detail.
    const words = error instanceof ApiError && error.detail ? error.detail : 'Linked Discord account required';
    return <Absent reason={`${what}: ${words}`} />;
  }
  return <Unavailable what={what} />;
}

const actionStyle = {
  all: 'unset', cursor: 'pointer', fontSize: 'var(--fs-caption)', letterSpacing: '0.06em',
  textTransform: 'uppercase', padding: '0 var(--space-1)', color: 'var(--color-accent)',
} as const;

const inputStyle = {
  background: 'transparent', border: '1px solid var(--color-rule-700)', color: 'var(--color-text-100)',
  fontSize: 'var(--fs-row)', padding: '0 var(--space-1)', width: 72,
} as const;

// ---------------------------------------------------------------------------
// the market

function multiplier(total: number, side: number): string {
  if (side <= 0) return '—';
  return `${(total / side).toFixed(2)}×`;
}

function MarketPanel({ market, wallet, authed, onBet }: {
  market: BetsMarket;
  wallet: BetsWallet | undefined;
  authed: boolean;
  onBet: (choice: 'team_a' | 'team_b', amount: number) => Promise<void>;
}) {
  const [amount, setAmount] = useState<string>(String(market.my_bet?.amount ?? 10));
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const pool = market.pool;
  const total = pool.total_pool;
  const label = (side: string) => (side === 'team_a' ? market.team_a_label : market.team_b_label);
  const canBet = authed && market.status === 'open';

  const place = async (choice: 'team_a' | 'team_b') => {
    const stake = Number.parseInt(amount, 10);
    if (!Number.isFinite(stake) || stake <= 0) { setNote('enter a positive stake'); return; }
    setBusy(true); setNote(null);
    try {
      await onBet(choice, stake);
      setNote(`bet placed — ${figure(stake)} on ${label(choice)}`);
    } catch (e) {
      setNote(wordsOf(e, 'the server did not accept the bet'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Stack gap={2} style={{ marginTop: 'var(--space-3)' }}>
      <Meta>
        {market.session_date ?? 'session'} · {market.status}
        {market.outcome ? ` · result: ${market.outcome === 'void' ? 'void (refunded)' : label(market.outcome)}` : ''}
      </Meta>
      {(['team_a', 'team_b'] as const).map((side) => (
        <Cluster key={side} gap={4} align="baseline" justify="between" className="row" style={{ padding: 'var(--space-1) 0', flexWrap: 'wrap' }}>
          <span className="m" style={{ fontSize: 'var(--fs-row)', minWidth: 140 }}>{label(side)}</span>
          <Cluster gap={4} align="baseline" style={{ flexWrap: 'wrap' }}>
            <Lbl>pool {figure(pool[side].pool)} · bets {figure(pool[side].bets)}</Lbl>
            <Lbl>{total > 0 ? `${Math.round((pool[side].pool / total) * 100)}%` : '0%'}</Lbl>
            <Lbl>{multiplier(total, pool[side].pool)}</Lbl>
          </Cluster>
          {canBet && (
            <button type="button" style={actionStyle} disabled={busy} onClick={() => place(side)} aria-label={`bet on ${label(side)}`} title={`bet on ${label(side)}`}>
              bet {label(side)}
            </button>
          )}
        </Cluster>
      ))}
      <Meta>total pool {figure(total)} · winners split it · points are just for fun</Meta>
      {market.my_bet && (market.status === 'settled' || market.my_bet.status !== 'open'
        ? <Meta>
            your bet: {figure(market.my_bet.amount)} on {label(market.my_bet.choice)} —{' '}
            {market.my_bet.status === 'won' ? `won ${figure(market.my_bet.payout)}`
              : market.my_bet.status === 'refunded' ? 'refunded' : market.my_bet.status}
          </Meta>
        : <Meta>your bet: {figure(market.my_bet.amount)} on {label(market.my_bet.choice)} · change any time before lock</Meta>)}
      {wallet && <Meta>balance {figure(wallet.balance)} · lifetime earned {figure(wallet.lifetime_earned)}</Meta>}
      {canBet && (
        <Cluster gap={3} align="baseline">
          <Lbl>stake</Lbl>
          <input aria-label="stake" type="number" min={1} value={amount} style={inputStyle}
            onChange={(e) => setAmount(e.target.value)} />
        </Cluster>
      )}
      {!authed && <Absent reason="sign in with CONNECT ID to place a bet" />}
      {authed && market.status !== 'open' && <Absent reason={`betting is ${market.status === 'settled' ? 'settled' : 'closed'} for this market`} />}
      {note && <Absent reason={note} />}
    </Stack>
  );
}

// ---------------------------------------------------------------------------
// settings & channels

type Toggle = keyof Pick<AvailabilitySettingsWrite,
  'discord_notify' | 'telegram_notify' | 'signal_notify' | 'sound_enabled' | 'availability_reminders_enabled'>;
const TOGGLES: { key: Toggle; label: string }[] = [
  { key: 'discord_notify', label: 'discord' },
  { key: 'telegram_notify', label: 'telegram' },
  { key: 'signal_notify', label: 'signal' },
  { key: 'sound_enabled', label: 'get-ready sound' },
  { key: 'availability_reminders_enabled', label: 'reminders' },
];

function writeOf(s: AvailabilitySettings): AvailabilitySettingsWrite {
  return {
    sound_enabled: s.sound_enabled,
    availability_reminders_enabled: s.availability_reminders_enabled,
    sound_cooldown_seconds: s.sound_cooldown_seconds,
    timezone: s.timezone,
    discord_notify: s.discord_notify,
    telegram_notify: s.telegram_notify,
    signal_notify: s.signal_notify,
  };
}

function SettingsForm({ settings, onSave }: {
  settings: AvailabilitySettings;
  onSave: (body: AvailabilitySettingsWrite) => Promise<void>;
}) {
  const [form, setForm] = useState<AvailabilitySettingsWrite>(() => writeOf(settings));
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  // A refetch (after a link/unlink) re-seeds the form: the server's answer
  // wins over a stale local copy.
  useEffect(() => { setForm(writeOf(settings)); }, [settings]);

  const save = async () => {
    setBusy(true); setNote(null);
    try {
      await onSave(form);
      setNote('settings saved');
    } catch (e) {
      setNote(wordsOf(e, 'saving failed — the server did not accept the change'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Stack gap={2}>
      <Cluster gap={2} style={{ flexWrap: 'wrap' }}>
        {TOGGLES.map((t) => (
          <Chip key={t.key} active={form[t.key]} label={t.label} title={`toggle ${t.label}`}
            onClick={() => setForm((f) => ({ ...f, [t.key]: !f[t.key] }))} />
        ))}
      </Cluster>
      <Cluster gap={4} align="baseline">
        <Meta>timezone {form.timezone} · sound cooldown {figure(form.sound_cooldown_seconds)} s</Meta>
        <button type="button" style={actionStyle} disabled={busy} onClick={save} title="save settings">save</button>
      </Cluster>
      {note && <Absent reason={note} />}
    </Stack>
  );
}

function ChannelRow({ sub, token, onLink, onUnlink }: {
  sub: AvailabilitySubscription;
  token: LinkTokenResponse | null;
  onLink: () => Promise<void>;
  onUnlink: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setNote(null);
    try { await fn(); } catch (e) { setNote(wordsOf(e, 'the server did not accept the change')); } finally { setBusy(false); }
  };
  const state = sub.verified ? 'linked & verified' : token ? 'token issued — waiting for the bot' : 'not linked';
  return (
    <Stack gap={1}>
      <Cluster gap={4} align="baseline" justify="between" className="row" style={{ padding: 'var(--space-1) 0', flexWrap: 'wrap' }}>
        <span className="m" style={{ fontSize: 'var(--fs-row)', minWidth: 110 }}>{sub.channel_type}</span>
        <Lbl>{state}{sub.channel_address ? ` · ${sub.channel_address}` : ''}{sub.enabled ? ' · on' : ' · off'}</Lbl>
        <Cluster gap={2}>
          {!sub.verified && (
            <button type="button" style={actionStyle} disabled={busy} onClick={() => run(onLink)} aria-label={`link ${sub.channel_type}`} title={`link ${sub.channel_type}`}>link</button>
          )}
          {(sub.verified || sub.channel_address || token) && (
            <button type="button" style={actionStyle} disabled={busy} onClick={() => run(onUnlink)} aria-label={`unlink ${sub.channel_type}`} title={`unlink ${sub.channel_type}`}>unlink</button>
          )}
        </Cluster>
      </Cluster>
      {token && !sub.verified && (
        <Meta>
          send <code>/link {token.token}</code> to the bot on {token.channel_type} · expires {token.expires_at}
        </Meta>
      )}
      {note && <Absent reason={note} />}
    </Stack>
  );
}

// ---------------------------------------------------------------------------
// promotions

function CampaignStatus({ campaign }: { campaign: PromotionCampaignPayload }) {
  const channels = Object.entries(campaign.channels_summary);
  return (
    <Stack gap={1}>
      <Meta>
        campaign {campaign.campaign_date} · {campaign.status} · {figure(campaign.recipient_count)} recipients
        {campaign.dry_run ? ' · dry run' : ''}
        {channels.length > 0 ? ` · ${channels.map(([c, n]) => `${c} ${figure(n)}`).join(', ')}` : ''}
      </Meta>
      {campaign.jobs.length === 0
        ? <Absent reason="no jobs scheduled for this campaign" />
        : (
          <Cluster gap={3} style={{ flexWrap: 'wrap' }}>
            {campaign.jobs.map((j) => (
              <Lbl key={j.id}>{j.job_type} · {j.status}{j.last_error ? ` · ${j.last_error}` : ''}</Lbl>
            ))}
          </Cluster>
        )}
    </Stack>
  );
}

function PromoterPanel({ onSchedule }: {
  onSchedule: (flags: { include_available: boolean; include_maybe: boolean; dry_run: boolean }) => Promise<CampaignCreateResponse>;
}) {
  // include_available defaults ON — the legacy modal's default, kept.
  const [flags, setFlags] = useState({ include_available: true, include_maybe: false });
  const [dryRun, setDryRun] = useState(false);
  const preview = usePromotionPreview(true, flags);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const schedule = async () => {
    setBusy(true); setNote(null);
    try {
      const r = await onSchedule({ ...flags, dry_run: dryRun });
      setNote(`campaign #${r.campaign_id} ${r.status} — ${figure(r.recipient_count)} recipients · reminder ${r.scheduled_times.reminder_2045_cet} · start ${r.scheduled_times.start_2100_cet}${r.dry_run ? ' · dry run' : ''}`);
    } catch (e) {
      setNote(wordsOf(e, 'the server did not schedule the campaign'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Stack gap={2} parity="availability.promote">
      <Cluster gap={2} style={{ flexWrap: 'wrap' }}>
        <Chip active={flags.include_available} label="include available" title="include AVAILABLE players"
          onClick={() => setFlags((f) => ({ ...f, include_available: !f.include_available }))} />
        <Chip active={flags.include_maybe} label="include maybe" title="include MAYBE players"
          onClick={() => setFlags((f) => ({ ...f, include_maybe: !f.include_maybe }))} />
        <Chip active={dryRun} label="dry run" title="send only to yourself" onClick={() => setDryRun((d) => !d)} />
        <button type="button" style={actionStyle} disabled={busy} onClick={schedule} title="schedule tonight's campaign">schedule</button>
      </Cluster>
      {preview.isPending && <Pending label="preview" />}
      {preview.isError && <Absent reason={`preview: ${wordsOf(preview.error, 'unavailable')}`} />}
      {preview.data && (
        <Stack gap={1}>
          <Meta>
            {preview.data.campaign_date} · reminder {preview.data.reminder_time_cet} CET · start {preview.data.target_time_cet} CET
            {' · '}{figure(preview.data.recipient_count)} recipients
            {' · '}{Object.entries(preview.data.channels_summary).map(([c, n]) => `${c} ${figure(n)}`).join(', ')}
          </Meta>
          {preview.data.recipients_preview.length === 0
            ? <Absent reason="nobody opted in matches these flags today" />
            : (
              <Cluster gap={3} style={{ flexWrap: 'wrap' }}>
                {preview.data.recipients_preview.map((r) => (
                  <Lbl key={`${r.display_name}-${r.selected_channel}`}>{r.display_name} · {r.status.toLowerCase()} · {r.selected_channel}</Lbl>
                ))}
              </Cluster>
            )}
        </Stack>
      )}
      {note && <Absent reason={note} />}
    </Stack>
  );
}

// ---------------------------------------------------------------------------

export function AvailabilityPage() {
  const qc = useQueryClient();
  const access = useAvailabilityAccess();
  const authed = access.data?.authenticated === true;
  const linked = authed && access.data?.linked_discord === true;
  const canPromote = authed && access.data?.can_promote === true;
  const from = useMemo(() => isoPlus(0), []);
  const to = useMemo(() => isoPlus(7), []);
  const week = useAvailabilityWeek(from, to, authed);
  const planning = usePlanningToday();
  const market = useBetsMarketCurrent();
  const wallet = useBetsWallet(authed);
  const campaign = usePromotionCampaign(authed);
  const prefs = usePromotionPreferences(authed);
  const settings = useAvailabilitySettings(authed);
  const subs = useAvailabilitySubscriptions(authed);
  const [saving, setSaving] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [tokens, setTokens] = useState<Partial<Record<Linkable, LinkTokenResponse>>>({});

  const setStatus = async (dateIso: string, status: AvailabilityStatus) => {
    setSaving(dateIso); setSaveError(null);
    try {
      await postMyAvailability(dateIso, status);
      await qc.invalidateQueries({ queryKey: ['availability-week'] });
      await qc.invalidateQueries({ queryKey: ['planning-today'] });
    } catch (e) {
      const tier = tierOf(e);
      const words = e instanceof ApiError && e.detail ? e.detail : null;
      setSaveError(tier === 'anonymous' ? 'sign in with CONNECT ID to submit availability'
        : tier === 'unlinked' ? (words ?? 'Linked Discord account required')
        : 'saving failed — the server did not accept the change');
    } finally {
      // Clear only OUR date: a click on another day mid-flight must not be
      // re-enabled by the earlier request settling (review on #887).
      setSaving((cur) => (cur === dateIso ? null : cur));
    }
  };

  const refreshLinked = async () => {
    await qc.invalidateQueries({ queryKey: ['availability-settings'] });
    await qc.invalidateQueries({ queryKey: ['availability-subscriptions'] });
  };

  const saveSettings = async (body: AvailabilitySettingsWrite) => {
    await postAvailabilitySettings(body);
    await refreshLinked();
  };

  const link = async (channel: Linkable) => {
    const t = await postLinkToken(channel);
    setTokens((cur) => ({ ...cur, [channel]: t }));
  };

  const unlink = async (channel: Linkable) => {
    await deleteSubscription(channel);
    setTokens((cur) => ({ ...cur, [channel]: undefined }));
    await refreshLinked();
  };

  const bet = async (choice: 'team_a' | 'team_b', amount: number) => {
    if (!market.data?.market) return;
    await postBet(market.data.market.id, choice, amount);
    await qc.invalidateQueries({ queryKey: ['bets-market-current'] });
    await qc.invalidateQueries({ queryKey: ['bets-wallet'] });
  };

  const schedule = async (flags: { include_available: boolean; include_maybe: boolean; dry_run: boolean }) => {
    const r = await postCampaign(flags);
    await qc.invalidateQueries({ queryKey: ['promotion-campaign'] });
    return r;
  };

  return (
    <Stack gap={7} style={{ paddingTop: 'var(--space-7)' }}>
      <Stack gap={2}>
        <Lbl>planning · availability</Lbl>
        <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: 'var(--track-title)', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
          who is playing this week
        </h1>
        {access.data && (
          <Meta>
            {access.data.authenticated
              ? access.data.linked_discord
                ? 'signed in with a linked Discord account'
                : 'signed in — Discord not linked, so submitting is off'
              : 'browsing anonymously — counts only, sign in with CONNECT ID to take part'}
          </Meta>
        )}
      </Stack>

      <div data-parity="availability.week">
        <SectionHead label="the week" aside={<span className="lbl">{from} → {to}</span>} />
        {week.isPending && <Pending label="availability" />}
        {week.isError && <Unavailable what="availability" />}
        {week.data && (
          <Stack gap={2} style={{ marginTop: 'var(--space-3)' }}>
            {week.data.days.map((d) => (
              <Cluster key={d.date} gap={4} align="baseline" justify="between" className="row" style={{ padding: 'var(--space-1) 0', flexWrap: 'wrap' }}>
                <span className="m" style={{ fontSize: 'var(--fs-row)', minWidth: 110 }}>{d.date}</span>
                <Cluster gap={4} align="baseline" style={{ flexWrap: 'wrap' }}>
                  {STATUSES.map((s) => (
                    <span key={s.key} className="lbl" style={{ fontSize: 'var(--fs-caption)', color: (d.counts[s.key] ?? 0) > 0 ? 'var(--color-text-100)' : 'var(--color-text-500)' }}>
                      {s.label} {figure(d.counts[s.key] ?? 0)}
                    </span>
                  ))}
                </Cluster>
                <Cluster gap={2}>
                  {STATUSES.map((s) => (
                    <button key={s.key} type="button"
                      onClick={() => setStatus(d.date, s.key)}
                      disabled={saving === d.date}
                      aria-pressed={d.my_status === s.key}
                      title={`set ${s.label} for ${d.date}`}
                      style={{ all: 'unset', cursor: 'pointer', fontSize: 'var(--fs-caption)', letterSpacing: '0.06em', textTransform: 'uppercase', padding: '0 var(--space-1)', color: d.my_status === s.key ? 'var(--color-accent)' : 'var(--color-text-400)' }}>
                      {s.label}
                    </button>
                  ))}
                </Cluster>
              </Cluster>
            ))}
            {saveError && <Absent reason={saveError} />}
          </Stack>
        )}
      </div>

      <div data-parity="availability.planning-today">
        <SectionHead label="tonight" />
        {planning.isPending && <Pending label="planning" />}
        {planning.isError && <Unavailable what="planning" />}
        {planning.data && (
          <Stack gap={2} style={{ marginTop: 'var(--space-3)' }}>
            <Meta>
              {planning.data.session_ready.ready
                ? `session ready — ${figure(planning.data.session_ready.looking_count)} looking (threshold ${figure(planning.data.session_ready.threshold)})`
                : `${figure(planning.data.session_ready.looking_count)} of ${figure(planning.data.session_ready.threshold)} needed are looking`}
            </Meta>
            <Cluster gap={3} style={{ flexWrap: 'wrap' }}>
              {planning.data.participants.map((p) => (
                <span key={p.user_id} className="lbl" style={{ fontSize: 'var(--fs-caption)' }}>
                  {p.display_name ?? `#${p.user_id}`} · {p.status.toLowerCase()}
                </span>
              ))}
            </Cluster>
            {planning.data.is_mock && (
              <Absent reason="this backend serves MOCK planning data and says so — nothing here is a real evening" />
            )}
          </Stack>
        )}
      </div>

      <div data-parity="availability.bets">
        <SectionHead label="the market" />
        {market.isPending && <Pending label="market" />}
        {market.isError && <Unavailable what="market" />}
        {market.data && (market.data.market == null
          ? <div style={{ marginTop: 'var(--space-2)' }}><Absent reason="no market is open right now" /></div>
          : <MarketPanel market={market.data.market} wallet={wallet.data} authed={authed} onBet={bet} />)}
        {authed && wallet.isError && <TierNote error={wallet.error} what="your wallet" />}
      </div>

      {authed && (
        <div data-parity="availability.promotions">
          <SectionHead label="promotions" />
          <Stack gap={3} style={{ marginTop: 'var(--space-2)' }}>
            {campaign.data && (campaign.data.campaign == null
              ? <Absent reason="no promotion campaign is running" />
              : <CampaignStatus campaign={campaign.data.campaign} />)}
            {campaign.isError && <TierNote error={campaign.error} what="campaigns" />}
            {prefs.data && (
              <Meta>
                promotions {prefs.data.allow_promotions ? 'on' : 'off'} · channel {prefs.data.preferred_channel}
                {' · '}timezone {prefs.data.timezone}
              </Meta>
            )}
            {canPromote
              ? <PromoterPanel onSchedule={schedule} />
              : linked
                ? <Absent reason="scheduling a campaign needs promoter permission" />
                : null}
          </Stack>
        </div>
      )}

      {authed && (
        <div data-parity="availability.settings">
          <SectionHead label="settings & subscriptions" />
          <Stack gap={3} style={{ marginTop: 'var(--space-2)' }}>
            {settings.isPending && <Pending label="settings" />}
            {settings.isError && <TierNote error={settings.error} what="settings" />}
            {settings.data && <SettingsForm settings={settings.data} onSave={saveSettings} />}
            {subs.isError && <TierNote error={subs.error} what="subscriptions" />}
            {subs.data && (
              <Stack gap={1} parity="availability.channels">
                {subs.data.subscriptions
                  .filter((s): s is AvailabilitySubscription & { channel_type: Linkable } =>
                    (LINKABLE as readonly string[]).includes(s.channel_type))
                  .map((s) => (
                    <ChannelRow key={s.channel_type} sub={s} token={tokens[s.channel_type] ?? null}
                      onLink={() => link(s.channel_type)} onUnlink={() => unlink(s.channel_type)} />
                  ))}
              </Stack>
            )}
          </Stack>
        </div>
      )}
    </Stack>
  );
}
