'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { getSupabase } from '@/lib/supabase';

export default function SignupPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const router = useRouter();
  const supabase = getSupabase();

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
      const { error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: {
            full_name: fullName,
          },
          emailRedirectTo: `${window.location.origin}/callback`,
        },
      });

      if (error) {
        setError(error.message);
        return;
      }

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
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}/callback`,
        },
      });

      if (error) {
        setError(error.message);
      }
    } catch (err) {
      setError('Une erreur est survenue');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center px-4">
        <div className="w-full max-w-[400px]">
          <div className="bg-bg-3 border border-border rounded-xl p-8 text-center">
            <div className="w-16 h-16 bg-green-dark rounded-full flex items-center justify-center mx-auto mb-4">
              <span className="text-green text-3xl">✓</span>
            </div>
            <h1 className="text-2xl font-bold text-text-1 mb-2">
              Vérifiez votre email
            </h1>
            <p className="text-text-2 mb-6">
              Nous avons envoyé un lien de confirmation à{' '}
              <span className="text-text-1 font-medium">{email}</span>
            </p>
            <p className="text-text-3 text-sm">
              Cliquez sur le lien dans l&apos;email pour activer votre compte.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-4">
      <div className="w-full max-w-[400px]">
        {/* Logo */}
        <Link href="/" className="flex items-center justify-center gap-2 mb-8">
          <div className="w-8 h-8 bg-gradient-to-br from-green to-[#00cc6a] rounded-lg flex items-center justify-center font-mono font-bold text-sm text-bg">
            K
          </div>
          <span className="font-extrabold text-xl text-text-1 tracking-tight">kickstat</span>
        </Link>

        {/* Card */}
        <div className="bg-bg-3 border border-border rounded-xl p-8">
          <h1 className="text-2xl font-bold text-text-1 text-center mb-2">
            Créer un compte
          </h1>
          <p className="text-text-2 text-center text-sm mb-6">
            Commencez à trouver des opportunités
          </p>

          {/* Google button */}
          <button
            onClick={handleGoogleSignup}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg border border-border bg-bg hover:bg-bg-4 text-text-1 font-medium transition-colors disabled:opacity-50"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path
                fill="currentColor"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="currentColor"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="currentColor"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="currentColor"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            Continuer avec Google
          </button>

          <div className="flex items-center gap-4 my-6">
            <div className="flex-1 h-px bg-border" />
            <span className="text-text-3 text-xs">ou</span>
            <div className="flex-1 h-px bg-border" />
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="bg-red-dark border border-red/20 rounded-lg px-4 py-3 text-red text-sm">
                {error}
              </div>
            )}

            <div>
              <label htmlFor="fullName" className="block text-text-2 text-sm mb-1.5">
                Nom complet
              </label>
              <input
                id="fullName"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full px-4 py-3 rounded-lg bg-bg border border-border text-text-1 placeholder:text-text-3 focus:border-green focus:outline-none transition-colors"
                placeholder="Jean Dupont"
              />
            </div>

            <div>
              <label htmlFor="email" className="block text-text-2 text-sm mb-1.5">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 rounded-lg bg-bg border border-border text-text-1 placeholder:text-text-3 focus:border-green focus:outline-none transition-colors"
                placeholder="vous@exemple.com"
                required
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-text-2 text-sm mb-1.5">
                Mot de passe
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 rounded-lg bg-bg border border-border text-text-1 placeholder:text-text-3 focus:border-green focus:outline-none transition-colors"
                placeholder="Au moins 6 caractères"
                required
                minLength={6}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-lg bg-green text-bg font-semibold hover:shadow-[0_0_20px_rgba(0,232,123,0.2)] transition-all disabled:opacity-50"
            >
              {loading ? 'Création...' : 'Créer mon compte'}
            </button>
          </form>

          <p className="text-center text-text-3 text-sm mt-6">
            Déjà un compte ?{' '}
            <Link href="/login" className="text-green hover:underline">
              Se connecter
            </Link>
          </p>
        </div>

        <p className="text-center text-text-3 text-xs mt-4">
          En créant un compte, vous acceptez nos{' '}
          <Link href="/terms" className="underline hover:text-text-2">
            Conditions d&apos;utilisation
          </Link>
        </p>
      </div>
    </div>
  );
}
