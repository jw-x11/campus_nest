import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Avatar, EmptyState, ErrorState, LoadingState } from '../components/ui.jsx';
import { SendIcon } from '../components/icons.jsx';
import { useApp } from '../context/AppContext.jsx';
import { useMessaging } from '../context/MessagingContext.jsx';
import { useSpaceTitles } from '../spaceTitles.js';
import {
  getConversation,
  initials,
  listConversations,
  listMessages,
  openConversation,
  sendMessage,
} from '../api.js';

const MAX_MESSAGE_LENGTH = 2000;
const TYPING_SEND_EVERY = 3000;
const TYPING_SHOWN_FOR = 4000;

function newClientMsgId() {
  if (crypto.randomUUID) return crypto.randomUUID();
  // randomUUID needs a secure context; plain-http LAN addresses get a v4 id built by hand.
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

function isToday(date) {
  const now = new Date();
  return date.toDateString() === now.toDateString();
}

/** "9:02 AM" today, "Oct 3" earlier. */
function shortWhen(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  if (isToday(date)) return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/** "9:02 AM" today, "Oct 3, 9:02 AM" earlier. */
function messageTime(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  const time = date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  if (isToday(date)) return time;
  return `${date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}, ${time}`;
}

function byPosition(a, b) {
  if (a.createdAt !== b.createdAt) return a.createdAt < b.createdAt ? -1 : 1;
  return a.id < b.id ? -1 : 1;
}

/**
 * Stored messages from the server merged into what is on screen, oldest first, without duplicates.
 * Messages still sending (they have a status) stay at the end until the stored copy with the
 * same clientMsgId arrives, from the send response or the live push, whichever is first.
 */
function mergeMessages(current, incoming) {
  const stored = new Map();
  const pending = [];
  for (const m of current) {
    if (m.status) pending.push(m);
    else stored.set(m.id, m);
  }
  for (const m of incoming) stored.set(m.id, m);
  const settled = new Set([...stored.values()].map((m) => `${m.senderId}:${m.clientMsgId}`));
  return [
    ...[...stored.values()].sort(byPosition),
    ...pending.filter((p) => !settled.has(`${p.senderId}:${p.clientMsgId}`)),
  ];
}

function UserAvatar({ user, size }) {
  if (user?.avatarUrl) {
    return (
      <img
        src={user.avatarUrl}
        alt=""
        style={{ width: size, height: size }}
        className="flex-none rounded-full border border-stone-200 object-cover"
      />
    );
  }
  return <Avatar size={size}>{initials(user?.username)}</Avatar>;
}

function ConversationRow({ conversation, title, unread, active }) {
  const last = conversation.lastMessage;
  return (
    <Link
      to={`/messages/${conversation.id}`}
      className={`flex w-full items-center gap-3 border-b border-stone-100 px-4 py-3.5 text-left transition last:border-0 ${
        active ? 'bg-stone-50' : 'hover:bg-stone-50/60'
      }`}
    >
      <UserAvatar user={conversation.otherUser} size={40} />
      <span className="min-w-0 flex-1">
        <span className="flex items-center justify-between gap-2">
          <span className="truncate text-sm font-semibold">{conversation.otherUser?.username ?? 'Unknown user'}</span>
          <span className="flex-none font-mono text-[10.5px] text-stone-400">
            {shortWhen(conversation.lastMessageAt ?? conversation.createdAt)}
          </span>
        </span>
        <span className="mt-0.5 block truncate font-mono text-[11px] text-stone-400">{title}</span>
        <span className="mt-0.5 flex items-center gap-2 text-[12.5px] text-stone-500">
          <span className={`truncate ${unread > 0 ? 'font-semibold text-stone-800' : ''}`}>
            {last ? last.body : 'No messages yet'}
          </span>
          {unread > 0 && (
            <span className="ml-auto grid h-[18px] min-w-[18px] flex-none place-items-center rounded-full bg-[#2b2b2b] px-1 font-mono text-[10px] text-white">
              {unread}
            </span>
          )}
        </span>
      </span>
    </Link>
  );
}

function Thread({ conversation, title }) {
  const { user } = useApp();
  const { subscribe, markRead, setActiveConversation, sendTyping, status } = useMessaging();
  const me = String(user.id);
  const convId = conversation.id;

  const [messages, setMessages] = useState([]);
  const [hasMore, setHasMore] = useState(false);
  const [state, setState] = useState('loading');
  const [error, setError] = useState('');
  const [loadingEarlier, setLoadingEarlier] = useState(false);
  const [draft, setDraft] = useState('');
  const [otherTyping, setOtherTyping] = useState(false);

  const messagesRef = useRef(messages);
  const scrollRef = useRef(null);
  const stickToBottom = useRef(true);
  const keepScrollFrom = useRef(null);
  const lastTypingSent = useRef(0);
  const typingTimer = useRef(null);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  const load = useCallback(async () => {
    setState('loading');
    try {
      const page = await listMessages(convId);
      setMessages(mergeMessages([], page.messages));
      setHasMore(page.hasMore);
      setState('ready');
      markRead(convId);
    } catch (err) {
      setError(err.message || 'Could not load messages.');
      setState('error');
    }
  }, [convId, markRead]);

  useEffect(() => {
    stickToBottom.current = true;
    load();
  }, [load]);

  useEffect(() => {
    setActiveConversation(convId);
    return () => setActiveConversation(null);
  }, [convId, setActiveConversation]);

  // Messages that arrived while the tab was in the background are read once it is back.
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible') markRead(convId);
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [convId, markRead]);

  // Everything after the newest message we have, for events missed while the socket was down.
  const catchUp = useCallback(async () => {
    const lastStored = [...messagesRef.current].reverse().find((m) => !m.status);
    try {
      const page = lastStored
        ? await listMessages(convId, { after: lastStored.id, limit: 100 })
        : await listMessages(convId);
      setMessages((prev) => mergeMessages(prev, page.messages));
    } catch {
      // the next reconnect or page load tries again
    }
  }, [convId]);

  useEffect(
    () =>
      subscribe((event) => {
        if (event.type === 'reconnected') {
          catchUp();
          return;
        }
        if (event.conversation_id !== convId) return;
        if (event.type === 'message') {
          setMessages((prev) => mergeMessages(prev, [event.message]));
          if (event.message.senderId !== me) {
            setOtherTyping(false);
            if (document.visibilityState === 'visible') markRead(convId);
          }
        } else if (event.type === 'typing' && event.user_id !== me) {
          setOtherTyping(true);
          clearTimeout(typingTimer.current);
          typingTimer.current = setTimeout(() => setOtherTyping(false), TYPING_SHOWN_FOR);
        }
      }),
    [subscribe, convId, me, markRead, catchUp],
  );

  useEffect(() => () => clearTimeout(typingTimer.current), []);

  // Follow new messages when the reader is at the bottom; keep their place when older ones load above.
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    if (keepScrollFrom.current != null) {
      el.scrollTop = el.scrollHeight - keepScrollFrom.current;
      keepScrollFrom.current = null;
    } else if (stickToBottom.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, otherTyping, state]);

  const onScroll = () => {
    const el = scrollRef.current;
    stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };

  const loadEarlier = async () => {
    const first = messages.find((m) => !m.status);
    if (!first) return;
    setLoadingEarlier(true);
    try {
      const page = await listMessages(convId, { before: first.id });
      keepScrollFrom.current = scrollRef.current.scrollHeight - scrollRef.current.scrollTop;
      setMessages((prev) => mergeMessages(prev, page.messages));
      setHasMore(page.hasMore);
    } catch {
      // the button stays, so the reader can try again
    } finally {
      setLoadingEarlier(false);
    }
  };

  const deliver = async (body, clientMsgId) => {
    try {
      const stored = await sendMessage(convId, body, clientMsgId);
      setMessages((prev) => mergeMessages(prev, [stored]));
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.status && m.clientMsgId === clientMsgId
            ? { ...m, status: 'failed', error: err.message || 'Not sent' }
            : m,
        ),
      );
    }
  };

  const send = () => {
    const body = draft.trim();
    if (!body) return;
    const clientMsgId = newClientMsgId();
    stickToBottom.current = true;
    setMessages((prev) => [
      ...prev,
      {
        id: `pending-${clientMsgId}`,
        clientMsgId,
        senderId: me,
        body,
        createdAt: new Date().toISOString(),
        status: 'sending',
      },
    ]);
    setDraft('');
    lastTypingSent.current = 0;
    deliver(body, clientMsgId);
  };

  // A retry reuses the clientMsgId, so a send that did reach the server is not stored twice.
  const retry = (pending) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === pending.id ? { ...m, status: 'sending', error: undefined } : m)),
    );
    deliver(pending.body, pending.clientMsgId);
  };

  const onDraftChange = (e) => {
    setDraft(e.target.value);
    const now = Date.now();
    if (e.target.value && now - lastTypingSent.current > TYPING_SEND_EVERY) {
      lastTypingSent.current = now;
      sendTyping(convId);
    }
  };

  const other = conversation.otherUser;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-3 border-b border-stone-100 px-5 py-3.5">
        <Link to="/messages" aria-label="Back to conversations" className="-ml-1 text-xl leading-none text-stone-400 lg:hidden">
          ‹
        </Link>
        <UserAvatar user={other} size={38} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[15px] font-semibold">{other?.username ?? 'Unknown user'}</p>
          <Link to={`/space/${conversation.spaceId}`} className="block truncate font-mono text-[11px] text-stone-400 hover:underline">
            {title}
          </Link>
        </div>
        {status !== 'live' && (
          <span className="hidden font-mono text-[10.5px] text-stone-400 sm:inline">Reconnecting…</span>
        )}
        {conversation.bookingId && (
          <Link to="/bookings" className="btn btn-sm flex-none">Booking</Link>
        )}
      </div>

      <div ref={scrollRef} onScroll={onScroll} className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto bg-stone-50/60 p-5">
        {state === 'loading' && <LoadingState label="Loading messages…" />}
        {state === 'error' && <ErrorState message={error} onRetry={load} />}
        {state === 'ready' && (
          <>
            {hasMore && (
              <button className="btn btn-sm mx-auto" disabled={loadingEarlier} onClick={loadEarlier}>
                {loadingEarlier ? 'Loading…' : 'Load earlier messages'}
              </button>
            )}
            {messages.length === 0 && (
              <p className="m-auto max-w-xs text-center text-sm text-stone-400">
                Say hello and ask about the space. Messages stay between you and {other?.username ?? 'them'}.
              </p>
            )}
            {messages.map((m) => {
              const mine = m.senderId === me;
              return (
                <div key={m.id} className={`flex flex-col ${mine ? 'items-end' : 'items-start'}`}>
                  <div
                    className={`max-w-[75%] whitespace-pre-wrap break-words rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                      mine ? 'rounded-br-md bg-[#ffd22e]' : 'rounded-bl-md bg-white shadow-sm'
                    } ${m.status === 'sending' ? 'opacity-60' : ''}`}
                  >
                    {m.body}
                  </div>
                  <span className="mt-1 px-1 font-mono text-[10.5px] text-stone-400">
                    {m.status === 'sending' && 'Sending…'}
                    {m.status === 'failed' && (
                      <span className="text-red-700">
                        {m.error || 'Not sent'} ·{' '}
                        <button className="underline" onClick={() => retry(m)}>Retry</button>
                      </span>
                    )}
                    {!m.status && messageTime(m.createdAt)}
                  </span>
                </div>
              );
            })}
            {otherTyping && (
              <p className="font-mono text-[11px] text-stone-400">{other?.username ?? 'They'} is typing…</p>
            )}
          </>
        )}
      </div>

      <form
        className="flex items-center gap-2 border-t border-stone-100 p-4"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <input
          className="input"
          placeholder="Type a message…"
          value={draft}
          maxLength={MAX_MESSAGE_LENGTH}
          onChange={onDraftChange}
          aria-label="Message"
        />
        <button
          type="submit"
          aria-label="Send"
          disabled={!draft.trim()}
          className="grid h-[46px] w-[46px] flex-none place-items-center rounded-xl bg-[#ffd22e] transition hover:brightness-95 disabled:opacity-50"
        >
          <SendIcon size={17} />
        </button>
      </form>
    </div>
  );
}

