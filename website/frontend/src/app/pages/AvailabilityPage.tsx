/**
 * Phase 6 — availability, slice 1 (route availability). The surface has
 * THREE auth tiers and the page renders each as a STATE, never a failure:
 * anonymous (sign in), authenticated-but-unlinked (the backend's own words:
 * "Linked Discord account required"), and linked. The write is the core
 * interaction — my status per day — and it fails closed with the tier
 * prompt instead of a dead button. Linked-only forms (settings,
 * subscriptions, channel linking, promotion admin) are slice 2.
 */
import { useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Cluster, Stack } from '../components/layout';
import { Absent, Lbl, Meta, Pending, SectionHead, Unavailable, figure } from '../components/ui';
import { ApiError } from '../lib/api';
import {
  postMyAvailability, useAvailabilityAccess, useAvailabilitySettingsProbe,
  useAvailabilitySubscriptionsProbe, useAvailabilityWeek, useBetsMarketCurrent,
  useBetsWallet, usePlanningToday, usePromotionCampaign, usePromotionPreferences,
} from '../lib/queries';
import type { AvailabilityStatus } from '../lib/types';

const STATUSES: { key: AvailabilityStatus; label: string }[] = [
  { key: 'LOOKING', label: 'looking' },
  { key: 'AVAILABLE', label: 'available' },
  { key: 'MAYBE', label: 'maybe' },
  { key: 'NOT_PLAYING', label: 'out' },
];

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

function TierNote({ error, what }: { error: unknown; what: string }) {
  const tier = tierOf(error);
  if (tier === 'anonymous') return <Absent reason={`sign in with CONNECT ID to see ${what}`} />;
  if (tier === 'unlinked') return <Absent reason={`${what} needs a linked Discord account — the backend's own gate, rendered as a state`} />;
  return <Unavailable what={what} />;
}

export function AvailabilityPage() {
  const qc = useQueryClient();
  const access = useAvailabilityAccess();
  const authed = access.data?.authenticated === true;
  const from = useMemo(() => isoPlus(0), []);
  const to = useMemo(() => isoPlus(7), []);
  const week = useAvailabilityWeek(from, to, authed);
  const planning = usePlanningToday();
  const market = useBetsMarketCurrent();
  const wallet = useBetsWallet(authed);
  const campaign = usePromotionCampaign(authed);
  const prefs = usePromotionPreferences(authed);
  const settings = useAvailabilitySettingsProbe(authed);
  const subs = useAvailabilitySubscriptionsProbe(authed);
  const [saving, setSaving] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const setStatus = async (dateIso: string, status: AvailabilityStatus) => {
    setSaving(dateIso); setSaveError(null);
    try {
      await postMyAvailability(dateIso, status);
      await qc.invalidateQueries({ queryKey: ['availability-week'] });
      await qc.invalidateQueries({ queryKey: ['planning-today'] });
    } catch (e) {
      const tier = tierOf(e);
      setSaveError(tier === 'anonymous' ? 'sign in with CONNECT ID to submit availability'
        : tier === 'unlinked' ? 'submitting needs a linked Discord account'
        : 'saving failed — the server did not accept the change');
    } finally {
      setSaving(null);
    }
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
          : <Meta>a market is open — betting UI arrives in slice 2</Meta>)}
        {authed && wallet.isError && <TierNote error={wallet.error} what="your wallet" />}
      </div>

      {authed && (
        <div data-parity="availability.promotions">
          <SectionHead label="promotions" />
          {campaign.data && (campaign.data.campaign == null
            ? <div style={{ marginTop: 'var(--space-2)' }}><Absent reason="no promotion campaign is running" /></div>
            : <Meta>a campaign is running — details in slice 2</Meta>)}
          {campaign.isError && <TierNote error={campaign.error} what="campaigns" />}
          {prefs.data && (
            <Meta>
              promotions {prefs.data.allow_promotions ? 'on' : 'off'} · channel {prefs.data.preferred_channel}
              {' · '}timezone {prefs.data.timezone}
            </Meta>
          )}
        </div>
      )}

      {authed && (
        <div data-parity="availability.settings">
          <SectionHead label="settings & subscriptions" />
          <Stack gap={1} style={{ marginTop: 'var(--space-2)' }}>
            {settings.isError ? <TierNote error={settings.error} what="settings" />
              : settings.data != null ? <Meta>settings loaded — the editable form is slice 2</Meta> : null}
            {subs.isError ? <TierNote error={subs.error} what="subscriptions" />
              : subs.data != null ? <Meta>subscriptions loaded — management is slice 2</Meta> : null}
          </Stack>
        </div>
      )}
    </Stack>
  );
}
