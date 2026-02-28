'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { getSupabase } from '../../lib/supabase';

export default function SignupPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    if (password.length < 6) {
      setError('Le mot de passe doit contenir au moins 6 caractères');
      setLoading(false);
      return;
    }

    try {
      const supabase = getSupabase();
      const { error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: { full_name: fullName },
          emailRedirectTo: `${window.location.origin}/callback`,
        },
      });

      if (error) { setError(error.message); return; }
      setSuccess(true);
    } catch (err) {
      setError('Une erreur est survenue');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignup = async () => {
    setLoading(true);
    try {
      const supabase = getSupabase();
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: { redirectTo: `${window.location.origin}/callback` },
      });
      if (error) setError(error.message);
    } catch (err) {
      setError('Une erreur est survenue');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-[#09090b] flex items-center justify-center px-4">
        <div className="w-full max-w-[400px] bg-white/5 border border-white/10 rounded-xl p-8 text-center">
          <div className="w-16 h-16 bg-emerald-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <span className="text-emerald-400 text-3xl">✓</span>
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">Vérifiez votre email</h1>
          <p className="text-gray-400 mb-6">
            Nous avons envoyé un lien de confirmation à <span className="text-white font-medium">{email}</span>
          </p>
          <p className="text-gray-500 text-sm">Cliquez sur le lien dans l&apos;email pour activer votre compte.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#09090b] flex items-center justify-center px-4">
      <div className="w-full max-w-[400px]">
        <Link href="/" className="flex items-center justify-center gap-2 mb-8">
          <span className="text-xl font-bold tracking-tight text-white">
            Kick<span className="bg-gradient-to-r from-violet-400 to-pink-400 bg-clip-text text-transparent">stat</span>
          </span>
        </Link>

        <div className="bg-white/5 border border-white/10 rounded-xl p-8">
          <h1 className="text-2xl font-bold text-white text-center mb-2">Créer un compte</h1>
          <p className="text-gray-400 text-center text-sm mb-6">Commencez à trouver des opportunités</p>

          <button onClick={handleGoogleSignup} disabled={loading}
            className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 text-white font-medium transition disabled:opacity-50">
            Continuer avec Google
          </button>

          <div className="flex items-center gap-4 my-6">
            <div className="flex-1 h-px bg-white/10" />
            <span className="text-gray-500 text-xs">ou</span>
            <div className="flex-1 h-px bg-white/10" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3 text-red-400 text-sm">{error}</div>
            )}

            <div>
              <label htmlFor="fullName" className="block text-gray-400 text-sm mb-1.5">Nom complet</label>
              <input id="fullName" type="text" value={fullName} onChange={(e) => setFullName(e.target.value)}
                className="w-full px-4 py-3 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-gray-600 focus:border-violet-500 focus:outline-none"
                placeholder="Jean Dupont" />
            </div>

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
                placeholder="Au moins 6 caractères" required minLength={6} />
            </div>

            <button type="submit" disabled={loading}
              className="w-full py-3 rounded-lg bg-gradient-to-r from-violet-600 to-violet-500 text-white font-semibold hover:from-violet-500 hover:to-violet-400 transition disabled:opacity-50">
              {loading ? 'Création...' : 'Créer mon compte'}
            </button>
          </form>

          <p className="text-center text-gray-500 text-sm mt-6">
            Déjà un compte ? <Link href="/login" className="text-violet-400 hover:underline">Se connecter</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
