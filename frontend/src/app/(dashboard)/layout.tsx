'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/auth-context';

function DashboardContent({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, signOut } = useAuth();

  const handleSignOut = async () => {
    await signOut();
    router.push('/login');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-green border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) {
    router.push('/login');
    return null;
  }

  return (
    <div className="min-h-screen bg-bg">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-[rgba(10,10,15,0.9)] backdrop-blur-xl border-b border-border px-6">
        <div className="max-w-[1100px] mx-auto flex items-center justify-between h-[54px]">
          <Link href="/dashboard" className="flex items-center gap-2 no-underline">
            <div className="w-[26px] h-[26px] bg-gradient-to-br from-green to-[#00cc6a] rounded-md flex items-center justify-center font-mono font-bold text-[11px] text-bg">
              K
            </div>
            <span className="font-extrabold text-[17px] text-text-1 tracking-tight">kickstat</span>
            <span className="font-mono text-[8px] text-green tracking-[2px] uppercase bg-green-dark px-1.5 py-0.5 rounded">
              beta
            </span>
          </Link>

          <nav className="flex items-center gap-3.5">
            <NavLink href="/dashboard" active={pathname === '/dashboard'}>
              Opportunités
            </NavLink>
            <NavLink href="/dashboard/matches" active={pathname?.startsWith('/dashboard/matches')}>
              Matchs
            </NavLink>
            <NavLink href="/dashboard/settings" active={pathname === '/dashboard/settings'}>
              Paramètres
            </NavLink>
            {user.subscriptionTier === 'free' ? (
              <Link
                href="/dashboard/subscription"
                className="font-mono text-[10px] px-3 py-1.5 rounded bg-green text-bg font-semibold hover:shadow-[0_0_14px_rgba(0,232,123,0.2)] transition-all"
              >
                Premium
              </Link>
            ) : (
              <span className="font-mono text-[10px] px-3 py-1.5 rounded bg-green-dark text-green font-semibold">
                {user.subscriptionTier.toUpperCase()}
              </span>
            )}
            <button
              onClick={handleSignOut}
              className="text-[11px] text-text-3 hover:text-text-1 transition-colors ml-2"
            >
              Sortir
            </button>
          </nav>
        </div>
      </header>

      {/* Ticker bar */}
      <div className="border-b border-border bg-bg-2 px-6">
        <div className="max-w-[1100px] mx-auto flex items-center gap-[22px] py-[9px] overflow-x-auto">
          <div className="flex items-center gap-[5px]">
            <span className="flex items-center gap-1 font-mono text-[9px] text-green tracking-wider">
              <span className="w-[5px] h-[5px] rounded-full bg-green animate-pulse" />
              LIVE
            </span>
          </div>
          <Separator />
          <Stat label="Réussite" value="68.4%" highlight />
          <Separator />
          <Stat label="Prédictions" value="247/361" />
          <Separator />
          <Stat label="ROI" value="+11.3%" highlight />
          <Separator />
          <Stat label="J21" value="1 fév 2026" />
        </div>
      </div>

      {/* Main content */}
      <main className="max-w-[1100px] mx-auto px-6 py-6 relative z-10">
        {children}
      </main>

      {/* Footer */}
      <footer className="max-w-[1100px] mx-auto mt-9 px-6 py-6 border-t border-border flex flex-col md:flex-row justify-between items-center gap-2">
        <span className="font-mono text-[8.5px] text-text-3">
          © 2026 Kickstat · Modèle ELO/ML · v2.4
        </span>
        <span className="font-mono text-[7.5px] text-text-3 max-w-[380px] text-center md:text-right leading-relaxed opacity-60">
          Analyse statistique uniquement. Ne constitue pas un conseil en investissement ni une incitation au jeu.
        </span>
      </footer>
    </div>
  );
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardContent>{children}</DashboardContent>;
}

function NavLink({
  href,
  active,
  children,
}: {
  href: string;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={`text-[11.5px] font-medium transition-colors ${
        active ? 'text-green' : 'text-text-2 hover:text-text-1'
      }`}
    >
      {children}
    </Link>
  );
}

function Separator() {
  return <div className="w-px h-[15px] bg-border flex-shrink-0" />;
}

function Stat({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex items-center gap-[5px] whitespace-nowrap">
      <span className="font-mono text-[9px] text-text-3 uppercase tracking-wider">{label}</span>
      <span className={`font-mono text-[11px] font-semibold ${highlight ? 'text-green' : 'text-text-1'}`}>
        {value}
      </span>
    </div>
  );
}
