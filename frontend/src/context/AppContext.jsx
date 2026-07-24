import { createContext, useContext, useMemo, useState } from 'react';
import { listings } from '../data.js';

const AppContext = createContext(null);

// Seed the watchlist with the first four spaces (matches the Saved screen).
const seedSaved = () => new Set(listings.slice(0, 4).map((l) => l.id));

export function AppProvider({ children }) {
  const [persona, setPersona] = useState('renter'); // 'renter' | 'lister'
  const [showNotes, setShowNotes] = useState(false); // wireframe annotations
  const [saved, setSaved] = useState(seedSaved);

  const value = useMemo(
    () => ({
      persona,
      setPersona,
      isRenter: persona === 'renter',
      showNotes,
      toggleNotes: () => setShowNotes((v) => !v),
      saved,
      isSaved: (id) => saved.has(id),
      toggleSaved: (id) =>
        setSaved((prev) => {
          const next = new Set(prev);
          next.has(id) ? next.delete(id) : next.add(id);
          return next;
        }),
    }),
    [persona, showNotes, saved]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}
