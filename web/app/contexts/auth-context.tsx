'use client';

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { User, Session } from '@supabase/supabase-js';
import { getSupabase } from '../lib/supabase';

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

  const fetchUserProfile = async (supabaseUser: User, accessToken: string) => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(
        `${apiUrl}/api/v1/auth/me`,
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
    const supabase = getSupabase();
    const { data: { session: currentSession } } = await supabase.auth.getSession();
    if (currentSession?.user) {
      await fetchUserProfile(currentSession.user, currentSession.access_token);
    }
  };

  useEffect(() => {
    const supabase = getSupabase();

    supabase.auth.getSession().then(({ data: { session: initialSession } }) => {
      setSession(initialSession);
      if (initialSession?.user) {
        fetchUserProfile(initialSession.user, initialSession.access_token);
      }
      setLoading(false);
    });

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
    const supabase = getSupabase();
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
