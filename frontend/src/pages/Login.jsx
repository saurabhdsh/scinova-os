import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { GitBranch, Loader2 } from 'lucide-react';
import { login } from '../api/client';
import { saveCurrentUser } from '../lib/auth';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const r = await login({ username, password });
      localStorage.setItem('scinova_token', r.data.access_token);
      saveCurrentUser({
        user_id: r.data.user_id,
        username: r.data.username,
        role: r.data.role,
        full_name: r.data.full_name,
      });
      navigate('/');
    } catch {
      setError('Invalid credentials');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-full flex items-center justify-center p-6 grid-bg">
      <div className="glass-panel-hero w-full max-w-md p-8">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cx-accent/20 to-cx-accent2/20 border border-cx-accent/30 flex items-center justify-center">
            <GitBranch className="text-cx-accent" size={24} />
          </div>
          <div>
            <h1 className="font-display text-xl font-semibold">SciNova OS</h1>
            <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">SciFabric AgentOS</p>
            <p className="text-2xs text-cx-fgMuted mt-1">Tata Consultancy Services</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-2xs uppercase tracking-wider text-cx-fgDim">Username</label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
              className="mt-1 w-full px-4 py-2.5 rounded-xl border border-cx-border bg-white/60 text-sm focus:outline-none focus:border-cx-accent/40"
            />
          </div>
          <div>
            <label className="text-2xs uppercase tracking-wider text-cx-fgDim">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
              className="mt-1 w-full px-4 py-2.5 rounded-xl border border-cx-border bg-white/60 text-sm focus:outline-none focus:border-cx-accent/40"
            />
          </div>
          {error && <p className="text-sm text-cx-danger">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 rounded-xl text-sm font-medium border border-cx-accent/30 bg-cx-accent/5 text-cx-accent hover:bg-cx-accent/10 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : null}
            Sign In
          </button>
        </form>

        <p className="mt-6 text-xs text-cx-fgDim text-center">
          Contact your administrator for login credentials.
        </p>
      </div>
    </div>
  );
}
