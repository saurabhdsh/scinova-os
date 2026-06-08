import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { getMe } from '../api/client';
import { getCurrentUser, logout, saveCurrentUser } from '../lib/auth';

const UserContext = createContext(null);

export function UserProvider({ children }) {
  const [user, setUser] = useState(getCurrentUser);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    const r = await getMe();
    const next = {
      user_id: r.data.id,
      username: r.data.username,
      role: r.data.role,
      full_name: r.data.full_name,
    };
    setUser(next);
    saveCurrentUser(next);
    return next;
  }, []);

  useEffect(() => {
    refreshUser()
      .catch(() => logout())
      .finally(() => setLoading(false));
  }, [refreshUser]);

  const value = useMemo(
    () => ({
      user,
      loading,
      isAdmin: user?.role === 'admin',
      displayName: user?.full_name || user?.username || 'User',
      logout,
      refreshUser,
    }),
    [user, loading, refreshUser],
  );

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
}

export function useUser() {
  const ctx = useContext(UserContext);
  if (!ctx) {
    throw new Error('useUser must be used within UserProvider');
  }
  return ctx;
}
