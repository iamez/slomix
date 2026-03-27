import { cn } from '../../lib/cn';

export type PlayerArchetype =
  | 'pressure_engine'
  | 'medic_anchor'
  | 'silent_assassin'
  | 'frontline_warrior'
  | 'wall_breaker'
  | 'objective_specialist'
  | 'trade_master'
  | 'survivor'
  | 'chaos_agent';

interface ArchetypeDef {
  icon: string;
  label: string;
  color: string;
  bg: string;
  border: string;
}

const ARCHETYPES: Record<PlayerArchetype, ArchetypeDef> = {
  pressure_engine:      { icon: '\uD83D\uDD25', label: 'PRESSURE ENGINE',      color: 'text-rose-400',    bg: 'bg-rose-500/10',    border: 'border-rose-500/25' },
  medic_anchor:         { icon: '\uD83D\uDC89', label: 'MEDIC ANCHOR',         color: 'text-emerald-400', bg: 'bg-emerald-500/10',  border: 'border-emerald-500/25' },
  silent_assassin:      { icon: '\uD83C\uDFAF', label: 'SILENT ASSASSIN',      color: 'text-cyan-400',    bg: 'bg-cyan-500/10',     border: 'border-cyan-500/25' },
  frontline_warrior:    { icon: '\u26A1',        label: 'FRONTLINE WARRIOR',    color: 'text-amber-400',   bg: 'bg-amber-500/10',    border: 'border-amber-500/25' },
  wall_breaker:         { icon: '\uD83D\uDEE1\uFE0F', label: 'WALL BREAKER',   color: 'text-purple-400',  bg: 'bg-purple-500/10',   border: 'border-purple-500/25' },
  objective_specialist: { icon: '\uD83D\uDD27', label: 'OBJECTIVE SPECIALIST', color: 'text-blue-400',    bg: 'bg-blue-500/10',     border: 'border-blue-500/25' },
  trade_master:         { icon: '\uD83E\uDD1D', label: 'TRADE MASTER',         color: 'text-teal-400',    bg: 'bg-teal-500/10',     border: 'border-teal-500/25' },
  survivor:             { icon: '\uD83C\uDFC3', label: 'SURVIVOR',             color: 'text-lime-400',    bg: 'bg-lime-500/10',     border: 'border-lime-500/25' },
  chaos_agent:          { icon: '\uD83D\uDCA5', label: 'CHAOS AGENT',          color: 'text-orange-400',  bg: 'bg-orange-500/10',   border: 'border-orange-500/25' },
};

interface ArchetypeBadgeProps {
  archetype: PlayerArchetype;
  className?: string;
  size?: 'sm' | 'md';
}

export function ArchetypeBadge({ archetype, className, size = 'md' }: ArchetypeBadgeProps) {
  const def = ARCHETYPES[archetype] ?? ARCHETYPES.frontline_warrior;

  return (
    <span className={cn(
      'inline-flex items-center gap-1.5 rounded-full border font-bold uppercase tracking-wider',
      def.bg, def.border, def.color,
      size === 'sm' ? 'px-2 py-0.5 text-[9px]' : 'px-3 py-1 text-[10px]',
      className,
    )}>
      <span>{def.icon}</span>
      <span>{def.label}</span>
    </span>
  );
}

export function getArchetypeDef(archetype: PlayerArchetype): ArchetypeDef {
  return ARCHETYPES[archetype] ?? ARCHETYPES.frontline_warrior;
}
