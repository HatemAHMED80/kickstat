'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '../contexts/auth-context';

export default function NavBar() {
  const { user, loading, signOut } = useAuth();
  const pathname = usePathname();

  const linkClass = (href: string) =>
    pathname === href
      ? 'text-sm font-medium text-white px-3 py-1.5'
      : 'text-sm text-zinc-500 hover:text-white transition px-3 py-1.5';

  return (
    <nav className="border-b border-zinc-800/50 bg-[#09090b]">
      <div className="max-w-3xl mx-auto px-6 h-14 flex items-center justify-between">
        <Link href="/" className="text-sm font-bold tracking-tight text-white">
          Kickstat
        </Link>
        <div className="flex items-center gap-1">
          <Link href="/historique" className={linkClass('/historique')}>
            Historique
          </Link>
          {loading ? (
            <div className="w-16 h-8" />
          ) : user ? (
            <>
              <Link href="/dashboard" className={linkClass('/dashboard')}>
                Dashboard
              </Link>
              <button
                onClick={() => signOut()}
                className="text-sm text-zinc-500 hover:text-red-400 transition px-3 py-1.5"
              >
                Déconnexion
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="text-sm text-zinc-500 hover:text-white transition px-3 py-1.5">
                Connexion
              </Link>
              <Link
                href="/signup"
                className="text-sm font-medium px-4 py-1.5 rounded-md bg-violet-600 hover:bg-violet-500 text-white transition"
              >
                S&apos;inscrire
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
