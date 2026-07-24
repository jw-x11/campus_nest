import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Avatar } from '../components/ui.jsx';
import { SendIcon } from '../components/icons.jsx';
import { conversations, threadMessages } from '../data.js';

function Bubble({ m }) {
  return (
    <div style={{ display: 'flex', justifyContent: m.mine ? 'flex-end' : 'flex-start' }}>
      <div style={{ maxWidth: '74%' }}>
        <div
          style={{
            border: '1.5px solid var(--ink)',
            borderRadius: 14,
            padding: '11px 14px',
            fontSize: 14,
            lineHeight: 1.4,
            background: m.mine ? 'var(--accent)' : '#fff',
            borderBottomRightRadius: m.mine ? 4 : 14,
            borderBottomLeftRadius: m.mine ? 14 : 4,
          }}
        >
          {m.text}
        </div>
        <div
          className="mono"
          style={{ fontSize: 10, color: '#aaa', marginTop: 4, textAlign: m.mine ? 'right' : 'left' }}
        >
          {m.when}
        </div>
      </div>
    </div>
  );
}

export default function Messages() {
  const [activeId, setActiveId] = useState(conversations[0].id);
  const [messages, setMessages] = useState(threadMessages);
  const [draft, setDraft] = useState('');
  const [status, setStatus] = useState('pending'); // pending | confirmed | declined

  const active = conversations.find((c) => c.id === activeId);

  const send = () => {
    const text = draft.trim();
    if (!text) return;
    setMessages((m) => [...m, { mine: true, text, when: 'now' }]);
    setDraft('');
  };

  const statusLabel = {
    pending: '● request pending',
    confirmed: '● booking confirmed',
    declined: '● request declined',
  }[status];

  return (
    <div className="page">
      <div className="wire-card" style={{ borderRadius: 5 }}>
        <div style={{ display: 'flex', height: 640 }}>
          {/* conversation list */}
          <div style={{ flex: 'none', width: 320, borderRight: '2px solid var(--ink)', display: 'flex', flexDirection: 'column' }}>
            <div
              style={{
                padding: '16px 18px',
                borderBottom: '1.5px solid var(--line)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <span className="display" style={{ fontSize: 19 }}>Messages</span>
              <span className="mono" style={{ fontSize: 11, color: 'var(--label)' }}>4 threads</span>
            </div>
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {conversations.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setActiveId(c.id)}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    display: 'flex',
                    gap: 12,
                    padding: '15px 18px',
                    border: 'none',
                    borderBottom: '1.5px solid var(--line)',
                    borderLeft: c.id === activeId ? '3px solid var(--accent)' : '3px solid transparent',
                    background: c.id === activeId ? 'var(--tint)' : '#fff',
                    cursor: 'pointer',
                  }}
                >
                  <Avatar size={42}>{c.initials}</Avatar>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
                      <span style={{ fontSize: 14.5, fontWeight: 600 }}>{c.name}</span>
                      <span className="mono" style={{ fontSize: 10.5, color: 'var(--label)' }}>{c.when}</span>
                    </div>
                    <div
                      className="mono"
                      style={{ fontSize: 10.5, color: 'var(--label)', marginTop: 3, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
                    >
                      {c.space}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginTop: 5 }}>
                      <span style={{ flex: 1, fontSize: 12.5, color: 'var(--muted-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {c.snippet}
                      </span>
                      {c.unread > 0 && (
                        <span
                          className="mono"
                          style={{
                            flex: 'none',
                            minWidth: 18,
                            height: 18,
                            padding: '0 5px',
                            borderRadius: 999,
                            background: 'var(--ink)',
                            color: '#fff',
                            fontSize: 10,
                            display: 'grid',
                            placeItems: 'center',
                          }}
                        >
                          {c.unread}
                        </span>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* thread */}
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
            {/* header */}
            <div style={{ padding: '13px 20px', borderBottom: '2px solid var(--ink)', display: 'flex', alignItems: 'center', gap: 12 }}>
              <Avatar size={40}>{active.initials}</Avatar>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 15.5, fontWeight: 600 }}>{active.name}</div>
                <div className="mono" style={{ fontSize: 11, color: 'var(--label)' }}>★ {active.rating}</div>
              </div>
              <Link to="/profile/aisha-l" className="chip btn-sm">View profile</Link>
            </div>

            {/* booking context */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 13, padding: '12px 20px', borderBottom: '1.5px solid var(--line)', background: 'var(--tint-2)', flexWrap: 'wrap' }}>
              <div className="hatch" style={{ flex: 'none', width: 46, height: 46, border: '1.5px solid var(--ink)', borderRadius: 9 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14 }}>{active.space}</div>
                <div className="mono" style={{ fontSize: 11, color: 'var(--label)', marginTop: 3 }}>
                  $45/mo · Jun 1 – Aug 20 · <span style={{ color: status === 'confirmed' ? '#3b7a3b' : 'var(--rust)' }}>{statusLabel}</span>
                </div>
              </div>
              {status === 'pending' ? (
                <>
                  <button className="btn btn-primary btn-sm" onClick={() => setStatus('confirmed')}>Accept</button>
                  <button className="btn btn-sm" onClick={() => setStatus('declined')}>Decline</button>
                </>
              ) : (
                <button className="btn btn-sm" onClick={() => setStatus('pending')}>Reset</button>
              )}
            </div>

            {/* messages */}
            <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 13, background: 'var(--tint-3)' }}>
              <div className="mono" style={{ textAlign: 'center', fontSize: 10.5, color: '#aaa' }}>TODAY</div>
              {messages.map((m, i) => (
                <Bubble key={i} m={m} />
              ))}
            </div>

            {/* composer */}
            <div style={{ borderTop: '2px solid var(--ink)', padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 11 }}>
              <input
                className="field"
                placeholder="Type a message…"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && send()}
                style={{ flex: 1, borderRadius: 12 }}
              />
              <button
                onClick={send}
                aria-label="Send"
                style={{
                  width: 46,
                  height: 46,
                  border: '2px solid var(--ink)',
                  borderRadius: 12,
                  background: 'var(--accent)',
                  display: 'grid',
                  placeItems: 'center',
                  cursor: 'pointer',
                  flex: 'none',
                }}
              >
                <SendIcon size={18} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
