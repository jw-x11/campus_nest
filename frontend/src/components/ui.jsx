// Small presentational primitives shared across the Campus Nest screens.

// Cross-hatched placeholder image (the wireframe's stand-in for a photo).
export function Hatch({ style, className = '', children }) {
  return (
    <div className={`hatch ${className}`} style={style}>
      {children}
    </div>
  );
}

// Stack of grey body-copy bars — low-fi placeholder text.
export function BodyLines({ widths = ['100%', '88%', '62%'], height = 9, gap = 7 }) {
  return (
    <div className="bar-stack" style={{ gap }}>
      {widths.map((w, i) => (
        <div key={i} className="bar" style={{ width: w, height }} />
      ))}
    </div>
  );
}

export function Avatar({ children, size = 34, style }) {
  return (
    <span
      className="avatar"
      style={{ width: size, height: size, fontSize: size * 0.34, ...style }}
    >
      {children}
    </span>
  );
}

export function Field({ label, fieldKey, note, children, value, ...rest }) {
  return (
    <div>
      {(label || fieldKey || note) && (
        <div
          style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: 8,
            marginBottom: 8,
            flexWrap: 'wrap',
          }}
        >
          {label && <span className="label">{label}</span>}
          {fieldKey && <span className="field-key">{fieldKey}</span>}
          {note && (
            <span className="field-key" style={{ color: 'var(--rust)' }}>
              {note}
            </span>
          )}
        </div>
      )}
      {children || (
        <div className="field" {...rest}>
          {value}
        </div>
      )}
    </div>
  );
}

// Annotation note (the rust ✎ callouts) — toggled by the "show notes" switch.
export function Annotation({ children, style }) {
  return (
    <div className="annot" style={style}>
      ✎ {children}
    </div>
  );
}
