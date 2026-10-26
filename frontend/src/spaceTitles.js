import { useEffect, useState } from 'react';
import { getSpace } from './api.js';

const spaceTitleCache = new Map();

async function spaceTitle(spaceId) {
  const key = String(spaceId);
  if (spaceTitleCache.has(key)) return spaceTitleCache.get(key);
  try {
    const s = await getSpace(key);
    spaceTitleCache.set(key, s.title);
    return s.title;
  } catch {
    return `Space #${key}`;
  }
}

/** Titles for these space ids, keyed by id, filled in as they load. Cached for the session. */
export function useSpaceTitles(spaceIds) {
  const [titles, setTitles] = useState({});
  const key = [...new Set(spaceIds.map(String))].sort().join(',');
  useEffect(() => {
    let cancelled = false;
    const ids = key ? key.split(',') : [];
    Promise.all(ids.map((id) => spaceTitle(id).then((t) => [id, t]))).then((pairs) => {
      if (!cancelled) setTitles(Object.fromEntries(pairs));
    });
    return () => {
      cancelled = true;
    };
  }, [key]);
  return titles;
}
