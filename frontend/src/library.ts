import { useCallback, useEffect, useState } from 'react';
import type { LibraryItem } from './types';

const KEY = 'mixverse.library.v1';
const EVENT = 'mixverse:library';
const LIMIT = 60;
export const SERVER_TTL_MS = 24 * 60 * 60 * 1000;

function read(): LibraryItem[] {
  try {
    const raw = localStorage.getItem(KEY);
    const items = raw ? (JSON.parse(raw) as LibraryItem[]) : [];
    return Array.isArray(items) ? items : [];
  } catch {
    return [];
  }
}

function write(items: LibraryItem[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(items.slice(0, LIMIT)));
  } catch {
    // Storage may be full or blocked; the library is a convenience, never required.
  }
  window.dispatchEvent(new Event(EVENT));
}

export function addToLibrary(item: Omit<LibraryItem, 'id' | 'createdAt'>) {
  const entry: LibraryItem = { ...item, id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, createdAt: Date.now() };
  write([entry, ...read().filter(existing => existing.audioUrl !== item.audioUrl)]);
}

export function isExpired(item: LibraryItem, now = Date.now()) {
  return now - item.createdAt > SERVER_TTL_MS;
}

export function useLibrary() {
  const [items, setItems] = useState<LibraryItem[]>(read);
  useEffect(() => {
    const sync = () => setItems(read());
    window.addEventListener(EVENT, sync);
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener(EVENT, sync);
      window.removeEventListener('storage', sync);
    };
  }, []);
  const remove = useCallback((id: string) => write(read().filter(item => item.id !== id)), []);
  const clear = useCallback(() => write([]), []);
  return { items, remove, clear };
}
