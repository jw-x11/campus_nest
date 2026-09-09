import { NavLink, Link } from 'react-router-dom';
import { HouseIcon } from './icons.jsx';
import { useApp } from '../context/AppContext.jsx';
import { initials } from '../api.js';

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
  const { saved, user } = useApp();
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
        </NavLink>
        <NavLink to="/list" className="nav-link">
          List a space
        </NavLink>
        {user ? (
          <Link to="/profile/me" aria-label="Your profile">
            <span className="avatar" style={{ width: 34, height: 34, borderWidth: 2 }}>
              {initials(user.username)}
            </span>
          </Link>
        ) : (
          <Link to="/login" className="btn btn-sm btn-primary">
            Log in
          </Link>
        )}
      </div>
    </nav>
  );
}
