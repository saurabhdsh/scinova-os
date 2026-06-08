import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { createProject, listProjects } from '../api/client';

const STORAGE_KEY = 'scinova_project_id';

const ProjectContext = createContext(null);

export function ProjectProvider({ children }) {
  const [projects, setProjects] = useState([]);
  const [activeProjectId, setActiveProjectIdState] = useState(
    () => localStorage.getItem(STORAGE_KEY) || '',
  );
  const [loading, setLoading] = useState(true);

  const refreshProjects = useCallback(async () => {
    const r = await listProjects();
    setProjects(r.data || []);
    return r.data || [];
  }, []);

  useEffect(() => {
    refreshProjects()
      .then((list) => {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored && list.some((p) => p.id === stored)) return;
        if (stored && !list.some((p) => p.id === stored)) {
          localStorage.removeItem(STORAGE_KEY);
          setActiveProjectIdState('');
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [refreshProjects]);

  const setActiveProjectId = useCallback((id) => {
    const next = id || '';
    setActiveProjectIdState(next);
    if (next) localStorage.setItem(STORAGE_KEY, next);
    else localStorage.removeItem(STORAGE_KEY);
  }, []);

  const createAndSelect = useCallback(async (name, description) => {
    const r = await createProject({ name, description });
    await refreshProjects();
    setActiveProjectId(r.data.id);
    return r.data;
  }, [refreshProjects, setActiveProjectId]);

  const activeProject = projects.find((p) => p.id === activeProjectId) || null;

  const value = useMemo(
    () => ({
      projects,
      activeProject,
      activeProjectId: activeProjectId || null,
      loading,
      setActiveProjectId,
      refreshProjects,
      createAndSelect,
    }),
    [projects, activeProject, activeProjectId, loading, setActiveProjectId, refreshProjects, createAndSelect],
  );

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useProject() {
  const ctx = useContext(ProjectContext);
  if (!ctx) {
    throw new Error('useProject must be used within ProjectProvider');
  }
  return ctx;
}
