'use client';

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { User, Session } from '@supabase/supabase-js';
import { getSupabase } from '@/lib/supabase';

interface AuthUser {
  id: string;
  email: string;
  fullName?: string;
  subscriptionTier: string;
  subscriptionStatus: string;
  telegramConnected: boolean;
  telegramAlertsEnabled: boolean;
}

interface AuthContextType {
  user: AuthUser | null;
  session: Session | null;
  loading: boolean;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  const supabase = getSupabase();

  const fetchUserProfile = async (supabaseUser: User, accessToken: string) => {
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/me`,
        {
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        }
      );

      if (response.ok) {
        const data = await response.json();
        setUser({
          id: data.id,
          email: data.email,
          fullName: data.full_name,
          subscriptionTier: data.subscription_tier,
          subscriptionStatus: data.subscription_status,
          telegramConnected: data.telegram_connected,
          telegramAlertsEnabled: data.telegram_alerts_enabled,
        });
      } else {
        // Fallback to basic Supabase user info
        setUser({
          id: supabaseUser.id,
          email: supabaseUser.email || '',
          fullName: supabaseUser.user_metadata?.full_name,
          subscriptionTier: 'free',
          subscriptionStatus: 'inactive',
          telegramConnected: false,
          telegramAlertsEnabled: false,
        });
      }
    } catch (error) {
      console.error('Error fetching user profile:', error);
      // Fallback to basic info
      setUser({
        id: supabaseUser.id,
        email: supabaseUser.email || '',
        fullName: supabaseUser.user_metadata?.full_name,
        subscriptionTier: 'free',
        subscriptionStatus: 'inactive',
        telegramConnected: false,
        telegramAlertsEnabled: false,
      });
    }
  };

  const refreshUser = async () => {
    const { data: { session: currentSession } } = await supabase.auth.getSession();
    if (currentSession?.user) {
      await fetchUserProfile(currentSession.user, currentSession.access_token);
    }
  };

  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data: { session: initialSession } }) => {
      setSession(initialSession);
      if (initialSession?.user) {
        fetchUserProfile(initialSession.user, initialSession.access_token);
      }
      setLoading(false);
    });

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, newSession) => {
        setSession(newSession);
        if (newSession?.user) {
          await fetchUserProfile(newSession.user, newSession.access_token);
        } else {
          setUser(null);
        }
        setLoading(false);
      }
    );

    return () => subscription.unsubscribe();
  }, []);

  const signOut = async () => {
    await supabase.auth.signOut();
    setUser(null);
    setSession(null);
  };

  return (
    <AuthContext.Provider value={{ user, session, loading, signOut, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// Higher-order component for protected routes
export function withAuth<P extends object>(
  Component: React.ComponentType<P>
) {
  return function AuthenticatedComponent(props: P) {
    const { user, loading } = useAuth();

    if (loading) {
      return (
        <div className="min-h-screen bg-bg flex items-center justify-center">
          <div className="w-8 h-8 border-2 border-green border-t-transparent rounded-full animate-spin" />
        </div>
      );
    }

    if (!user) {
      // Redirect to login
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
      return null;
    }

    return <Component {...props} />;
  };
}
