import Link from 'next/link';
import { TrendingUp, Target, BarChart3, Globe, Layers, ArrowRight, ChevronRight, Play } from 'lucide-react';
import NavBar from './components/NavBar';

function SectionBg({ src }: { src: string }) {
  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt="" className="absolute inset-0 w-full h-full object-cover opacity-30" />
      <div className="absolute inset-0 bg-gradient-to-b from-[#09090b] via-[#09090b]/30 to-[#09090b]" />
    </div>
  );
}

export default function Home() {
  return (
    <div className="min-h-screen bg-[#09090b] text-white">
      <NavBar />

      {/* ── Hero ── */}
      <section className="relative pt-28 pb-20 px-6 overflow-hidden">
        <SectionBg src="/images/stadium.jpg" />

        <div className="relative max-w-2xl mx-auto text-center">
          <h1 className="text-4xl md:text-[3.5rem] font-bold tracking-tight leading-[1.1] mb-6">
            Les bookmakers se trompent.
            <br />
            <span className="text-violet-400">On le prouve.</span>
          </h1>

          <p className="text-lg text-zinc-400 max-w-lg mx-auto mb-10 leading-relaxed">
            Kickstat calcule la <strong className="text-white">vraie probabilité</strong> de
            chaque match et détecte les cotes où le bookmaker sous-estime une
            équipe. Cet écart, c&apos;est votre avantage.
          </p>

          <div className="flex flex-col sm:flex-row gap-3 justify-center mb-16">
            <Link
              href="/signup"
              className="inline-flex items-center justify-center gap-2 px-7 py-3 rounded-lg bg-violet-600 text-white font-semibold text-sm hover:bg-violet-500 transition"
            >
              Créer un compte gratuit
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link
              href="/dashboard"
              className="inline-flex items-center justify-center gap-2 px-7 py-3 rounded-lg border border-white/10 text-zinc-400 font-medium text-sm hover:border-white/20 hover:text-white transition backdrop-blur-sm"
            >
              Voir les paris du jour
            </Link>
          </div>

          {/* Stats bar */}
          <div className="inline-flex items-center gap-8 sm:gap-10 px-8 py-5 rounded-2xl bg-black/40 border border-white/10 backdrop-blur-md">
            <div>
              <div className="text-2xl font-bold text-violet-400">+1.7%</div>
              <div className="text-xs text-zinc-500 mt-0.5">ROI validé</div>
            </div>
            <div className="w-px h-8 bg-white/10" />
            <div>
              <div className="text-2xl font-bold">53.4%</div>
              <div className="text-xs text-zinc-500 mt-0.5">Précision</div>
            </div>
            <div className="w-px h-8 bg-white/10" />
            <div>
              <div className="text-2xl font-bold">1 660</div>
              <div className="text-xs text-zinc-500 mt-0.5">Matchs testés</div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Video / Demo ── */}
      <section className="relative py-20 px-6 overflow-hidden">
        <SectionBg src="/images/crowd.jpg" />

        <div className="relative max-w-4xl mx-auto">
          <p className="text-xs font-medium text-violet-400 text-center uppercase tracking-wider mb-3">
            Démo
          </p>
          <h2 className="text-2xl font-bold text-center mb-4">
            Voyez Kickstat en action
          </h2>
          <p className="text-sm text-zinc-400 text-center max-w-md mx-auto mb-10">
            Chaque matin, les paris du jour avec leur edge et la mise optimale. En 30 secondes.
          </p>

          <div className="relative aspect-video rounded-2xl overflow-hidden border border-white/10 bg-black/40 backdrop-blur-sm">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/images/match.jpg"
              alt="Aperçu vidéo Kickstat"
              className="absolute inset-0 w-full h-full object-cover opacity-40"
            />
            <div className="absolute inset-0 flex items-center justify-center">
              <button className="group flex items-center justify-center w-20 h-20 rounded-full bg-violet-600/80 hover:bg-violet-500 transition-all shadow-2xl shadow-violet-600/40 backdrop-blur-sm">
                <Play className="w-8 h-8 text-white ml-1 group-hover:scale-110 transition-transform" fill="white" />
              </button>
            </div>
            <div className="absolute bottom-4 left-4">
              <span className="text-xs text-zinc-300 bg-black/60 backdrop-blur-sm px-3 py-1.5 rounded-full">
                Démo du dashboard — 0:32
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* ── Edge — exemple concret ── */}
      <section className="relative py-20 px-6 overflow-hidden">
        <SectionBg src="/images/field.jpg" />

        <div className="relative max-w-3xl mx-auto">
          <p className="text-xs font-medium text-violet-400 text-center uppercase tracking-wider mb-3">
            Comprendre l&apos;edge
          </p>
          <h2 className="text-2xl font-bold text-center mb-4">
            Notre modèle voit ce que le bookmaker ne voit pas.
          </h2>
          <p className="text-sm text-zinc-400 text-center max-w-md mx-auto mb-12">
            Exemple réel sur un match de Premier League.
          </p>

          <div className="rounded-2xl border border-white/10 bg-black/40 backdrop-blur-sm overflow-hidden">
            <div className="grid md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-white/10">
              <div className="p-8 text-center">
                <div className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-white/5 border border-white/10 mb-4">
                  <BarChart3 className="w-5 h-5 text-violet-400" />
                </div>
                <div className="text-xs text-zinc-500 mb-2">Notre modèle dit</div>
                <div className="text-4xl font-bold mb-1">64%</div>
                <div className="text-sm text-zinc-500">de chances de victoire</div>
              </div>
              <div className="p-8 text-center">
                <div className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-white/5 border border-white/10 mb-4">
                  <Target className="w-5 h-5 text-zinc-400" />
                </div>
                <div className="text-xs text-zinc-500 mb-2">Le bookmaker offre</div>
                <div className="text-4xl font-bold mb-1">1.85</div>
                <div className="text-sm text-zinc-500">= 54% implicite</div>
              </div>
              <div className="p-8 text-center bg-violet-500/[0.06]">
                <div className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-violet-500/10 border border-violet-500/20 mb-4">
                  <TrendingUp className="w-5 h-5 text-violet-400" />
                </div>
                <div className="text-xs text-violet-400 mb-2">Votre avantage</div>
                <div className="text-4xl font-bold text-violet-400 mb-1">+10%</div>
                <div className="text-sm text-zinc-500">d&apos;edge détecté</div>
              </div>
            </div>
            <div className="px-8 py-4 border-t border-white/10 bg-black/30">
              <p className="text-sm text-zinc-400 text-center">
                Le bookmaker équilibre ses livres pour faire du profit.
                Quand il sous-estime une équipe, notre IA le détecte — c&apos;est ça, l&apos;edge.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Ce que vous recevez ── */}
      <section className="relative py-20 px-6 overflow-hidden">
        <SectionBg src="/images/scoreboard.jpg" />

        <div className="relative max-w-5xl mx-auto">
          <p className="text-xs font-medium text-violet-400 text-center uppercase tracking-wider mb-3">
            Fonctionnalités
          </p>
          <h2 className="text-2xl font-bold text-center mb-14">
            Ce que vous recevez chaque matin
          </h2>

          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div className="space-y-8">
              {[
                { icon: TrendingUp, title: 'Paris du jour avec edge', desc: 'Les matchs où notre modèle détecte un écart significatif entre la probabilité réelle et la cote. Pas de bruit, que de la valeur.' },
                { icon: Target, title: 'Mise Kelly optimale', desc: 'Combien miser sur chaque pari pour maximiser le profit sans risquer la ruine. Calibré sur les données réelles.' },
                { icon: Globe, title: '7 ligues couvertes', desc: 'Premier League, Liga, Serie A, Ligue 1, Champions League, Europa League, Conference League.' },
                { icon: Layers, title: 'Combinés optimisés', desc: 'Les meilleures sélections du jour combinées automatiquement. Cote multipliée, edge maintenu.' },
              ].map((item) => (
                <div key={item.title} className="flex gap-4">
                  <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center">
                    <item.icon className="w-5 h-5 text-violet-400" />
                  </div>
                  <div>
                    <h3 className="font-semibold mb-1">{item.title}</h3>
                    <p className="text-sm text-zinc-500 leading-relaxed">{item.desc}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Dashboard preview */}
            <div className="relative rounded-2xl overflow-hidden border border-white/10 bg-black/40 backdrop-blur-sm">
              <div className="border-b border-white/10 px-4 py-2.5 flex items-center gap-2">
                <div className="flex gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                  <div className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                  <div className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                </div>
                <div className="flex-1 text-center text-xs text-zinc-500 font-mono">
                  kickstat.app/dashboard
                </div>
              </div>
              <div className="relative aspect-[4/3]">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="/images/match.jpg"
                  alt="Aperçu du dashboard Kickstat"
                  className="absolute inset-0 w-full h-full object-cover opacity-60"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />
                <div className="absolute bottom-4 left-4">
                  <span className="text-xs text-zinc-300 bg-black/60 backdrop-blur-sm px-3 py-1.5 rounded-lg">
                    Remplacer par screenshot du vrai dashboard
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Les chiffres ── */}
      <section className="relative py-20 px-6 overflow-hidden">
        <SectionBg src="/images/crowd.jpg" />

        <div className="relative max-w-3xl mx-auto">
          <p className="text-xs font-medium text-violet-400 text-center uppercase tracking-wider mb-3">
            Backtest transparent
          </p>
          <h2 className="text-2xl font-bold text-center mb-4">La preuve par les chiffres</h2>
          <p className="text-sm text-zinc-400 text-center mb-14">
            Premier League · 2021–2025 · Backtesté hors échantillon sur 4 saisons complètes
          </p>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12">
            {[
              { value: '1 660', label: 'matchs analysés' },
              { value: '+1.7%', label: 'ROI final', accent: true },
              { value: '53.4%', label: 'précision 1X2' },
              { value: '1 079', label: 'paris sélectionnés' },
            ].map((s) => (
              <div key={s.label} className="text-center p-5 rounded-xl bg-black/40 border border-white/10 backdrop-blur-sm">
                <div className={`text-3xl font-bold mb-1 ${s.accent ? 'text-violet-400' : ''}`}>{s.value}</div>
                <div className="text-xs text-zinc-500">{s.label}</div>
              </div>
            ))}
          </div>

          <div className="max-w-lg mx-auto rounded-xl border border-white/10 bg-black/40 backdrop-blur-sm p-6">
            <p className="text-sm text-zinc-400 leading-relaxed mb-3">
              <strong className="text-white">+1.7% ROI = +17€ de profit pour chaque 1 000€ misés.</strong>{' '}
              C&apos;est modeste — et c&apos;est le point. Pas de promesses irréalistes.
              Un edge statistique réel, validé sur des données jamais vues par le modèle.
            </p>
            <p className="text-xs text-zinc-600 leading-relaxed">
              5 modèles ML &middot; 62 variables par match &middot; Calibration isotonique (ECE 0.0078)
            </p>
          </div>
        </div>
      </section>

      {/* ── CTA final ── */}
      <section className="relative py-24 px-6 overflow-hidden">
        <SectionBg src="/images/stadium.jpg" />

        <div className="relative max-w-2xl mx-auto text-center">
          <h2 className="text-2xl md:text-3xl font-bold mb-4">
            Arrêtez de parier à l&apos;aveugle.
          </h2>
          <p className="text-zinc-400 mb-8">
            Les paris du jour sont gratuits. Pas de carte bancaire. Mis à jour chaque matin.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link
              href="/signup"
              className="inline-flex items-center justify-center gap-2 px-7 py-3 rounded-lg bg-violet-600 text-white font-semibold text-sm hover:bg-violet-500 transition"
            >
              Commencer gratuitement
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link
              href="/historique"
              className="inline-flex items-center justify-center gap-1 px-7 py-3 rounded-lg text-zinc-400 font-medium text-sm hover:text-white transition"
            >
              Voir l&apos;historique
              <ChevronRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-zinc-800/50 py-8 px-6">
        <div className="max-w-3xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <span className="text-sm font-semibold">Kickstat</span>
          <div className="flex items-center gap-6 text-xs text-zinc-600">
            <Link href="/dashboard" className="hover:text-white transition">Dashboard</Link>
            <Link href="/historique" className="hover:text-white transition">Historique</Link>
            <span>© 2026</span>
          </div>
          <p className="text-xs text-zinc-700">18+ · Jouez responsablement</p>
        </div>
      </footer>
    </div>
  );
}
