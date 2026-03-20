// Centralized proximity metric definitions — used by InfoTip tooltips across the Proximity page.

export interface MetricDef {
  label: string;
  unit: string;
  oneLiner: string;
  detail: string;
  howMeasured?: string;
}

export const METRICS: Record<string, MetricDef> = {
  engagement: {
    label: 'Engagement',
    unit: '',
    oneLiner: 'A tracked combat encounter between two players.',
    detail:
      'An engagement starts when a player deals >1 HP damage to an enemy. ' +
      'It ends when one player dies, escapes (moves 300+ game units away for 5 seconds), ' +
      'or the 15-second timeout expires.',
    howMeasured:
      'The Lua tracker on the game server monitors damage events in real time and groups them into engagements.',
  },

  avg_duration: {
    label: 'Avg Fight Duration',
    unit: 'ms',
    oneLiner: 'Average length of each combat engagement in milliseconds.',
    detail:
      'Shorter fights mean faster eliminations. Longer fights may indicate evasive play or drawn-out duels. ' +
      'Typical ET fights last 800\u20133000 ms.',
    howMeasured: 'Measured from the first damage event to the kill/escape/timeout that ends the engagement.',
  },

  trade_kill: {
    label: 'Trade Kill',
    unit: 'ms',
    oneLiner: 'A revenge kill \u2014 your teammate avenges your death within 3 seconds.',
    detail:
      'When you die, a trade kill happens if a teammate kills your attacker within 3000 ms. ' +
      'High trade rates mean the team reacts quickly to losses and denies the enemy any advantage.',
    howMeasured: 'The tracker links death events to subsequent kills on the same target within 3000 ms.',
  },

  trade_rate: {
    label: 'Trade Rate',
    unit: '%',
    oneLiner: 'Percentage of deaths that were avenged by a teammate within 3 seconds.',
    detail:
      'A 40%+ trade rate is strong \u2014 it means nearly half of all deaths are quickly avenged. ' +
      'Low trade rates suggest players are fighting alone or teammates are too far away to help.',
  },

  crossfire: {
    label: 'Crossfire',
    unit: '',
    oneLiner: 'Two or more teammates attacking the same enemy from different angles.',
    detail:
      'A crossfire is detected when 2+ teammates engage the same enemy from positions that form a 45\u00b0+ ' +
      'angle, within 2000 game units (\u224833 meters) of each other. Crossfire is extremely hard to defend against.',
    howMeasured:
      'The tracker calculates angular separation between teammates attacking the same target and flags pairs exceeding 45\u00b0.',
  },

  crossfire_rate: {
    label: 'Crossfire Rate',
    unit: '%',
    oneLiner: 'Percentage of kills that involved crossfire positioning.',
    detail:
      'Higher crossfire rates indicate coordinated team positioning. ' +
      'Elite teams consistently create crossfire angles, making 1v1 duels nearly impossible for enemies.',
  },

  spawn_timing: {
    label: 'Spawn Timing',
    unit: 'score 0\u20131',
    oneLiner: 'How well-timed your kills are relative to enemy respawn waves.',
    detail:
      'ET:Legacy uses timed respawn waves (usually every 20\u201330 seconds). ' +
      'A score of 1.0 means you killed the enemy right after they spawned (maximum time denied before they return). ' +
      'A score of 0.0 means you killed them just before their respawn wave (minimal impact \u2014 they\u2019re back instantly).',
    howMeasured:
      'The tracker compares each kill\u2019s timestamp against the enemy team\u2019s respawn timer cycle.',
  },

  team_cohesion: {
    label: 'Team Cohesion',
    unit: 'u (game units)',
    oneLiner: 'How close together the team moves \u2014 measured by formation tightness.',
    detail:
      'Cohesion is the average distance of each player from the team\u2019s center point (centroid). ' +
      'Lower values mean tighter formations. In ET, ~300 units \u2248 5 meters. ' +
      'Good cohesion (~400\u2013800u) means teammates can support each other quickly.',
    howMeasured: 'Position samples are taken every second; centroid dispersion is averaged over the round.',
  },

  reaction_return_fire: {
    label: 'Return Fire',
    unit: 'ms',
    oneLiner: 'Time to shoot back after being hit.',
    detail:
      'Measures how quickly a player fires their first shot after taking damage. ' +
      'Faster return fire (<300 ms) indicates strong reflexes and combat awareness.',
    howMeasured: 'The tracker records the timestamp of incoming damage and the player\u2019s next outgoing damage event.',
  },

  reaction_dodge: {
    label: 'Dodge',
    unit: 'ms',
    oneLiner: 'Time to start evasive movement after being hit.',
    detail:
      'Measures how quickly a player changes movement direction after receiving damage. ' +
      'Good dodge times (<200 ms) suggest the player reacts instinctively to threats.',
    howMeasured: 'The tracker detects velocity vector changes following a damage event.',
  },

  reaction_support: {
    label: 'Support',
    unit: 'ms',
    oneLiner: 'Time for a teammate to engage your attacker after you take damage.',
    detail:
      'When you get hit, support time measures how fast a nearby teammate starts shooting at your attacker. ' +
      'Fast support (<500 ms) indicates excellent team awareness.',
    howMeasured:
      'The tracker links damage-received events to the next outgoing damage from a teammate toward the same attacker.',
  },

  distance: {
    label: 'Distance',
    unit: 'u (game units)',
    oneLiner: 'Distance between players in game units.',
    detail:
      'ET:Legacy uses its own distance unit. Roughly 300 game units \u2248 5 meters (one sprint-second). ' +
      'Close combat is <200u, medium range 200\u2013600u, long range 600u+.',
  },

  power_rating: {
    label: 'Power Rating',
    unit: 'score',
    oneLiner: 'Composite combat effectiveness score across 5 skill axes.',
    detail:
      'Combines Aggression (engagement dominance), Awareness (dodge & reaction speed), ' +
      'Teamplay (crossfire & trade participation), Timing (spawn timing efficiency), ' +
      'and Mechanical (aim accuracy & kill rate) into a single score. Higher = more impactful player.',
    howMeasured: 'Each axis is normalized 0\u20131 against the player pool, then weighted and summed.',
  },

  movement_speed: {
    label: 'Movement',
    unit: 'u/s',
    oneLiner: 'Average movement speed in game units per second.',
    detail:
      'Sprint speed in ET is ~300 u/s. Higher average speed indicates aggressive positioning and map control. ' +
      'Low speed may mean camping or defending.',
  },

  escape_rate: {
    label: 'Escape Rate',
    unit: '%',
    oneLiner: 'Percentage of engagements where the player survived.',
    detail:
      'An engagement ends in escape when the player moves 300+ units away from the attacker and stays away for 5 seconds. ' +
      'High escape rates suggest strong movement skills and map awareness.',
  },

  focus_fire: {
    label: 'Focus Fire',
    unit: 'score 0\u20131',
    oneLiner: 'Coordinated multi-attacker damage burst on a single target.',
    detail:
      'Focus fire occurs when 2+ attackers concentrate damage on one enemy within a tight time window. ' +
      'The score combines timing tightness (60%) and DPS concentration (40%). ' +
      'Higher scores indicate better-coordinated team fire.',
    howMeasured:
      'The Lua tracker identifies engagements with 2+ attackers and computes focus_score = timing_tightness * 0.6 + dps_score * 0.4.',
  },
};

