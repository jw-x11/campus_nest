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
        if (!username.trim()) throw new Error('Choose a username.');
        if (password.length < 8) throw new Error('Password must be at least 8 characters.');
        await register(email.trim(), password, username.trim());
      } else {
        await login(email.trim(), password);
      }
      navigate(next, { replace: true });
    } catch (err) {
      setError(err.message || 'Could not sign in.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page !max-w-[480px]">
      <div className="card p-7 sm:p-9">
        <p className="eyebrow">Account</p>
        <h1 className="display mt-1 text-3xl">{mode === 'login' ? 'Welcome back' : 'Create an account'}</h1>
        <p className="mt-2 text-sm text-stone-500">
          Needed to save spaces, list a unit, or send a booking request.
        </p>

        <div className="mt-5 grid grid-cols-2 gap-1 rounded-xl bg-stone-100 p-1">
          {['login', 'register'].map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => { setMode(m); setError(''); }}
              className={`rounded-lg py-2 text-sm font-semibold capitalize transition ${
                mode === m ? 'bg-white shadow-sm' : 'text-stone-400 hover:text-stone-600'
              }`}
            >
              {m === 'login' ? 'Log in' : 'Sign up'}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="mt-5 flex flex-col gap-4">
          {mode === 'register' && (
            <Field label="Username">
              <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Jane Doe" autoComplete="username" required />
            </Field>
          )}
          <Field label="Email">
            <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@university.edu" autoComplete="email" required />
          </Field>
          <Field label="Password" hint={mode === 'register' ? 'min 8 characters' : ''}>
            <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required />
          </Field>

          {error && <p className="text-sm text-red-700">{error}</p>}

          <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
            {busy ? 'Working…' : mode === 'login' ? 'Log in' : 'Create account'}
          </button>
        </form>

        <p className="mt-5 text-center text-sm text-stone-400">
          <Link to="/" className="hover:text-stone-700">← Back home</Link>
        </p>
      </div>
    </div>
  );
}
