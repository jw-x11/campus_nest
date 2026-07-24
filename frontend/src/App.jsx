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

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

export default function App() {
  return (
    <>
      <ScrollToTop />
      <Nav />
      <main>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/search" element={<Search />} />
          <Route path="/map" element={<MapView />} />
          <Route path="/list" element={<ListSpace />} />
          <Route path="/space/:id" element={<SpaceDetail />} />
          <Route path="/book/:id" element={<Booking />} />
          <Route path="/messages" element={<Messages />} />
          <Route path="/profile/:id" element={<Profile />} />
          <Route path="/saved" element={<Saved />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <Controls />
    </>
  );
}
