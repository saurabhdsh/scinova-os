import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login } from '../api/client';
import { saveCurrentUser } from '../lib/auth';

const inputClass =
  'w-full rounded-lg border border-[#e8e8ed] bg-white px-3 py-2.5 text-[14px] text-[#1d1d1f] outline-none transition focus:border-[#0071e3] focus:ring-2 focus:ring-[rgba(0,113,227,0.10)]';

function Molecule({ className }) {
  return (
    <svg viewBox="0 0 220 160" className={className} fill="none" aria-hidden="true">
      <g strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round">
        <g stroke="#8ecae6">
          <path d="M70 38 L96 53 L96 83 L70 98 L44 83 L44 53 Z" />
          <path d="M70 50 L88 61 L88 75 L70 86 L52 75 L52 61 Z" />
          <path d="M44 68 L28 78" />
        </g>
        <g stroke="#c4b5e8">
          <path d="M96 68 L122 83 L122 113 L96 128 L70 113 L70 83" />
          <path d="M96 92 L114 103 L114 117 L96 128" />
        </g>
        <g stroke="#9ed9c8">
          <path d="M122 98 L146 84 L170 98 L170 126 L146 140 L122 126" />
          <path d="M146 96 L162 106 L162 118 L146 128 L130 118 L130 106 Z" />
          <path d="M170 112 L188 102" />
        </g>
        <path d="M28 78 L18 92" stroke="#f0c4b0" />
      </g>
      <g>
        <circle cx="28" cy="78" r="3.2" fill="#8ecae6" />
        <circle cx="18" cy="92" r="2.4" fill="#f0c4b0" />
        <circle cx="188" cy="102" r="3.2" fill="#9ed9c8" />
        <circle cx="70" cy="38" r="2.2" fill="#c4b5e8" />
        <circle cx="146" cy="84" r="2.2" fill="#a9d4f2" />
      </g>
    </svg>
  );
}

function MoleculeField() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <Molecule className="mol-drift absolute -left-6 top-8 w-64 opacity-70" />
      <Molecule className="mol-drift-alt absolute -right-10 bottom-6 w-72 opacity-60" />
      <div className="absolute left-1/2 top-1/2 w-80 -translate-x-1/2 -translate-y-1/2">
        <Molecule className="mol-drift w-full opacity-40" />
      </div>
      <Molecule className="mol-drift-alt absolute right-10 top-16 w-40 opacity-55" />
    </div>
  );
}

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
    <div className="grid min-h-screen bg-[#f5f5f7] lg:grid-cols-[38%_62%]">
      <section className="relative hidden overflow-hidden bg-[#1d1d1f] lg:flex lg:flex-col lg:justify-between">
        <img
          src="/TCS-logo-white.svg"
          alt="Tata Consultancy Services"
          className="w-auto object-contain"
          style={{ height: 140, maxWidth: 300, alignSelf: 'flex-start', paddingLeft: 24 }}
          draggable={false}
        />

        <div className="px-12 pb-12">
          <h1 className="text-5xl font-semibold leading-tight text-white" style={{ letterSpacing: '-0.025em' }}>
            SciNova
          </h1>
          <p className="mt-4 max-w-sm text-[15px] leading-relaxed text-white/50">
            TCS AI Native Drug Discovery Accelerator
          </p>
        </div>
      </section>

      <section className="relative flex items-center justify-center overflow-hidden bg-white p-8">
        <MoleculeField />
        <form className="relative z-10 w-full max-w-[340px] space-y-5" onSubmit={handleSubmit}>
          <div className="mb-2 lg:hidden">
            <img
              src="/TCS-logo-white.svg"
              alt="Tata Consultancy Services"
              className="h-16 w-auto rounded-lg bg-[#1d1d1f] object-contain object-left"
              draggable={false}
            />
          </div>
          <div className="mb-8">
            <h2 className="text-[28px] font-semibold text-[#1d1d1f]" style={{ letterSpacing: '-0.022em' }}>
              Sign in
            </h2>
            <p className="mt-1 text-[14px] text-[#86868b]">Use your SciNova username and password.</p>
          </div>
          <label className="block space-y-1.5">
            <span className="text-[12px] font-medium text-[#86868b]">Username</span>
            <input
              className={inputClass}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </label>
          <label className="block space-y-1.5">
            <span className="text-[12px] font-medium text-[#86868b]">Password</span>
            <input
              className={inputClass}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          {error && <p className="text-[13px] text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-[#0071e3] px-4 py-3 text-[13px] font-medium text-white transition-all hover:bg-[#0077ed] active:bg-[#0058ae] disabled:opacity-40"
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </section>
    </div>
  );
}
