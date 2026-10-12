import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Avatar } from '../components/ui.jsx';
import { SendIcon } from '../components/icons.jsx';

// Pilot preview: the backend has no messaging endpoints yet
// (see backend/main.py TODO: SocketIO live message), so threads
// below are static and composing stays on this device.
const THREADS = [
  { id: 'aisha', initials: 'AL', name: 'Aisha L.', space: 'Walk-in closet, North Side', snippet: 'Sounds good — I can do the 1st.', when: '2m', unread: 2 },
  { id: 'tom', initials: 'TM', name: 'Tom M.', space: 'Dry garage bay', snippet: 'Is the space climate controlled?', when: '1h', unread: 0 },
  { id: 'priya', initials: 'PS', name: 'Priya S.', space: 'Lockable spare room', snippet: 'Thanks! See you Saturday.', when: '3h', unread: 0 },
];

const STARTER = [
  { mine: false, text: 'Hi! Is the space still available June through August?', when: '9:02 AM' },
  { mine: true, text: 'Hey! Yes it is — lockable door, self-serve access. When would you want to drop off?', when: '9:05 AM' },
  { mine: false, text: 'Sounds good — I can do the 1st.', when: '9:11 AM' },
];

export default function Messages() {
  const [activeId, setActiveId] = useState(THREADS[0].id);
  const [messages, setMessages] = useState(STARTER);
  const [draft, setDraft] = useState('');
  const active = THREADS.find((t) => t.id === activeId);

  const send = () => {
    const text = draft.trim();
    if (!text) return;
    setMessages((m) => [...m, { mine: true, text, when: 'now' }]);
    setDraft('');
  };

  return (
    <div className="page">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Messages</p>
          <h1 className="display mt-1 text-3xl">Inbox</h1>
        </div>
        <span className="badge badge-accent">Pilot preview — stays on this device</span>
      </div>

      <div className="card grid overflow-hidden lg:grid-cols-[300px_1fr]">
        <div className="border-b border-stone-100 lg:border-b-0 lg:border-r">
          {THREADS.map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveId(t.id)}
              className={`flex w-full items-center gap-3 border-b border-stone-100 px-4 py-3.5 text-left transition last:border-0 ${
                t.id === activeId ? 'bg-stone-50' : 'hover:bg-stone-50/60'
              }`}
            >
              <Avatar size={40}>{t.initials}</Avatar>
              <span className="min-w-0 flex-1">
                <span className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-semibold">{t.name}</span>
                  <span className="font-mono text-[10.5px] text-stone-400">{t.when}</span>
                </span>
                <span className="mt-0.5 block truncate font-mono text-[11px] text-stone-400">{t.space}</span>
                <span className="mt-0.5 flex items-center gap-2 truncate text-[12.5px] text-stone-500">
                  <span className="truncate">{t.snippet}</span>
                  {t.unread > 0 && (
                    <span className="grid h-[18px] min-w-[18px] flex-none place-items-center rounded-full bg-[#2b2b2b] px-1 font-mono text-[10px] text-white">
                      {t.unread}
                    </span>
                  )}
                </span>
              </span>
            </button>
          ))}
        </div>

        <div className="flex min-h-[480px] flex-col">
          <div className="flex items-center gap-3 border-b border-stone-100 px-5 py-3.5">
            <Avatar size={38}>{active.initials}</Avatar>
            <div className="flex-1">
              <p className="text-[15px] font-semibold">{active.name}</p>
              <p className="font-mono text-[11px] text-stone-400">{active.space}</p>
            </div>
            <Link to="/bookings" className="btn btn-sm">Bookings</Link>
          </div>

          <div className="flex flex-1 flex-col gap-3 overflow-y-auto bg-stone-50/60 p-5">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.mine ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[75%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                  m.mine ? 'rounded-br-md bg-[#ffd22e]' : 'rounded-bl-md bg-white shadow-sm'
                }`}>
                  {m.text}
                </div>
              </div>
            ))}
          </div>

          <div className="flex items-center gap-2 border-t border-stone-100 p-4">
            <input
              className="input"
              placeholder="Type a message…"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && send()}
            />
            <button
              onClick={send}
              aria-label="Send"
              className="grid h-[46px] w-[46px] flex-none place-items-center rounded-xl bg-[#ffd22e] transition hover:brightness-95"
            >
              <SendIcon size={17} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
