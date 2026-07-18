export const VIEW_PATHS = {
  home: '/',
  artists: '/artists',
  designer: '/designer',
  community: '/community',
  build: '/build',
  admin: '/admin',
};

const PATH_VIEWS = Object.fromEntries(
  Object.entries(VIEW_PATHS).map(([view, path]) => [path, view]),
);

export function viewFromLocation(location = window.location) {
  const legacyView = location.hash.replace(/^#/, '');
  if (['designer', 'community', 'admin'].includes(legacyView)) return legacyView;

  const path = location.pathname.length > 1
    ? location.pathname.replace(/\/+$/, '')
    : location.pathname;
  return PATH_VIEWS[path] || 'home';
}

export function navigateToView(view, { replace = false } = {}) {
  const path = VIEW_PATHS[view] || VIEW_PATHS.home;
  window.history[replace ? 'replaceState' : 'pushState']({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}
