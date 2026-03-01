'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { getSupabase } from '../lib/supabase';
import { useAuth } from '../contexts/auth-context';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  // Redirect if already logged in
  useEffect(() => {
    if (!authLoading && session) {
      router.push('/dashboard');
    }
  }, [authLoading, session, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const supabase = getSupabase();
      const { error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (error) { setError(error.message); return; }
      router.push('/dashboard');
    } catch (err) {
      setError('Une erreur est survenue');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#09090b] flex items-center justify-center px-4">
      <div className="w-full max-w-[400px]">
        <Link href="/" className="flex items-center justify-center gap-2 mb-8">
          <span className="text-xl font-bold tracking-tight text-white">
            Kick<span className="bg-gradient-to-r from-violet-400 to-pink-400 bg-clip-text text-transparent">stat</span>
          </span>
        </Link>

        <div className="bg-white/5 border border-white/10 rounded-xl p-8">
          <h1 className="text-2xl font-bold text-white text-center mb-2">Se connecter</h1>
          <p className="text-gray-400 text-center text-sm mb-6">Accédez à vos prédictions</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3 text-red-400 text-sm">{error}</div>
            )}

            <div>
              <label htmlFor="email" className="block text-gray-400 text-sm mb-1.5">Email</label>
              <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-gray-600 focus:border-violet-500 focus:outline-none"
                placeholder="vous@exemple.com" required />
            </div>

            <div>
              <label htmlFor="password" className="block text-gray-400 text-sm mb-1.5">Mot de passe</label>
              <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-gray-600 focus:border-violet-500 focus:outline-none"
                placeholder="Votre mot de passe" required />
            </div>

            <button type="submit" disabled={loading}
              className="w-full py-3 rounded-lg bg-gradient-to-r from-violet-600 to-violet-500 text-white font-semibold hover:from-violet-500 hover:to-violet-400 transition disabled:opacity-50">
              {loading ? 'Connexion...' : 'Se connecter'}
            </button>
          </form>

          <p className="text-center text-gray-500 text-sm mt-6">
            Pas encore de compte ? <Link href="/signup" className="text-violet-400 hover:underline">Créer un compte</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
