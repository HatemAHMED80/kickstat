'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { getSupabase } from '@/lib/supabase';

export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    const handleCallback = async () => {
      const supabase = getSupabase();
      // Exchange the code for a session
      const { error } = await supabase.auth.exchangeCodeForSession(
        window.location.href
      );

      if (error) {
        console.error('Auth callback error:', error);
        router.push('/login?error=auth_failed');
        return;
      }

      // Redirect to dashboard on success
      router.push('/dashboard');
    };

    handleCallback();
  }, [router]);

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-green border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-text-2">Connexion en cours...</p>
      </div>
    </div>
  );
}
