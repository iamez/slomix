import { createRoot, type Root } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { lazy, Suspense } from 'react';
import type { ModernRouteContext } from './runtime/catalog';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Skeleton } from './components/Skeleton';
import './styles/tailwind.css';

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

const routeComponents: Record<string, React.LazyExoticComponent<React.ComponentType<{ params?: Record<string, string> }>>> = {
  home: lazy(() => import('./pages/Home')),
  records: lazy(() => import('./pages/Records')),
  leaderboards: lazy(() => import('./pages/Leaderboards')),
  maps: lazy(() => import('./pages/Maps')),
  'hall-of-fame': lazy(() => import('./pages/HallOfFame')),
  awards: lazy(() => import('./pages/Awards')),
  sessions2: lazy(() => import('./pages/Sessions2')),
  profile: lazy(() => import('./pages/Profile')),
  weapons: lazy(() => import('./pages/Weapons')),
  'retro-viz': lazy(() => import('./pages/RetroViz')),
  'session-detail': lazy(() => import('./pages/SessionDetail')),
  uploads: lazy(() => import('./pages/Uploads')),
  'upload-detail': lazy(() => import('./pages/UploadDetail')),
  greatshot: lazy(() => import('./pages/Greatshot')),
  'greatshot-demo': lazy(() => import('./pages/GreatshotDemo')),
  availability: lazy(() => import('./pages/Availability')),
  admin: lazy(() => import('./pages/Admin')),
  proximity: lazy(() => import('./pages/Proximity')),
  'proximity-player': lazy(() => import('./pages/ProximityPlayer')),
  'proximity-replay': lazy(() => import('./pages/ProximityReplay')),
  'proximity-teams': lazy(() => import('./pages/ProximityTeams')),
  'skill-rating': lazy(() => import('./pages/SkillRating')),
  story: lazy(() => import('./pages/Story')),
  rivalries: lazy(() => import('./pages/Rivalries')),
  replay: lazy(() => import('./pages/Replay')),
};

const mountedRoots = new WeakMap<HTMLElement, Root>();

function RouteShell({ viewId, params }: { viewId: string; params?: Record<string, string> }) {
  const Page = routeComponents[viewId];
  if (!Page) {
    return <div className="text-slate-400 text-center py-12">Not yet migrated.</div>;
  }
  return (
    <ErrorBoundary viewId={viewId}>
      <QueryClientProvider client={queryClient}>
        <Suspense fallback={<Skeleton variant="card" count={4} />}>
          <Page params={params} />
        </Suspense>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export async function mountRoute(
  container: HTMLElement,
  context: ModernRouteContext,
): Promise<{ unmount: () => void }> {
  const existingRoot = mountedRoots.get(container);
  if (existingRoot) {
    existingRoot.unmount();
    mountedRoots.delete(container);
  }

  const root = createRoot(container);
  root.render(<RouteShell viewId={context.viewId} params={context.params} />);
  mountedRoots.set(container, root);

  return {
    unmount() {
      const mountedRoot = mountedRoots.get(container);
      if (mountedRoot) {
        mountedRoot.unmount();
        mountedRoots.delete(container);
      }
    },
  };
}
