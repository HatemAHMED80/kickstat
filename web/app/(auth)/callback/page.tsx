'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { getSupabase } from '../../lib/supabase';

export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    const handleCallback = async () => {
      const supabase = getSupabase();
      const { error } = await supabase.auth.exchangeCodeForSession(window.location.href);
      if (error) {
        console.error('Auth callback error:', error);
        router.push('/login?error=auth_failed');
        return;
      }
      router.push('/dashboard');
    };
    handleCallback();
  }, [router]);

  return (
    <div className="min-h-screen bg-[#09090b] flex items-center justify-center">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-violet-400 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-gray-400">Connexion en cours...</p>
      </div>
    </div>
  );
}
