import { NavLink, Link } from 'react-router-dom';
import { HouseIcon } from './icons.jsx';
import { useApp } from '../context/AppContext.jsx';
import { initials } from '../api.js';

export function Brand() {
  return (
    <Link to="/" className="brand">
      <span className="brand-mark">
        <HouseIcon size={15} />
      </span>
      campus nest
    </Link>
  );
}

const linkCls = ({ isActive }) => `nav-link${isActive ? ' active' : ''}`;

export default function Nav() {
  const { saved, user } = useApp();
  return (
    <nav className="nav">
      <div className="nav-inner">
        <Brand />
        <div className="nav-links">
          <NavLink to="/search" className={linkCls}>
            Browse
          </NavLink>
          <NavLink to="/map" className={linkCls}>
            <span className="nav-link-label">Map</span>
            <span className="sm:hidden">Map</span>
          </NavLink>
          <NavLink to="/saved" className={linkCls}>
            Saved{saved.size > 0 && (
              <span className="ml-1.5 rounded-full bg-[#ffd22e] px-1.5 py-0.5 font-mono text-[10.5px] text-[#2b2b2b]">
                {saved.size}
              </span>
            )}
          </NavLink>
          <NavLink to="/bookings" className={linkCls}>
            Bookings
          </NavLink>
          {user ? (
            <Link
              to="/profile"
              aria-label="Your profile"
              className="ml-1 grid h-8 w-8 place-items-center rounded-full bg-[#2b2b2b] font-mono text-[11px] text-white"
            >
              {initials(user.username)}
            </Link>
          ) : (
            <Link to="/login" className="btn btn-sm btn-dark ml-2">
              Log in
            </Link>
          )}
          <Link to="/list" className="btn btn-sm btn-primary ml-2 hidden sm:inline-flex">
            List a space
          </Link>
        </div>
      </div>
    </nav>
  );
}
