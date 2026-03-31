export type RouteMode = 'legacy' | 'modern';
export type MigrationWave = 'A' | 'B' | 'C';

export interface RouteSummary {
  viewId: string;
  label: string;
  description: string;
  mode: RouteMode;
  migrationWave: MigrationWave;
  surfaceType: string;
}

export interface ModernRouteContext {
  viewId: string;
  params?: Record<string, string>;
}

export const routeCatalog: RouteSummary[] = [
  { viewId: 'home', label: 'Home', description: 'Dashboard widgets and search', mode: 'modern', migrationWave: 'A', surfaceType: 'read-heavy' },
  { viewId: 'sessions', label: 'Sessions', description: 'Session browser and drill-down entry', mode: 'legacy', migrationWave: 'A', surfaceType: 'read-heavy' },
  { viewId: 'leaderboards', label: 'Leaderboards', description: 'Top-player rankings and period filters', mode: 'modern', migrationWave: 'A', surfaceType: 'read-heavy' },
  { viewId: 'maps', label: 'Maps', description: 'Historical map analytics', mode: 'modern', migrationWave: 'A', surfaceType: 'read-heavy' },
  { viewId: 'records', label: 'Records', description: 'All-time records and stat ceilings', mode: 'modern', migrationWave: 'A', surfaceType: 'read-heavy' },
  { viewId: 'awards', label: 'Awards', description: 'Awards leaderboards and round awards', mode: 'modern', migrationWave: 'A', surfaceType: 'read-heavy' },
  { viewId: 'profile', label: 'Profile', description: 'Player profile drill-down', mode: 'modern', migrationWave: 'A', surfaceType: 'read-heavy' },
  { viewId: 'weapons', label: 'Weapons', description: 'Weapon usage and weapon hall-of-fame', mode: 'modern', migrationWave: 'B', surfaceType: 'read-heavy' },
  { viewId: 'proximity', label: 'Proximity', description: 'Complex combat analytics and local map overlays', mode: 'modern', migrationWave: 'B', surfaceType: 'read-heavy' },
  { viewId: 'hall-of-fame', label: 'Hall of Fame', description: 'Historical hall-of-fame surface', mode: 'modern', migrationWave: 'B', surfaceType: 'read-heavy' },
  { viewId: 'retro-viz', label: 'Retro Viz', description: 'Round-level visual analytics', mode: 'modern', migrationWave: 'B', surfaceType: 'read-heavy' },
  { viewId: 'sessions2', label: 'Sessions 2.0', description: 'New session list and analytics drill-down', mode: 'modern', migrationWave: 'B', surfaceType: 'read-heavy' },
  { viewId: 'session-detail', label: 'Session Detail', description: 'Five-tab session analytics detail page', mode: 'modern', migrationWave: 'B', surfaceType: 'read-heavy' },
  { viewId: 'greatshot', label: 'Greatshot', description: 'Demo library hub and renders', mode: 'modern', migrationWave: 'C', surfaceType: 'mixed' },
  { viewId: 'greatshot-demo', label: 'Greatshot Demo', description: 'Demo detail and render queue actions', mode: 'modern', migrationWave: 'C', surfaceType: 'write/auth-heavy' },
  { viewId: 'uploads', label: 'Uploads', description: 'Upload library and sharing', mode: 'modern', migrationWave: 'C', surfaceType: 'write/auth-heavy' },
  { viewId: 'upload-detail', label: 'Upload Detail', description: 'Upload detail and download/share actions', mode: 'modern', migrationWave: 'C', surfaceType: 'mixed' },
  { viewId: 'availability', label: 'Availability', description: 'Planning and promotion flows', mode: 'modern', migrationWave: 'C', surfaceType: 'write/auth-heavy' },
  { viewId: 'admin', label: 'Admin', description: 'Operational diagnostics and tooling', mode: 'modern', migrationWave: 'C', surfaceType: 'write/auth-heavy' },
  { viewId: 'skill-rating', label: 'ET Rating', description: 'Individual performance skill rating (experimental)', mode: 'modern', migrationWave: 'C', surfaceType: 'read-heavy' },
  { viewId: 'rivalries', label: 'Rivalries', description: 'Head-to-head rivalry analysis', mode: 'legacy', migrationWave: 'C', surfaceType: 'read-heavy' },
  { viewId: 'story', label: 'Smart Stats', description: 'AI-narrated session summaries and momentum', mode: 'legacy', migrationWave: 'C', surfaceType: 'read-heavy' },
  { viewId: 'replay', label: 'Replay', description: 'Round timeline replay viewer', mode: 'legacy', migrationWave: 'C', surfaceType: 'read-heavy' },
];
