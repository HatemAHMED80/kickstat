import Link from 'next/link';

export default function Home() {
  return (
    <div className="min-h-screen bg-[#09090b] text-white overflow-x-hidden">

      {/* Gradient background */}
      <div className="fixed inset-0 pointer-events-none bg-[radial-gradient(ellipse_80%_50%_at_20%_-10%,rgba(124,58,237,0.10),transparent),radial-gradient(ellipse_60%_40%_at_80%_60%,rgba(219,39,119,0.07),transparent)]" />

      {/* Navigation */}
      <nav className="relative z-50 border-b border-white/5 bg-[#09090b]">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <span className="text-xl font-bold tracking-tight">
            Kick<span className="bg-gradient-to-r from-violet-400 to-pink-400 bg-clip-text text-transparent">stat</span>
          </span>
          <div className="flex items-center gap-2">
            <Link href="/historique" className="text-sm text-gray-500 hover:text-white transition px-3 py-2">
              Historique
            </Link>
            <Link href="/login" className="text-sm text-gray-500 hover:text-white transition px-3 py-2">
              Connexion
            </Link>
            <Link
              href="/dashboard"
              className="text-sm font-semibold px-4 py-2 rounded-lg bg-gradient-to-r from-violet-600 to-violet-500 hover:from-violet-500 hover:to-violet-400 text-white transition shadow-lg shadow-violet-500/25"
            >
              Dashboard →
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative pt-28 pb-16 px-6">
        <div className="max-w-4xl mx-auto text-center">

          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-violet-500/30 bg-violet-500/10 text-violet-300 text-xs font-mono uppercase tracking-widest mb-10">
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
            Paris du jour disponibles · Backtesté sur 1 660 matchs
          </div>

          <h1 className="text-5xl md:text-7xl font-black tracking-tight leading-[1.08] mb-6">
            Les bookmakers
            <br />
            <span className="bg-gradient-to-r from-violet-400 via-fuchsia-400 to-pink-400 bg-clip-text text-transparent">
              se trompent.
            </span>
            <br />
            <span className="text-white">On le prouve.</span>
          </h1>

          <p className="text-xl text-gray-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            Kickstat calcule la <strong className="text-white">vraie probabilité</strong> de chaque match
            et détecte les matchs où les bookmakers sous-estiment une équipe —
            c'est ça, <span className="text-violet-300 font-semibold">l'edge</span>.
          </p>

          <div className="flex flex-col sm:flex-row gap-3 justify-center mb-16">
            <Link
              href="/dashboard"
              className="px-8 py-4 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white font-bold text-base hover:from-violet-500 hover:to-fuchsia-500 transition shadow-xl shadow-violet-500/30"
            >
              Voir les paris du jour →
            </Link>
            <Link
              href="/login"
              className="px-8 py-4 rounded-xl border border-white/10 text-gray-400 font-medium text-base hover:border-violet-500/30 hover:text-white transition"
            >
              Créer un compte gratuit
            </Link>
          </div>

          {/* Stats row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { value: '+1.7%', label: 'ROI validé', sub: '1 660 matchs · PL 2021–25', color: 'from-violet-400 to-fuchsia-400' },
              { value: '53.4%', label: 'Précision', sub: 'vs 33% aléatoire', color: 'from-fuchsia-400 to-pink-400' },
              { value: '62', label: 'Features IA', sub: 'XGBoost calibré', color: 'from-violet-400 to-fuchsia-400' },
              { value: '8', label: 'Ligues', sub: 'Top 5 + UCL · UEL · UECL', color: 'from-fuchsia-400 to-pink-400' },
            ].map((s) => (
              <div key={s.label} className="p-5 rounded-2xl bg-white/3 border border-white/8 hover:border-violet-500/30 transition text-center group">
                <div className={`text-3xl font-black bg-gradient-to-r ${s.color} bg-clip-text text-transparent mb-1`}>
                  {s.value}
                </div>
                <div className="text-sm font-semibold text-white mb-0.5">{s.label}</div>
                <div className="text-xs text-gray-600">{s.sub}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Dashboard Preview */}
      <section className="relative py-16 px-6 overflow-hidden">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-8">
            <p className="text-xs font-mono uppercase tracking-widest text-gray-600 mb-2">Aperçu du dashboard</p>
            <h2 className="text-2xl font-bold text-white">Ce que tu vois chaque matin</h2>
          </div>

          {/* Browser chrome */}
          <div className="rounded-2xl border border-white/10 overflow-hidden shadow-2xl shadow-violet-500/10">
            {/* Browser bar */}
            <div className="bg-[#141418] border-b border-white/8 px-4 py-3 flex items-center gap-3">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-red-500/60" />
                <div className="w-3 h-3 rounded-full bg-yellow-500/60" />
                <div className="w-3 h-3 rounded-full bg-green-500/60" />
              </div>
              <div className="flex-1 mx-4 px-4 py-1.5 bg-white/5 rounded-lg text-xs text-gray-600 font-mono text-center">
                kickstat.app/dashboard
              </div>
            </div>

            {/* Dashboard content */}
            <div className="bg-[#09090b] p-4 space-y-3">

              {/* Filters bar mock */}
              <div className="flex gap-2 flex-wrap mb-4">
                <div className="px-3 py-1.5 rounded-full bg-violet-500/20 border border-violet-400/60 text-violet-300 text-xs font-bold">Tous</div>
                <div className="px-3 py-1.5 rounded-full border border-white/8 text-gray-600 text-xs">Premier League</div>
                <div className="px-3 py-1.5 rounded-full border border-white/8 text-gray-600 text-xs">🏆 Ultra</div>
                <div className="px-3 py-1.5 rounded-full border border-white/8 text-gray-600 text-xs">✅ Safe</div>
                <div className="px-3 py-1.5 rounded-full border border-fuchsia-500/40 bg-fuchsia-500/10 text-fuchsia-400 text-xs font-bold">🎰 Combinés</div>
                <div className="ml-auto text-xs text-gray-600 font-mono flex items-center gap-2">
                  <span className="text-violet-400 font-bold">12</span> paris
                  <span className="w-2 h-2 rounded-full bg-violet-400 animate-pulse inline-block" />
                </div>
              </div>

              {/* Card 1 — HOT bet */}
              <div className="rounded-xl border border-violet-500/40 bg-white/3 overflow-hidden">
                <div className="border-b border-white/5 px-5 py-4 flex items-center justify-between">
                  <span className="text-xs font-mono text-gray-500 uppercase">Premier League</span>
                  <span className="text-xs font-mono text-violet-400">Sam. 1 Mar · 15h00</span>
                </div>
                <div className="px-5 py-4 flex items-center justify-between gap-4">
                  <div className="text-right flex-1">
                    <div className="text-lg font-bold text-white">Arsenal</div>
                    <div className="flex items-center justify-end gap-1.5 mt-1.5">
                      {['win','win','win','draw','win'].map((r,i) => (
                        <div key={i} className={`w-2.5 h-2.5 rounded-full ring-1 ring-black/30 ${r==='win'?'bg-emerald-400':r==='draw'?'bg-yellow-400':'bg-red-500'}`} />
                      ))}
                    </div>
                  </div>
                  <div className="flex flex-col items-center gap-1">
                    <div className="text-xl font-black bg-gradient-to-r from-violet-400 to-fuchsia-400 bg-clip-text text-transparent">VS</div>
                    <div className="px-2 py-0.5 rounded-full bg-fuchsia-500/20 border border-fuchsia-500/50 text-fuchsia-400 text-xs font-bold animate-pulse">🔥 HOT</div>
                  </div>
                  <div className="text-left flex-1">
                    <div className="text-lg font-bold text-white">Brentford</div>
                    <div className="flex items-center justify-start gap-1.5 mt-1.5">
                      {['loss','draw','win','loss','draw'].map((r,i) => (
                        <div key={i} className={`w-2.5 h-2.5 rounded-full ring-1 ring-black/30 ${r==='win'?'bg-emerald-400':r==='draw'?'bg-yellow-400':'bg-red-500'}`} />
                      ))}
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-2 divide-x divide-white/5 border-t border-white/5">
                  <div className="p-4">
                    <div className="text-xs font-mono text-gray-500 uppercase mb-3">Prédiction du modèle</div>
                    <div className="space-y-2">
                      {[['Arsenal', '68%', true], ['Nul', '18%', false], ['Brentford', '14%', false]].map(([l, p, top]) => (
                        <div key={String(l)}>
                          <div className="flex justify-between text-xs mb-1">
                            <span className={String(top) === 'true' ? 'text-white font-medium' : 'text-gray-600'}>{l}</span>
                            <span className={String(top) === 'true' ? 'text-violet-400 font-bold' : 'text-gray-700'}>{p}</span>
                          </div>
                          <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                            <div className={`h-full rounded-full ${String(top) === 'true' ? 'bg-gradient-to-r from-violet-500 to-fuchsia-500' : 'bg-white/10'}`}
                              style={{ width: p as string }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="p-4">
                    <div className="text-xs font-mono text-gray-500 uppercase mb-3">Paris recommandé</div>
                    <div className="rounded-lg border border-violet-500/30 bg-violet-500/5 p-3">
                      <div className="flex items-baseline gap-2 mb-2 flex-wrap">
                        <span className="text-sm font-bold text-white">Arsenal</span>
                        <span className="text-sm font-bold text-yellow-400 font-mono">(1.62)</span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-center">
                        <div>
                          <div className="text-base font-bold text-emerald-400 font-mono">+14.2%</div>
                          <div className="text-xs text-gray-600">Edge</div>
                        </div>
                        <div>
                          <div className="text-base font-bold text-violet-400 font-mono">68%</div>
                          <div className="text-xs text-gray-600">Prob.</div>
                        </div>
                      </div>
                      <div className="mt-2 pt-2 border-t border-violet-500/20 text-xs text-gray-500 font-mono text-center">
                        Mise Kelly : <span className="text-violet-400 font-bold">3.2%</span> de ta bankroll
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Card 2 — SAFE bet */}
              <div className="rounded-xl border border-white/8 bg-white/3 overflow-hidden">
                <div className="border-b border-white/5 px-5 py-4 flex items-center justify-between">
                  <span className="text-xs font-mono text-gray-500 uppercase">Ligue 1</span>
                  <span className="text-xs font-mono text-violet-400">Sam. 1 Mar · 17h00</span>
                </div>
                <div className="px-5 py-3 flex items-center justify-between gap-4">
                  <div className="text-right flex-1">
                    <div className="text-base font-bold text-white">PSG</div>
                    <div className="flex items-center justify-end gap-1.5 mt-1.5">
                      {['win','win','win','win','win'].map((r,i) => (
                        <div key={i} className={`w-2.5 h-2.5 rounded-full ring-1 ring-black/30 ${r==='win'?'bg-emerald-400':r==='draw'?'bg-yellow-400':'bg-red-500'}`} />
                      ))}
                    </div>
                  </div>
                  <div className="flex flex-col items-center gap-1">
                    <div className="text-lg font-black bg-gradient-to-r from-violet-400 to-fuchsia-400 bg-clip-text text-transparent">VS</div>
                    <div className="px-2 py-0.5 rounded-full bg-emerald-500/20 border border-emerald-500/50 text-emerald-400 text-xs font-bold">✅ SAFE</div>
                  </div>
                  <div className="text-left flex-1">
                    <div className="text-base font-bold text-white">Lens</div>
                    <div className="flex items-center justify-start gap-1.5 mt-1.5">
                      {['loss','draw','loss','win','loss'].map((r,i) => (
                        <div key={i} className={`w-2.5 h-2.5 rounded-full ring-1 ring-black/30 ${r==='win'?'bg-emerald-400':r==='draw'?'bg-yellow-400':'bg-red-500'}`} />
                      ))}
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-2 divide-x divide-white/5 border-t border-white/5">
                  <div className="p-3">
                    <div className="text-xs font-mono text-gray-500 uppercase mb-2">Prédiction</div>
                    <div className="space-y-1.5">
                      {[['PSG', '74%', true], ['Nul', '16%', false], ['Lens', '10%', false]].map(([l, p, top]) => (
                        <div key={String(l)}>
                          <div className="flex justify-between text-xs mb-0.5">
                            <span className={String(top) === 'true' ? 'text-white' : 'text-gray-600'}>{l}</span>
                            <span className={String(top) === 'true' ? 'text-violet-400 font-bold' : 'text-gray-700'}>{p}</span>
                          </div>
                          <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                            <div className={`h-full rounded-full ${String(top) === 'true' ? 'bg-gradient-to-r from-violet-500 to-fuchsia-500' : 'bg-white/10'}`}
                              style={{ width: p as string }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="p-3">
                    <div className="text-xs font-mono text-gray-500 uppercase mb-2">Paris recommandé</div>
                    <div className="rounded-lg border border-violet-500/30 bg-violet-500/5 p-3">
                      <div className="flex items-baseline gap-2 mb-2">
                        <span className="text-sm font-bold text-white">Moins de 2.5 buts</span>
                        <span className="text-sm font-bold text-yellow-400 font-mono">(1.78)</span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-center">
                        <div>
                          <div className="text-sm font-bold text-emerald-400 font-mono">+8.6%</div>
                          <div className="text-xs text-gray-600">Edge</div>
                        </div>
                        <div>
                          <div className="text-sm font-bold text-violet-400 font-mono">61%</div>
                          <div className="text-xs text-gray-600">Prob.</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Card 3 — Combiné */}
              <div className="rounded-xl border border-fuchsia-500/30 bg-white/3 overflow-hidden">
                <div className="border-b border-white/5 px-5 py-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-gray-500 uppercase">Combiné du jour</span>
                    <span className="px-2 py-0.5 rounded-full bg-fuchsia-500/20 border border-fuchsia-500/40 text-fuchsia-400 text-xs font-bold">🎰 2 sélections</span>
                  </div>
                  <span className="text-xs font-mono text-gray-600">Sam. 1 Mar</span>
                </div>
                <div className="p-4 space-y-2">
                  {/* Leg 1 */}
                  <div className="flex items-center gap-3 p-3 rounded-lg bg-white/3 border border-white/5">
                    <div className="w-5 h-5 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center">
                      <div className="w-2 h-2 rounded-full bg-emerald-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-semibold text-white">Arsenal</div>
                      <div className="text-xs text-gray-600 font-mono">Arsenal vs Brentford · 1X2</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-bold text-yellow-400 font-mono">(1.62)</div>
                      <div className="text-xs text-emerald-400 font-mono">+14.2%</div>
                    </div>
                  </div>
                  {/* Leg 2 */}
                  <div className="flex items-center gap-3 p-3 rounded-lg bg-white/3 border border-white/5">
                    <div className="w-5 h-5 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center">
                      <div className="w-2 h-2 rounded-full bg-emerald-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-semibold text-white">Moins de 2.5 buts</div>
                      <div className="text-xs text-gray-600 font-mono">PSG vs Lens · O/U</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-bold text-yellow-400 font-mono">(1.78)</div>
                      <div className="text-xs text-emerald-400 font-mono">+8.6%</div>
                    </div>
                  </div>
                  {/* Combined result */}
                  <div className="flex items-center justify-between pt-1 px-1">
                    <div className="text-xs text-gray-600 font-mono">Cote combinée</div>
                    <div className="flex items-center gap-3">
                      <div className="text-base font-black text-fuchsia-400 font-mono">× 2.88</div>
                      <div className="text-xs text-gray-500 font-mono">Mise Kelly <span className="text-violet-400 font-bold">1.8%</span></div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Blur overlay + CTA */}
              <div className="relative">
                <div className="rounded-xl border border-white/5 bg-white/2 h-16 opacity-30" />
                <div className="absolute inset-0 flex items-center justify-center">
                  <Link href="/dashboard" className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white font-bold text-sm hover:from-violet-500 hover:to-fuchsia-500 transition shadow-lg shadow-violet-500/30">
                    Voir tous les paris du jour →
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* What is edge — key section */}
      <section className="relative py-20 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <div className="inline-block px-3 py-1 rounded-full bg-violet-500/10 border border-violet-500/20 text-violet-400 text-xs font-mono uppercase tracking-widest mb-4">
              C'est quoi l'edge ?
            </div>
            <h2 className="text-3xl md:text-4xl font-black text-white mb-4">
              La différence entre parier<br />et <span className="bg-gradient-to-r from-violet-400 to-fuchsia-400 bg-clip-text text-transparent">investir dans le foot</span>
            </h2>
            <p className="text-gray-500 max-w-xl mx-auto">
              Un bookmaker ne connaît pas la vraie probabilité — il équilibre ses livres pour faire du profit.
              Ce déséquilibre crée des opportunités que notre IA détecte en temps réel.
            </p>
          </div>

          {/* Visual example */}
          <div className="rounded-2xl border border-white/8 bg-white/3 overflow-hidden mb-8">
            <div className="px-6 py-4 border-b border-white/5 flex items-center gap-3">
              <span className="w-2 h-2 rounded-full bg-violet-400 animate-pulse" />
              <span className="text-sm font-mono text-gray-400">Exemple réel — Premier League</span>
            </div>
            <div className="p-6 grid md:grid-cols-3 gap-6">
              <div className="text-center p-5 rounded-xl bg-white/3 border border-white/5">
                <div className="text-xs font-mono uppercase tracking-wider text-gray-600 mb-3">Notre modèle dit</div>
                <div className="text-4xl font-black text-violet-400 mb-1">64%</div>
                <div className="text-sm text-gray-400">de chances de victoire</div>
                <div className="mt-3 text-xs text-gray-600 font-mono">Dixon-Coles + ELO + XGBoost</div>
              </div>
              <div className="text-center p-5 rounded-xl bg-white/3 border border-white/5">
                <div className="text-xs font-mono uppercase tracking-wider text-gray-600 mb-3">Le bookmaker offre</div>
                <div className="text-4xl font-black text-yellow-400 mb-1">1.85</div>
                <div className="text-sm text-gray-400">= 54% implicite</div>
                <div className="mt-3 text-xs text-gray-600 font-mono">Il sous-estime l'équipe de 10%</div>
              </div>
              <div className="text-center p-5 rounded-xl bg-violet-500/10 border border-violet-500/30">
                <div className="text-xs font-mono uppercase tracking-wider text-violet-400 mb-3">Votre avantage</div>
                <div className="text-4xl font-black text-fuchsia-400 mb-1">+10%</div>
                <div className="text-sm text-gray-300 font-semibold">Edge détecté ⚡</div>
                <div className="mt-3 text-xs text-violet-400 font-mono">Mise Kelly recommandée</div>
              </div>
            </div>
            <div className="px-6 py-4 border-t border-white/5 bg-white/2">
              <p className="text-sm text-gray-500 text-center">
                Sur 1 000 paris avec +10% d'edge, la loi des grands nombres garantit un profit —
                <span className="text-violet-300"> c'est la mathématique des casinos, retournée contre les bookmakers.</span>
              </p>
            </div>
          </div>

          {/* 3 concepts */}
          <div className="grid md:grid-cols-3 gap-4">
            {[
              {
                icon: '📊',
                title: 'Probabilité réelle',
                desc: "Notre IA analyse la forme, les stats offensives/défensives, l'ELO, et 62 autres variables pour calculer la vraie chance de chaque résultat.",
                color: 'border-violet-500/20 hover:border-violet-500/40',
              },
              {
                icon: '💹',
                title: 'Edge = écart de valeur',
                desc: "L'edge est la différence entre notre probabilité et celle implicite dans la cote. Un edge de +5% signifie que le bookmaker vous paie trop.",
                color: 'border-fuchsia-500/20 hover:border-fuchsia-500/40',
              },
              {
                icon: '🎯',
                title: 'Mise Kelly optimale',
                desc: "On calcule la mise idéale selon le critère de Kelly : assez pour capitaliser sur l'avantage, jamais assez pour risquer la ruine.",
                color: 'border-pink-500/20 hover:border-pink-500/40',
              },
            ].map((c) => (
              <div key={c.title} className={`p-5 rounded-2xl bg-white/3 border ${c.color} transition`}>
                <div className="text-3xl mb-3">{c.icon}</div>
                <h3 className="text-sm font-bold text-white mb-2">{c.title}</h3>
                <p className="text-xs text-gray-500 leading-relaxed">{c.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pipeline — how it works */}
      <section className="relative py-16 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-10">
            <h2 className="text-2xl font-bold text-white mb-2">5 modèles. 1 signal clair.</h2>
            <p className="text-gray-600 text-sm">Le pipeline ML derrière chaque recommandation</p>
          </div>

          <div className="space-y-3">
            {[
              { name: 'Dixon-Coles', role: 'Modèle de buts', desc: "Calcule la distribution des scores possibles en tenant compte du force offensive et défensive de chaque équipe.", badge: 'Statistiques' },
              { name: 'ELO Rating', role: 'Force relative', desc: "Classement dynamique qui s'adapte match après match — similaire aux échecs, mais pour le foot.", badge: 'Ranking' },
              { name: 'XGBoost', role: '62 features', desc: "Le cœur du système : gradient boosting entraîné sur 4 saisons. Détecte les patterns invisibles à l'œil nu.", badge: 'Machine Learning' },
              { name: 'Calibration isotonique', role: 'Probabilités fiables', desc: "Ajuste les probabilités brutes pour qu'elles correspondent à la réalité (ECE 0.0078 — niveau professionnel).", badge: 'Précision' },
              { name: 'Bandit Thompson', role: 'Sélection adaptative', desc: "Choisit les marchés à recommander selon leur historique de performance — apprend en continu.", badge: 'IA adaptative' },
            ].map((step, i) => (
              <div key={step.name} className="flex gap-4 p-4 rounded-xl bg-white/3 border border-white/5 hover:border-violet-500/20 transition group">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-violet-500/10 border border-violet-500/20 flex items-center justify-center text-sm font-bold text-violet-400 group-hover:bg-violet-500/20 transition">
                  {i + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="font-bold text-white text-sm">{step.name}</span>
                    <span className="text-xs text-gray-600">·</span>
                    <span className="text-xs text-gray-500">{step.role}</span>
                    <span className="ml-auto px-2 py-0.5 rounded-full bg-white/5 border border-white/8 text-gray-600 text-xs font-mono">{step.badge}</span>
                  </div>
                  <p className="text-xs text-gray-600 leading-relaxed">{step.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ROI proof */}
      <section className="relative py-16 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="p-8 rounded-3xl border border-white/8 bg-white/2">
            <div className="text-center mb-8">
              <div className="text-xs font-mono uppercase tracking-widest text-gray-600 mb-2">Backtesting · Premier League · 2021–2025</div>
              <h2 className="text-2xl font-bold text-white">La preuve par les chiffres</h2>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              {[
                { v: '1 660', l: 'matchs testés', c: 'text-white' },
                { v: '+1.7%', l: 'ROI final', c: 'text-violet-400' },
                { v: '53.4%', l: 'accuracy', c: 'text-fuchsia-400' },
                { v: '1 079', l: 'paris sélectionnés', c: 'text-white' },
              ].map(s => (
                <div key={s.l} className="text-center p-4 rounded-xl bg-white/3 border border-white/5">
                  <div className={`text-2xl font-black ${s.c} mb-1`}>{s.v}</div>
                  <div className="text-xs text-gray-600">{s.l}</div>
                </div>
              ))}
            </div>
            <div className="flex items-start gap-3 p-4 rounded-xl bg-violet-500/5 border border-violet-500/10">
              <span className="text-lg flex-shrink-0">💡</span>
              <p className="text-sm text-gray-400 leading-relaxed">
                +1.7% ROI peut sembler modeste — mais c'est <strong className="text-white">+17€ de profit pour chaque 1 000€ misés</strong>, en pariant sur des événements imprévisibles. Les meilleurs traders professionnels visent 3–5%. Notre modèle n'est pas une arnaque : c'est une <span className="text-violet-300">edge statistique réelle, validée hors échantillon</span>.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA final */}
      <section className="relative py-20 px-6">
        <div className="max-w-2xl mx-auto text-center">
          <div className="p-10 rounded-3xl border border-violet-500/20 bg-gradient-to-b from-violet-500/10 to-transparent">
            <div className="text-4xl mb-4">⚡</div>
            <h2 className="text-3xl md:text-4xl font-black mb-3">
              Arrêtez de parier
              <span className="bg-gradient-to-r from-violet-400 to-pink-400 bg-clip-text text-transparent"> à l'aveugle.</span>
            </h2>
            <p className="text-gray-500 text-sm mb-2">Les paris du jour sont gratuits. Pas de carte bancaire.</p>
            <p className="text-gray-600 text-xs mb-8 font-mono">Mis à jour chaque matin avec les dernières cotes.</p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Link
                href="/dashboard"
                className="inline-block px-10 py-4 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white font-bold hover:from-violet-500 hover:to-fuchsia-500 transition shadow-2xl shadow-violet-500/40"
              >
                Voir les paris du jour →
              </Link>
              <Link
                href="/historique"
                className="inline-block px-10 py-4 rounded-xl border border-violet-500/30 text-violet-400 font-medium hover:bg-violet-500/10 hover:text-white transition"
              >
                Historique des résultats
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative border-t border-white/5 py-8 px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <span className="text-sm font-bold">
            Kick<span className="bg-gradient-to-r from-violet-400 to-pink-400 bg-clip-text text-transparent">stat</span>
          </span>
          <div className="flex items-center gap-6 text-xs text-gray-600">
            <Link href="/dashboard" className="hover:text-white transition">Dashboard</Link>
            <Link href="/historique" className="hover:text-white transition">Historique</Link>
            <Link href="/login" className="hover:text-white transition">Connexion</Link>
            <span>© 2026 Kickstat</span>
          </div>
          <p className="text-xs text-gray-700">Jouez responsablement · 18+</p>
        </div>
      </footer>

    </div>
  );
}
