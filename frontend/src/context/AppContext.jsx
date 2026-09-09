import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  getMe,
  getAuthToken,
  listSaved,
  login as loginRequest,
  logout as logoutRequest,
  readStoredUser,
  register as registerRequest,
  saveSpace,
  setAuthToken,
  storeUser,
  unsaveSpace,
} from '../api.js';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [persona, setPersona] = useState('renter');
  const [showNotes, setShowNotes] = useState(false);
  const [user, setUser] = useState(() => readStoredUser());
  const [saved, setSaved] = useState(() => new Set());
  const [savedItems, setSavedItems] = useState([]);
  const [authReady, setAuthReady] = useState(!getAuthToken());

  const applySaved = (items) => {
    setSavedItems(items);
    setSaved(new Set(items.map((item) => item.id)));
  };

  const refreshSaved = useCallback(async () => {
    if (!getAuthToken()) {
      applySaved([]);
      return;
    }
    const data = await listSaved();
    applySaved(data.items);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const token = getAuthToken();
    if (!token) {
      setAuthReady(true);
      return undefined;
    }

    (async () => {
      try {
        const me = await getMe();
        if (cancelled) return;
        setUser(me);
        storeUser(me);
        try {
          await refreshSaved();
        } catch {
          if (!cancelled) applySaved([]);
        }
      } catch {
        if (cancelled) return;
        setAuthToken(null);
        storeUser(null);
        setUser(null);
        applySaved([]);
      } finally {
        if (!cancelled) setAuthReady(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [refreshSaved]);

  const login = useCallback(
    async (email, password) => {
      const { token, user: nextUser } = await loginRequest(email, password);
      setAuthToken(token);
      storeUser(nextUser);
      setUser(nextUser);
      try {
        await refreshSaved();
      } catch {
        applySaved([]);
      }
      return nextUser;
    },
    [refreshSaved],
  );

  const register = useCallback(
    async (email, password, username) => {
      const { token, user: nextUser } = await registerRequest(email, password, username);
      setAuthToken(token);
      storeUser(nextUser);
      setUser(nextUser);
      applySaved([]);
      return nextUser;
    },
    [],
  );

  const logout = useCallback(async () => {
    await logoutRequest();
    setAuthToken(null);
    storeUser(null);
    setUser(null);
    applySaved([]);
  }, []);

  const toggleSaved = useCallback(
    async (id) => {
      if (!user) return false;
      const currentlySaved = saved.has(id);
      setSaved((prev) => {
        const next = new Set(prev);
        currentlySaved ? next.delete(id) : next.add(id);
        return next;
      });
      if (currentlySaved) {
        setSavedItems((prev) => prev.filter((item) => item.id !== id));
      }
      try {
        if (currentlySaved) await unsaveSpace(id);
        else await saveSpace(id);
        return true;
      } catch (err) {
        setSaved((prev) => {
          const next = new Set(prev);
          currentlySaved ? next.add(id) : next.delete(id);
          return next;
        });
        throw err;
      }
    },
    [saved, user],
  );

  const value = useMemo(
    () => ({
      persona,
      setPersona,
      isRenter: persona === 'renter',
      showNotes,
      toggleNotes: () => setShowNotes((v) => !v),
      user,
      authReady,
      login,
      register,
      logout,
      saved,
      savedItems,
      refreshSaved,
      isSaved: (id) => saved.has(id),
      toggleSaved,
    }),
    [persona, showNotes, user, authReady, login, register, logout, saved, savedItems, refreshSaved, toggleSaved],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}
