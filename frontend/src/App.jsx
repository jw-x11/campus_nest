import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import Nav from './components/Nav.jsx';
import Controls from './components/Controls.jsx';
import Landing from './pages/Landing.jsx';
import Search from './pages/Search.jsx';
import ListSpace from './pages/ListSpace.jsx';
import SpaceDetail from './pages/SpaceDetail.jsx';
import Messages from './pages/Messages.jsx';
import Booking from './pages/Booking.jsx';
import MapView from './pages/MapView.jsx';
import Profile from './pages/Profile.jsx';
import Saved from './pages/Saved.jsx';
import Login from './pages/Login.jsx';
import { useApp } from './context/AppContext.jsx';
import { PageStatus } from './components/ui.jsx';

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

function RequireAuth({ children }) {
  const { user, authReady } = useApp();
  const location = useLocation();
  if (!authReady) {
    return (
      <div className="page">
        <div className="wire-card" style={{ borderRadius: 5 }}>
          <PageStatus>Loading…</PageStatus>
        </div>
      </div>
    );
  }
  if (!user) {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }
  return children;
}

export default function App() {
  return (
    <>
      <ScrollToTop />
      <Nav />
      <main>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/search" element={<Search />} />
          <Route path="/map" element={<MapView />} />
          <Route
            path="/list"
            element={
              <RequireAuth>
                <ListSpace />
              </RequireAuth>
            }
          />
          <Route path="/space/:id" element={<SpaceDetail />} />
          <Route
            path="/book/:id"
            element={
              <RequireAuth>
                <Booking />
              </RequireAuth>
            }
          />
          <Route path="/messages" element={<Messages />} />
          <Route
            path="/profile/:id"
            element={
              <RequireAuth>
                <Profile />
              </RequireAuth>
            }
          />
          <Route
            path="/saved"
            element={
              <RequireAuth>
                <Saved />
              </RequireAuth>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <Controls />
    </>
  );
}
