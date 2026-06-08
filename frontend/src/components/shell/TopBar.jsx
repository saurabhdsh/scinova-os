import { useCallback, useEffect, useRef, useState } from 'react';
import { Search, Bell, Maximize2, Minimize2, PanelRight, Plus, LogOut } from 'lucide-react';
import { useUser } from '../../context/UserContext';
import { useProject } from '../../context/ProjectContext';
import { getCollaborationActivity } from '../../api/client';
import CommandPalette from './CommandPalette';
import NotificationsMenu from './NotificationsMenu';
import NewProjectModal from './NewProjectModal';

export default function TopBar({ title, breadcrumb, onDockToggle, dockOpen }) {
  const { user, displayName, logout } = useUser();
  const {
    projects, activeProjectId, setActiveProjectId, createAndSelect,
  } = useProject();

  const [paletteOpen, setPaletteOpen] = useState(false);
  const [paletteQuery, setPaletteQuery] = useState('');
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [projectModalOpen, setProjectModalOpen] = useState(false);
  const [notificationCount, setNotificationCount] = useState(0);
  const [fullscreen, setFullscreen] = useState(false);
  const notifWrapRef = useRef(null);

  const refreshNotificationCount = useCallback(async () => {
    try {
      const r = await getCollaborationActivity();
      const count = (r.data?.open_risks?.length || 0) + (r.data?.pending_approvals?.length || 0);
      setNotificationCount(count);
    } catch {
      setNotificationCount(0);
    }
  }, []);

  useEffect(() => {
    refreshNotificationCount();
    const interval = setInterval(refreshNotificationCount, 60_000);
    return () => clearInterval(interval);
  }, [refreshNotificationCount]);

  useEffect(() => {
    const onKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPaletteQuery('');
        setPaletteOpen(true);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  useEffect(() => {
    const onFullscreenChange = () => {
      setFullscreen(Boolean(document.fullscreenElement));
    };
    document.addEventListener('fullscreenchange', onFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', onFullscreenChange);
  }, []);

  const openPalette = (query = '') => {
    setPaletteQuery(query);
    setPaletteOpen(true);
  };

  const toggleFullscreen = async () => {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else {
        await document.documentElement.requestFullscreen();
      }
    } catch {
      /* browser may block */
    }
  };

  const handleCreateProject = async (name, description) => {
    await createAndSelect(name, description);
  };

  return (
    <>
      <header className="shrink-0 h-[3.25rem] border-b border-cx-line bg-white/65 backdrop-blur-2xl relative z-40">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/80 to-transparent" />
        <div className="h-full px-4 flex items-center gap-4">
          <div className="flex items-center gap-2 min-w-0">
            {breadcrumb && (
              <span className="font-mono text-2xs text-cx-accent border border-cx-accent/20 px-2 py-0.5 rounded-lg bg-cx-accent/5">
                {breadcrumb}
              </span>
            )}
            <h2 className="font-display font-semibold text-cx-fg truncate">{title}</h2>
          </div>

          <div className="flex-1 max-w-md mx-auto hidden md:block">
            <button
              type="button"
              onClick={() => openPalette('')}
              className="relative w-full text-left"
            >
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-cx-accent pointer-events-none" size={16} />
              <span className="block w-full pl-10 pr-16 py-2 rounded-xl border border-cx-border bg-white/60 shadow-inner-soft text-sm text-cx-fgDim">
                Search documents, entities, agents…
              </span>
              <kbd className="absolute right-3 top-1/2 -translate-y-1/2 font-mono text-2xs text-cx-fgDim border border-cx-border px-1.5 py-0.5 rounded bg-cx-deep/50 pointer-events-none">
                ⌘K
              </kbd>
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => openPalette('')}
              className="md:hidden p-2 rounded-xl border border-cx-border bg-white/50 hover:border-cx-accent/30 transition-colors"
              title="Search"
            >
              <Search size={16} className="text-cx-fgMuted" />
            </button>

            <select
              value={activeProjectId || ''}
              onChange={(e) => setActiveProjectId(e.target.value || null)}
              className="hidden sm:block text-xs border border-cx-border rounded-xl px-3 py-1.5 bg-white/60 text-cx-fgMuted max-w-[180px]"
              title="Workspace scope"
            >
              <option value="">Personal workspace</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>

            <button
              type="button"
              onClick={() => setProjectModalOpen(true)}
              title="New shared project"
              className="p-2 rounded-xl border border-cx-border bg-white/50 hover:border-cx-accent/30 transition-colors"
            >
              <Plus size={16} className="text-cx-fgMuted" />
            </button>

            <div className="relative" ref={notifWrapRef}>
              <button
                type="button"
                onClick={() => {
                  setNotificationsOpen((v) => !v);
                  if (!notificationsOpen) refreshNotificationCount();
                }}
                title="Notifications"
                aria-expanded={notificationsOpen}
                className={`p-2 rounded-xl border transition-colors relative ${
                  notificationsOpen ? 'border-cx-accent/30 bg-cx-accent/5' : 'border-cx-border bg-white/50 hover:border-cx-accent/30'
                }`}
              >
                <Bell size={16} className="text-cx-fgMuted" />
                {notificationCount > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 min-w-[1rem] h-4 px-1 rounded-full bg-cx-danger text-white text-[10px] font-medium flex items-center justify-center">
                    {notificationCount > 9 ? '9+' : notificationCount}
                  </span>
                )}
              </button>
              <NotificationsMenu
                open={notificationsOpen}
                onClose={() => {
                  setNotificationsOpen(false);
                  refreshNotificationCount();
                }}
                onCountChange={setNotificationCount}
              />
            </div>

            <button
              type="button"
              onClick={toggleFullscreen}
              title={fullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
              className="p-2 rounded-xl border border-cx-border bg-white/50 hover:border-cx-accent/30 transition-colors hidden sm:block"
            >
              {fullscreen ? (
                <Minimize2 size={16} className="text-cx-fgMuted" />
              ) : (
                <Maximize2 size={16} className="text-cx-fgMuted" />
              )}
            </button>

            <button
              type="button"
              onClick={onDockToggle}
              title={dockOpen ? 'Close evidence panel' : 'Open evidence panel'}
              className={`p-2 rounded-xl border transition-colors ${dockOpen ? 'border-cx-accent/30 bg-cx-accent/5' : 'border-cx-border bg-white/50 hover:border-cx-accent/30'}`}
            >
              <PanelRight size={16} className="text-cx-fgMuted" />
            </button>

            {user && (
              <div className="flex items-center gap-2 pl-2 ml-1 border-l border-cx-line">
                <div className="hidden lg:block text-right min-w-0 max-w-[140px]">
                  <p className="text-xs font-medium text-cx-fg truncate">{displayName}</p>
                  <p className="text-2xs text-cx-fgDim capitalize truncate">{user.role}</p>
                </div>
                <button
                  type="button"
                  onClick={logout}
                  className="p-2 rounded-xl border border-cx-border bg-white/50 hover:border-cx-danger/30 hover:text-cx-danger transition-colors"
                  title="Sign out"
                >
                  <LogOut size={16} />
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <CommandPalette
        open={paletteOpen}
        initialQuery={paletteQuery}
        onClose={() => setPaletteOpen(false)}
      />

      <NewProjectModal
        open={projectModalOpen}
        onClose={() => setProjectModalOpen(false)}
        onCreate={handleCreateProject}
      />
    </>
  );
}
