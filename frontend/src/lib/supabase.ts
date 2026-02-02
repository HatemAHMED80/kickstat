import { createBrowserClient } from '@supabase/ssr';

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}

// Singleton client for client-side use
let supabaseClient: ReturnType<typeof createClient> | null = null;

export function getSupabase() {
  if (!supabaseClient) {
    supabaseClient = createClient();
  }
  return supabaseClient;
}