// Scope selector hint texts
export const SCOPE_HINTS: Record<string, string> = {
  session: 'Showing data for the selected gaming session (one continuous play period).',
  all: 'Aggregated data across all sessions in the selected time range.',
  custom: 'Filtered by specific date, map, or round.',
};

// Leaderboard tab help texts
export const LEADERBOARD_HELP: Record<string, string> = {
  power:
    'Composite score combining engagement dominance, movement efficiency, crossfire participation, ' +
    'trade success, spawn timing, and reaction speed. Higher = more impactful player.',
  spawn:
    'Measures how well-timed your kills are relative to enemy respawn waves. ' +
    '1.0 = killed right after respawn (maximum time denied), 0.0 = killed just before respawn (minimal impact).',
  crossfire:
    'Top duos creating crossfire angles \u2014 two teammates attacking the same enemy from 45\u00b0+ separation. ' +
    'Crossfire is extremely hard to defend against and marks strong team coordination.',
  trades:
    'Fastest and most prolific traders. A trade kill avenges a teammate\u2019s death within 3 seconds. ' +
    'High trade counts mean the team never lets a death go unpunished.',
  reactions:
    'Quickest return fire after being hit. Measures raw reflexes \u2014 the time from taking damage to firing the first shot back. ' +
    'Also shows dodge speed (evasive movement) and support speed (teammate assistance).',
  survivors:
    'Highest escape rate from engagements. Players who survive by moving 300+ units from the attacker for 5 seconds. ' +
    'High escape rates signal exceptional movement and map awareness.',
  movement:
    'Speed and distance leaders. Average movement speed (u/s), sprint percentage, and total distance covered. ' +
    'ET sprint speed is ~300 u/s.',
  focus_fire:
    'Top targets of coordinated team fire. Focus score combines timing tightness (how simultaneously attackers deal damage) ' +
    'and DPS concentration into a 0\u20131 score. Higher = better-coordinated fire.',
};
