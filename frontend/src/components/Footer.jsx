export default function Footer() {
  return (
    <div
      style={{
        borderTop: '2px solid var(--ink)',
        background: 'var(--tint)',
        padding: '24px 56px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 18,
        flexWrap: 'wrap',
      }}
    >
      <span className="display" style={{ fontSize: 20 }}>
        campus nest
      </span>
      <div style={{ display: 'flex', gap: 22, fontSize: 13.5, color: 'var(--muted)' }}>
        <span>How it works</span>
        <span>Safety</span>
        <span>Prohibited items</span>
        <span>Help</span>
      </div>
    </div>
  );
}
