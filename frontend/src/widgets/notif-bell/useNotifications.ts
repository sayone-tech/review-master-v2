import { useCallback, useEffect, useState } from "react";
import { getBell, markAllRead, markRead } from "./api";
import type { NotificationRow } from "./types";

export function useNotifications() {
  const [count, setCount] = useState(0);
  const [items, setItems] = useState<NotificationRow[]>([]);
  const [loaded, setLoaded] = useState(false);

  const fetchBell = useCallback(async () => {
    try {
      const data = await getBell();
      setCount(data.unread_count);
      setItems(data.items);
      setLoaded(true);
    } catch {
      // Bell is best-effort — silently swallow transient errors.
    }
  }, []);

  // Pitfall 7: initial fetch BEFORE setting up the 60s interval — avoids
  // a flash where the bell renders with count=0 then jumps to the real count.
  useEffect(() => {
    void fetchBell();
    const id = setInterval(() => {
      void fetchBell();
    }, 60_000);
    return () => clearInterval(id);
  }, [fetchBell]);

  // Immediately re-fetch when sync completes so the bell updates without
  // waiting for the next 60s poll tick.
  useEffect(() => {
    const handler = () => void fetchBell();
    window.addEventListener("notifications:refresh", handler);
    return () => window.removeEventListener("notifications:refresh", handler);
  }, [fetchBell]);

  const markReadAndNavigate = async (n: NotificationRow) => {
    // Optimistic: decrement count and flip is_read locally.
    setCount((c) => Math.max(0, c - (n.is_read ? 0 : 1)));
    setItems((arr) =>
      arr.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)),
    );
    try {
      await markRead(n.id);
    } catch {
      // swallow — server reconfirm follows.
    }
    void fetchBell();
    window.location.href = n.target_url;
  };

  const markAll = async () => {
    setCount(0);
    setItems((arr) => arr.map((x) => ({ ...x, is_read: true })));
    try {
      await markAllRead();
    } catch {
      // swallow
    }
    void fetchBell();
  };

  return { count, items, loaded, markReadAndNavigate, markAll, refetch: fetchBell };
}
