import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { getUnread, mapMessage, markConversationRead, messageSocketUrl } from '../api.js';
import { useApp } from './AppContext.jsx';

const MessagingContext = createContext(null);

// The server closes with this when the session behind the socket was logged out or expired.
const CLOSE_UNAUTHORIZED = 4401;
const MAX_RETRY_DELAY = 30000;

/**
 * One live socket per tab for the signed-in user. Holds the unread counts and passes every
 * server event to subscribers. Pages send over REST; the socket only receives, plus typing.
 *
 * Events: { type: 'message', conversation_id, message } (message already mapped), 'read',
 * 'typing', and a local { type: 'reconnected' } after a dropped socket comes back, when pages
 * should catch up from history because events sent while it was down are lost.
 */
export function MessagingProvider({ children }) {
  const { user } = useApp();
  const userId = user ? String(user.id) : null;
  const [status, setStatus] = useState('offline'); // 'connecting' | 'live' | 'offline'
  const [unread, setUnread] = useState({});
  const listeners = useRef(new Set());
  const socketRef = useRef(null);
  // The thread on screen; its new messages are read straight away, so they never count as unread.
  const activeConversation = useRef(null);

  const emit = useCallback((event) => {
    for (const listener of listeners.current) listener(event);
  }, []);

  const refreshUnread = useCallback(async () => {
    try {
      const data = await getUnread();
      setUnread(data.conversations);
    } catch {
      // keep the last counts; the next reconnect tries again
    }
  }, []);

  useEffect(() => {
    if (!userId) return undefined;

    let stopped = false;
    let retryTimer = null;
    let attempt = 0;

    const scheduleRetry = () => {
      if (stopped) return;
      setStatus('offline');
      const delay = Math.min(1000 * 2 ** attempt, MAX_RETRY_DELAY);
      attempt += 1;
      retryTimer = setTimeout(connect, delay);
    };

    async function connect() {
      setStatus('connecting');
      let url;
      try {
        url = await messageSocketUrl();
      } catch {
        scheduleRetry();
        return;
      }
      if (stopped) return;

      const ws = new WebSocket(url);
      socketRef.current = ws;

      ws.onopen = () => {
        const reconnected = attempt > 0;
        attempt = 0;
        setStatus('live');
        if (reconnected) {
          refreshUnread();
          emit({ type: 'reconnected' });
        }
      };

      ws.onmessage = (e) => {
        let event;
        try {
          event = JSON.parse(e.data);
        } catch {
          return;
        }
        if (event.type === 'ping') {
          ws.send(JSON.stringify({ type: 'pong' }));
          return;
        }
        if (event.type === 'message') {
          event = { ...event, message: mapMessage(event.message) };
          const onScreen =
            activeConversation.current === event.conversation_id && document.visibilityState === 'visible';
          if (event.message.senderId !== userId && !onScreen) {
            setUnread((prev) => ({
              ...prev,
              [event.conversation_id]: (prev[event.conversation_id] || 0) + 1,
            }));
          }
        }
        emit(event);
      };

      ws.onclose = (e) => {
        if (socketRef.current === ws) socketRef.current = null;
        if (stopped) return;
        setStatus('offline');
        // A logged-out session will not come back by reconnecting.
        if (e.code === CLOSE_UNAUTHORIZED) return;
        scheduleRetry();
      };
    }

    refreshUnread();
    connect();

    return () => {
      stopped = true;
      clearTimeout(retryTimer);
      socketRef.current?.close();
      socketRef.current = null;
      // Signed out or switched user: the next user's counts are fetched fresh.
      setUnread({});
      setStatus('offline');
    };
  }, [userId, emit, refreshUnread]);

  const subscribe = useCallback((listener) => {
    listeners.current.add(listener);
    return () => listeners.current.delete(listener);
  }, []);

  const setActiveConversation = useCallback((conversationId) => {
    activeConversation.current = conversationId;
  }, []);

  const markRead = useCallback(async (conversationId) => {
    setUnread((prev) => {
      if (!prev[conversationId]) return prev;
      const next = { ...prev };
      delete next[conversationId];
      return next;
    });
    try {
      await markConversationRead(conversationId);
    } catch {
      // the count comes back on the next refresh; nothing else depends on it
    }
  }, []);

  const sendTyping = useCallback((conversationId) => {
    const ws = socketRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'typing', conversation_id: conversationId }));
    }
  }, []);

  const value = useMemo(
    () => ({
      status,
      unread,
      unreadTotal: Object.values(unread).reduce((sum, n) => sum + n, 0),
      subscribe,
      setActiveConversation,
      markRead,
      sendTyping,
      refreshUnread,
    }),
    [status, unread, subscribe, setActiveConversation, markRead, sendTyping, refreshUnread],
  );

  return <MessagingContext.Provider value={value}>{children}</MessagingContext.Provider>;
}

export function useMessaging() {
  const ctx = useContext(MessagingContext);
  if (!ctx) throw new Error('useMessaging must be used within MessagingProvider');
  return ctx;
}
