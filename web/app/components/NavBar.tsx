'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

// TODO: réactiver useAuth dans la NavBar avant la prod
export default function NavBar() {
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
          <Link href="/dashboard" className={linkClass('/dashboard')}>
            Dashboard
          </Link>
          <Link href="/historique" className={linkClass('/historique')}>
            Historique
          </Link>
        </div>
      </div>
    </nav>
  );
}
