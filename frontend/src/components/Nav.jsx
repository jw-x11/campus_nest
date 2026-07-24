import { NavLink, Link } from 'react-router-dom';
import { HouseIcon } from './icons.jsx';
import { useApp } from '../context/AppContext.jsx';

export function Brand({ size = 23, markSize = 30 }) {
  return (
    <Link to="/" className="brand" style={{ fontSize: size }}>
      <span className="brand-mark" style={{ width: markSize, height: markSize }}>
        <HouseIcon size={markSize * 0.5} />
      </span>
      campus nest
    </Link>
  );
}

export default function Nav() {
  const { saved } = useApp();
  return (
    <nav className="nav">
      <Brand />
      <div className="nav-links">
        <NavLink to="/search" className="nav-link">
          Browse
        </NavLink>
        <NavLink to="/saved" className="nav-link">
          ♡ Saved
          <span className="count-badge">{saved.size}</span>
        </NavLink>
        <NavLink to="/messages" className="nav-link">
          Messages
          <span className="count-badge" style={{ background: 'var(--accent)' }}>
            2
          </span>
        </NavLink>
        <NavLink to="/list" className="nav-link">
          List a space
        </NavLink>
        <Link to="/profile/john-doe" aria-label="Your profile">
          <span className="avatar" style={{ width: 34, height: 34, borderWidth: 2 }}>
            JD
          </span>
        </Link>
      </div>
    </nav>
  );
}
