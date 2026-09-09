import { useState } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { Field } from '../components/ui.jsx';
import { useApp } from '../context/AppContext.jsx';
import { safeNext } from '../api.js';

export default function Login() {
  const { login, register, user } = useApp();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get('next'));
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={next} replace />;

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      if (mode === 'register') {
        if (!username.trim()) throw new Error('Choose a username');
        await register(email.trim(), password, username.trim());
      } else {
        await login(email.trim(), password);
      }
      navigate(next, { replace: true });
    } catch (err) {
      setError(err.message || 'Could not sign in');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page" style={{ maxWidth: 520 }}>
      <div className="wire-card" style={{ borderRadius: 5, padding: '34px 40px 40px' }}>
        <div className="label" style={{ letterSpacing: '.06em' }}>ACCOUNT</div>
        <h1 className="display" style={{ fontSize: 32, marginTop: 6 }}>
          {mode === 'login' ? 'Log in' : 'Create an account'}
        </h1>
        <div style={{ fontSize: 14.5, color: 'var(--muted)', marginTop: 6 }}>
          Needed to save spaces, list a unit, or send a booking request.
        </div>

        <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 18, marginTop: 28 }}>
          {mode === 'register' && (
            <Field label="USERNAME">
              <input
                className="field"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
              />
            </Field>
          )}
          <Field label="EMAIL">
            <input
              className="field"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </Field>
          <Field label="PASSWORD">
            <input
              className="field"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              required
            />
          </Field>

          {error && (
            <div style={{ fontSize: 14, color: 'var(--rust)' }}>{error}</div>
          )}

          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? 'Working…' : mode === 'login' ? 'Log in' : 'Create account'}
          </button>
        </form>

        <div style={{ marginTop: 22, fontSize: 14, color: 'var(--muted-2)' }}>
          {mode === 'login' ? (
            <>
              New here?{' '}
              <button
                type="button"
                onClick={() => { setMode('register'); setError(''); }}
                style={{ background: 'none', border: 'none', color: 'var(--rust)', cursor: 'pointer', padding: 0 }}
              >
                Create an account
              </button>
            </>
          ) : (
            <>
              Already have an account?{' '}
              <button
                type="button"
                onClick={() => { setMode('login'); setError(''); }}
                style={{ background: 'none', border: 'none', color: 'var(--rust)', cursor: 'pointer', padding: 0 }}
              >
                Log in
              </button>
            </>
          )}
          <div style={{ marginTop: 12 }}>
            <Link to="/" style={{ color: 'var(--muted)' }}>← Back home</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