export default function Messages() {
  const { conversationId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { subscribe, unread } = useMessaging();

  const [conversations, setConversations] = useState([]);
  const [listState, setListState] = useState('loading');
  const [openError, setOpenError] = useState('');
  const conversationsRef = useRef(conversations);

  useEffect(() => {
    conversationsRef.current = conversations;
  }, [conversations]);

  const loadList = useCallback(async () => {
    try {
      const data = await listConversations();
      setConversations(data.conversations);
      setListState('ready');
    } catch {
      setListState('error');
    }
  }, []);

  useEffect(() => {
    loadList();
  }, [loadList]);

  const addConversation = (conv) =>
    setConversations((prev) => (prev.some((c) => c.id === conv.id) ? prev : [conv, ...prev]));

  // /messages?space=ID[&booking=ID] opens that thread, creating it the first time, then moves to its URL.
  const spaceParam = searchParams.get('space');
  const bookingParam = searchParams.get('booking');
  useEffect(() => {
    if (!spaceParam) return undefined;
    let cancelled = false;
    openConversation({ spaceId: spaceParam, bookingId: bookingParam })
      .then((conv) => {
        if (cancelled) return;
        setOpenError('');
        addConversation(conv);
        navigate(`/messages/${conv.id}`, { replace: true });
      })
      .catch((err) => {
        if (!cancelled) setOpenError(err.message || 'Could not open this conversation.');
      });
    return () => {
      cancelled = true;
    };
  }, [spaceParam, bookingParam, navigate]);

  // A direct link to a thread that is not on the first page of the inbox.
  const active = conversations.find((c) => c.id === conversationId) ?? null;
  useEffect(() => {
    if (!conversationId || listState !== 'ready') return undefined;
    if (conversationsRef.current.some((c) => c.id === conversationId)) return undefined;
    let cancelled = false;
    getConversation(conversationId)
      .then((conv) => {
        if (!cancelled) addConversation(conv);
      })
      .catch((err) => {
        if (!cancelled) setOpenError(err.message || 'Conversation not found.');
      });
    return () => {
      cancelled = true;
    };
  }, [conversationId, listState]);

  // New messages move their thread to the top; one from a thread we have not loaded refreshes the list.
  useEffect(
    () =>
      subscribe((event) => {
        if (event.type === 'reconnected') {
          loadList();
          return;
        }
        if (event.type !== 'message') return;
        if (!conversationsRef.current.some((c) => c.id === event.conversation_id)) {
          loadList();
          return;
        }
        setConversations((prev) => {
          const current = prev.find((c) => c.id === event.conversation_id);
          if (!current) return prev;
          const updated = { ...current, lastMessage: event.message, lastMessageAt: event.message.createdAt };
          return [updated, ...prev.filter((c) => c.id !== event.conversation_id)];
        });
      }),
    [subscribe, loadList],
  );

  const titles = useSpaceTitles(conversations.map((c) => c.spaceId));
  const titleOf = (conv) => titles[conv.spaceId] || `Space #${conv.spaceId}`;
  const opening = Boolean(spaceParam) && !openError;

  return (
    <div className="page">
      <div className="mb-4">
        <p className="eyebrow">Messages</p>
        <h1 className="display mt-1 text-3xl">Inbox</h1>
      </div>

      {openError && (
        <p className="mb-3 rounded-xl bg-red-50 p-3 text-[13px] text-red-700">{openError}</p>
      )}

      {listState === 'loading' && <div className="card"><LoadingState label="Loading conversations…" /></div>}
      {listState === 'error' && (
        <div className="card"><ErrorState message="Could not load your messages." onRetry={loadList} /></div>
      )}
      {listState === 'ready' && conversations.length === 0 && !opening && (
        <div className="card">
          <EmptyState
            title="No messages yet"
            body="Ask a host about their space from its listing page, and the conversation shows up here."
            action={<Link to="/search" className="btn btn-primary">Browse spaces</Link>}
          />
        </div>
      )}

      {listState === 'ready' && (conversations.length > 0 || opening) && (
        <div className="card grid h-[min(680px,calc(100vh-210px))] min-h-[460px] overflow-hidden lg:grid-cols-[300px_1fr]">
          <div className={`min-h-0 overflow-y-auto border-stone-100 lg:block lg:border-r ${active ? 'hidden' : ''}`}>
            {conversations.map((c) => (
              <ConversationRow
                key={c.id}
                conversation={c}
                title={titleOf(c)}
                unread={c.id === conversationId ? 0 : unread[c.id] || 0}
                active={c.id === conversationId}
              />
            ))}
          </div>

          <div className={`min-h-0 flex-col lg:flex ${active ? 'flex' : 'hidden'}`}>
            {active ? (
              <Thread key={active.id} conversation={active} title={titleOf(active)} />
            ) : opening || conversationId ? (
              <LoadingState label="Opening conversation…" />
            ) : (
              <p className="m-auto text-sm text-stone-400">Pick a conversation to read it.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
