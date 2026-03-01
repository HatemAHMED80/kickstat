export default function AlgoPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Pipeline algorithmique v8 — optimise par ligue</h1>
        <p className="text-zinc-400 mt-1">
          Chaque ligue utilise sa propre strategie optimale par marche, calibree par grid-search sur 4 saisons (2021-2025).
          Backtest : <span className="text-emerald-400 font-semibold">+430.8u, +6.4% ROI</span> sur 5 ligues.
        </p>
      </div>

      {/* Pipeline Overview */}
      <section className="rounded-xl border border-white/10 bg-white/[0.02] p-6">
        <h2 className="text-lg font-semibold mb-4">Vue d&apos;ensemble du pipeline</h2>
        <div className="flex items-center gap-3 flex-wrap">
          {[
            { name: "Dixon-Coles", color: "bg-blue-500/20 text-blue-300 border-blue-500/30" },
            { name: "ELO", color: "bg-green-500/20 text-green-300 border-green-500/30" },
            { name: "XGBoost 1X2", color: "bg-amber-500/20 text-amber-300 border-amber-500/30" },
            { name: "XGB Props (O/U)", color: "bg-orange-500/20 text-orange-300 border-orange-500/30" },
            { name: "Calibration", color: "bg-purple-500/20 text-purple-300 border-purple-500/30" },
            { name: "Optimizer", color: "bg-pink-500/20 text-pink-300 border-pink-500/30" },
          ].map((algo, i) => (
            <div key={algo.name} className="flex items-center gap-3">
              <span className={`px-3 py-1.5 rounded-lg text-sm font-medium border ${algo.color}`}>
                {algo.name}
              </span>
              {i < 5 && <span className="text-zinc-600">&#8594;</span>}
            </div>
          ))}
        </div>
        <p className="text-zinc-500 text-sm mt-3">
          Les donnees traversent chaque etape. Dixon-Coles + ELO forment la baseline.
          XGBoost affine les 1X2, XGB Props les O/U. La calibration isotonique corrige les biais.
          L&apos;optimiseur selectionne la meilleure source de probabilite <span className="text-pink-300">par ligue x marche</span>.
        </p>
      </section>

      {/* Per-league strategy mapping */}
      <section className="rounded-xl border border-pink-500/20 bg-pink-500/[0.03] p-6">
        <div className="flex items-center gap-3 mb-4">
          <h2 className="text-lg font-semibold text-pink-300">Strategie optimale par ligue x marche</h2>
          <span className="text-xs px-2 py-0.5 rounded bg-pink-500/20 text-pink-400">v8 grid-search</span>
        </div>
        <p className="text-zinc-400 text-sm mb-4">
          L&apos;optimiseur teste 720 combinaisons (4 strategies x 18 seuils edge x 10 seuils proba) par marche
          et selectionne celle avec le meilleur PnL. Chaque cellule montre : strategie (PnL, ROI).
        </p>

        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/10 text-zinc-400">
                <th className="text-left py-2 pr-4">Ligue</th>
                <th className="text-center py-2 px-2">Home</th>
                <th className="text-center py-2 px-2">Draw</th>
                <th className="text-center py-2 px-2">Away</th>
                <th className="text-center py-2 px-2">Over 2.5</th>
                <th className="text-center py-2 px-2">Under 2.5</th>
                <th className="text-center py-2 px-2">AH Home</th>
                <th className="text-center py-2 px-2">AH Away</th>
                <th className="text-right py-2 pl-4 font-bold">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {[
                {
                  league: "Premier League", total: "+116.4u",
                  markets: [
                    { strat: "baseline", pnl: "+36.8u", roi: "+16.5%", edge: "3%", prob: "30%" },
                    { strat: "xgb_draw", pnl: "-5.7u", roi: "-24.6%", edge: "18%", prob: "25%" },
                    { strat: "xgb", pnl: "+3.6u", roi: "+22.7%", edge: "5%", prob: "65%" },
                    { strat: "xgb", pnl: "+14.5u", roi: "+5.8%", edge: "16%", prob: "50%" },
                    { strat: "baseline", pnl: "+20.8u", roi: "+9.2%", edge: "10%", prob: "55%" },
                    { strat: "baseline", pnl: "+11.7u", roi: "+6.4%", edge: "18%", prob: "25%" },
                    { strat: "baseline", pnl: "+3.2u", roi: "+0.4%", edge: "8%", prob: "25%" },
                  ],
                },
                {
                  league: "La Liga", total: "+72.8u",
                  markets: [
                    { strat: "xgb_cal", pnl: "+41.0u", roi: "+13.8%", edge: "20%", prob: "45%" },
                    { strat: "xgb_cal", pnl: "+32.7u", roi: "+16.4%", edge: "13%", prob: "30%" },
                    { strat: "xgb", pnl: "+18.8u", roi: "+24.4%", edge: "11%", prob: "50%" },
                    { strat: "baseline", pnl: "+18.5u", roi: "+11.1%", edge: "7%", prob: "65%" },
                    { strat: "xgb", pnl: "+16.1u", roi: "+10.0%", edge: "20%", prob: "50%" },
                    { strat: "baseline", pnl: "+14.1u", roi: "+11.5%", edge: "20%", prob: "60%" },
                    { strat: "baseline", pnl: "-18.7u", roi: "-16.2%", edge: "3%", prob: "70%" },
                  ],
                },
                {
                  league: "Bundesliga", total: "-4.1u",
                  markets: [
                    { strat: "xgb", pnl: "+13.2u", roi: "+25.4%", edge: "7%", prob: "65%" },
                    { strat: "xgb_cal", pnl: "+3.4u", roi: "+2.2%", edge: "16%", prob: "25%" },
                    { strat: "xgb_cal", pnl: "+7.5u", roi: "+15.1%", edge: "14%", prob: "40%" },
                    { strat: "xgb", pnl: "-1.0u", roi: "-1.2%", edge: "18%", prob: "65%" },
                    { strat: "baseline", pnl: "+19.0u", roi: "+29.7%", edge: "3%", prob: "60%" },
                    { strat: "baseline", pnl: "+3.1u", roi: "+11.4%", edge: "3%", prob: "70%" },
                    { strat: "baseline", pnl: "-21.4u", roi: "-29.0%", edge: "3%", prob: "70%" },
                  ],
                },
                {
                  league: "Serie A", total: "+135.7u",
                  markets: [
                    { strat: "xgb_draw", pnl: "+10.2u", roi: "+11.8%", edge: "12%", prob: "40%" },
                    { strat: "xgb_cal", pnl: "+91.3u", roi: "+13.8%", edge: "12%", prob: "25%" },
                    { strat: "xgb", pnl: "+35.1u", roi: "+12.4%", edge: "13%", prob: "30%" },
                    { strat: "xgb", pnl: "+3.4u", roi: "+3.4%", edge: "16%", prob: "55%" },
                    { strat: "baseline", pnl: "+38.1u", roi: "+12.9%", edge: "13%", prob: "25%" },
                    { strat: "baseline", pnl: "+3.1u", roi: "+7.0%", edge: "3%", prob: "65%" },
                    { strat: "baseline", pnl: "+36.5u", roi: "+5.0%", edge: "7%", prob: "25%" },
                  ],
                },
                {
                  league: "Ligue 1", total: "+110.2u",
                  markets: [
                    { strat: "xgb", pnl: "+11.7u", roi: "+24.5%", edge: "16%", prob: "50%" },
                    { strat: "xgb", pnl: "+8.1u", roi: "+5.7%", edge: "3%", prob: "25%" },
                    { strat: "baseline", pnl: "+41.8u", roi: "+8.3%", edge: "15%", prob: "25%" },
                    { strat: "xgb", pnl: "+3.1u", roi: "+6.5%", edge: "19%", prob: "60%" },
                    { strat: "baseline", pnl: "+3.9u", roi: "+1.5%", edge: "17%", prob: "35%" },
                    { strat: "baseline", pnl: "+11.1u", roi: "+4.5%", edge: "11%", prob: "25%" },
                    { strat: "baseline", pnl: "+29.2u", roi: "+5.3%", edge: "9%", prob: "55%" },
                  ],
                },
              ].map((row) => (
                <tr key={row.league}>
                  <td className="py-2 pr-4 font-medium text-sm">{row.league}</td>
                  {row.markets.map((m, i) => {
                    const isPositive = !m.pnl.startsWith("-");
                    const stratColor: Record<string, string> = {
                      baseline: "bg-blue-500/10 text-blue-300",
                      xgb: "bg-amber-500/10 text-amber-300",
                      xgb_draw: "bg-orange-500/10 text-orange-300",
                      xgb_cal: "bg-purple-500/10 text-purple-300",
                    };
                    return (
                      <td key={i} className="py-2 px-1 text-center">
                        <div className={`inline-block px-1.5 py-0.5 rounded ${stratColor[m.strat] || "bg-zinc-500/10 text-zinc-300"}`}>
                          {m.strat}
                        </div>
                        <div className={`font-mono mt-0.5 ${isPositive ? "text-emerald-400" : "text-red-400"}`}>
                          {m.pnl}
                        </div>
                        <div className="text-zinc-500 mt-0.5">
                          e{m.edge} p{m.prob}
                        </div>
                      </td>
                    );
                  })}
                  <td className={`py-2 pl-4 text-right font-mono font-bold text-sm ${row.total.startsWith("-") ? "text-red-400" : "text-emerald-400"}`}>
                    {row.total}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-4 flex flex-wrap gap-3 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-300">baseline</span>
            <span className="text-zinc-500">DC+ELO (65/35) + DC Poisson O/U</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-300">xgb</span>
            <span className="text-zinc-500">XGBoost stacking (tous marches)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="px-2 py-0.5 rounded bg-orange-500/10 text-orange-300">xgb_draw</span>
            <span className="text-zinc-500">XGB draw + DC+ELO home/away</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="px-2 py-0.5 rounded bg-purple-500/10 text-purple-300">xgb_cal</span>
            <span className="text-zinc-500">XGB + calibration isotonique</span>
          </div>
        </div>
      </section>

      {/* Dixon-Coles */}
      <section className="rounded-xl border border-blue-500/20 bg-blue-500/[0.03] p-6">
        <div className="flex items-center gap-3 mb-4">
          <h2 className="text-lg font-semibold text-blue-300">Dixon-Coles (1997)</h2>
          <span className="text-xs px-2 py-0.5 rounded bg-blue-500/20 text-blue-400">Modele de base</span>
        </div>
        <p className="text-zinc-400 text-sm mb-4">
          Modele bivariant de Poisson avec correction de correlation pour les scores faibles (0-0, 0-1, 1-0, 1-1).
          Estime les parametres attaque/defense par equipe via Maximum Likelihood Estimation (MLE)
          avec decroissance temporelle exponentielle.
        </p>

        <h3 className="text-sm font-semibold text-zinc-300 mb-2 mt-4">Parametres du modele</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            { param: "max_goals", value: "8", desc: "Score maximum modelise (matrice 9x9)" },
            { param: "half_life_days", value: "180 jours", desc: "Demi-vie pour la decroissance temporelle. Un match d'il y a 180 jours pese 50% d'un match recent." },
            { param: "home_advantage_init", value: "0.25", desc: "Valeur initiale du home advantage (avant optimisation MLE)" },
            { param: "rho_init", value: "-0.13", desc: "Correlation initiale pour les scores faibles" },
          ].map((p) => (
            <div key={p.param} className="rounded-lg bg-black/30 p-3">
              <div className="flex items-center gap-2 mb-1">
                <code className="text-blue-300 text-xs">{p.param}</code>
                <span className="text-white font-mono text-sm">{p.value}</span>
              </div>
              <p className="text-zinc-500 text-xs">{p.desc}</p>
            </div>
          ))}
        </div>

        <h3 className="text-sm font-semibold text-zinc-300 mb-2 mt-4">Parametres estimes par MLE</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            { param: "attack_i", value: "[0.2, 3.0]", desc: "Force offensive par equipe. Moyenne normalisee a 1.0." },
            { param: "defense_i", value: "[0.2, 3.0]", desc: "Faiblesse defensive par equipe (plus haut = plus facile a marquer contre). Moyenne normalisee a 1.0." },
            { param: "home_adv_i", value: "[0.0, 0.6] par equipe", desc: "Avantage a domicile par equipe (ex: Newcastle 0.35, Brighton 0.12). Regularisation ridge vers la moyenne." },
            { param: "rho", value: "[-0.3, 0.0]", desc: "Correction de correlation des scores faibles. Negatif = moins de 0-0 que prevu par Poisson independant." },
          ].map((p) => (
            <div key={p.param} className="rounded-lg bg-black/30 p-3">
              <div className="flex items-center gap-2 mb-1">
                <code className="text-blue-300 text-xs">{p.param}</code>
                <span className="text-white font-mono text-sm">{p.value}</span>
              </div>
              <p className="text-zinc-500 text-xs">{p.desc}</p>
            </div>
          ))}
        </div>

        <h3 className="text-sm font-semibold text-zinc-300 mb-2 mt-4">Formule</h3>
        <div className="rounded-lg bg-black/40 p-4 font-mono text-sm text-zinc-300 space-y-1">
          <p><span className="text-blue-300">lambda_home</span> = avg_goals * attack[home] * defense[away] * (1 + home_adv[home])</p>
          <p><span className="text-blue-300">lambda_away</span> = avg_goals * attack[away] * defense[home]</p>
          <p className="text-zinc-500 text-xs mt-2">Les buts suivent une distribution de Poisson : P(X=k) = e^(-lambda) * lambda^k / k!</p>
          <p className="text-zinc-500 text-xs">La matrice 9x9 de scores donne toutes les probas : 1X2, O/U, BTTS, Asian Handicap...</p>
        </div>

        <h3 className="text-sm font-semibold text-zinc-300 mb-2 mt-4">Optimisation</h3>
        <div className="rounded-lg bg-black/30 p-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
            <div><span className="text-zinc-500">Methode:</span> <span className="text-white">L-BFGS-B</span></div>
            <div><span className="text-zinc-500">Max iter:</span> <span className="text-white">2000</span></div>
            <div><span className="text-zinc-500">Tolerance:</span> <span className="text-white">1e-8</span></div>
            <div><span className="text-zinc-500">Refit:</span> <span className="text-white">tous les 30 matchs</span></div>
          </div>
        </div>
      </section>

      {/* ELO */}
      <section className="rounded-xl border border-green-500/20 bg-green-500/[0.03] p-6">
        <div className="flex items-center gap-3 mb-4">
          <h2 className="text-lg font-semibold text-green-300">ELO Rating</h2>
          <span className="text-xs px-2 py-0.5 rounded bg-green-500/20 text-green-400">1X2 uniquement</span>
        </div>
        <p className="text-zinc-400 text-sm mb-4">
          Systeme de classement ELO adapte au football. Chaque equipe a un rating qui evolue apres chaque match.
          La difference de rating est convertie en probabilites 1X2.
        </p>

        <h3 className="text-sm font-semibold text-zinc-300 mb-2">Parametres</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            { param: "k_factor", value: "20", desc: "Vitesse d'ajustement du rating apres chaque match. Plus eleve = reactions plus fortes aux resultats recents." },
            { param: "home_advantage", value: "100 pts", desc: "Bonus ELO ajoute a l'equipe a domicile pour le calcul de probabilite. ~100 pts = environ +7% de chance de gagner." },
            { param: "initial_rating", value: "1500", desc: "Rating de depart pour les nouvelles equipes." },
            { param: "seasonal_decay", value: "0.85", desc: "Regression vers la moyenne entre les saisons (rating * 0.85 + mean * 0.15)." },
          ].map((p) => (
            <div key={p.param} className="rounded-lg bg-black/30 p-3">
              <div className="flex items-center gap-2 mb-1">
                <code className="text-green-300 text-xs">{p.param}</code>
                <span className="text-white font-mono text-sm">{p.value}</span>
              </div>
              <p className="text-zinc-500 text-xs">{p.desc}</p>
            </div>
          ))}
        </div>

        <h3 className="text-sm font-semibold text-zinc-300 mb-2 mt-4">Formule</h3>
        <div className="rounded-lg bg-black/40 p-4 font-mono text-sm text-zinc-300 space-y-1">
          <p><span className="text-green-300">expected</span> = 1 / (1 + 10^((rating_away - (rating_home + 100)) / 400))</p>
          <p><span className="text-green-300">new_rating</span> = old_rating + K * (result - expected)</p>
          <p className="text-zinc-500 text-xs mt-2">result: 1=victoire, 0.5=nul, 0=defaite</p>
        </div>
      </section>

      {/* Ensemble */}
      <section className="rounded-xl border border-violet-500/20 bg-violet-500/[0.03] p-6">
        <div className="flex items-center gap-3 mb-4">
          <h2 className="text-lg font-semibold text-violet-300">Ensemble (DC + ELO)</h2>
          <span className="text-xs px-2 py-0.5 rounded bg-violet-500/20 text-violet-400">Fusion ponderee = baseline</span>
        </div>
        <p className="text-zinc-400 text-sm mb-4">
          Les probabilites 1X2 de Dixon-Coles et ELO sont fusionnees par moyenne ponderee.
          Cette fusion est la &quot;baseline&quot; du systeme — la prediction sans XGBoost.
          Utilisee comme strategie principale pour certaines ligues/marches.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="rounded-lg bg-black/30 p-3">
            <div className="flex items-center gap-2 mb-1">
              <code className="text-violet-300 text-xs">dc_weight</code>
              <span className="text-white font-mono text-sm">0.65 (65%)</span>
            </div>
            <p className="text-zinc-500 text-xs">Poids de Dixon-Coles dans la fusion. DC est plus precis grace a la matrice de scores.</p>
          </div>
          <div className="rounded-lg bg-black/30 p-3">
            <div className="flex items-center gap-2 mb-1">
              <code className="text-violet-300 text-xs">elo_weight</code>
              <span className="text-white font-mono text-sm">0.35 (35%)</span>
            </div>
            <p className="text-zinc-500 text-xs">Poids d&apos;ELO dans la fusion. ELO apporte l&apos;inertie de la forme longue duree.</p>
          </div>
        </div>

        <h3 className="text-sm font-semibold text-zinc-300 mb-2 mt-4">Formule</h3>
        <div className="rounded-lg bg-black/40 p-4 font-mono text-sm text-zinc-300">
          <p><span className="text-violet-300">P(home)</span> = 0.65 * DC_home + 0.35 * ELO_home &nbsp;&nbsp; (puis normalise pour que la somme = 1)</p>
        </div>
      </section>

      {/* XGBoost 1X2 */}
      <section className="rounded-xl border border-amber-500/20 bg-amber-500/[0.03] p-6">
        <div className="flex items-center gap-3 mb-4">
          <h2 className="text-lg font-semibold text-amber-300">XGBoost Stacking (1X2)</h2>
          <span className="text-xs px-2 py-0.5 rounded bg-amber-500/20 text-amber-400">Utilise selon la ligue/marche</span>
        </div>
        <p className="text-zinc-400 text-sm mb-4">
          XGBoost est un meta-modele qui prend en entree les predictions DC+ELO + 50 features
          (forme, tirs, corners, H2H, repos...) pour affiner la probabilite 1X2.
          Selon la ligue, il est utilise pour certains marches et pas d&apos;autres (voir tableau ci-dessus).
        </p>

        <h3 className="text-sm font-semibold text-zinc-300 mb-2">3 modes d&apos;utilisation</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
          <div className="rounded-lg bg-black/30 p-3">
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 text-xs">xgb</span>
            </div>
            <p className="text-zinc-500 text-xs">XGBoost remplace les probas 1X2 (home, draw, away). Utilise pour away en PL, Liga, Bundesliga, Serie A.</p>
          </div>
          <div className="rounded-lg bg-black/30 p-3">
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2 py-0.5 rounded bg-orange-500/10 text-orange-300 text-xs">xgb_draw</span>
            </div>
            <p className="text-zinc-500 text-xs">XGBoost remplace uniquement la proba draw. Home/away restent DC+ELO. Utilise pour draw en PL, home en Serie A.</p>
          </div>
          <div className="rounded-lg bg-black/30 p-3">
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2 py-0.5 rounded bg-purple-500/10 text-purple-300 text-xs">xgb_cal</span>
            </div>
            <p className="text-zinc-500 text-xs">XGBoost + calibration isotonique. Corrige les biais de confiance. Utilise pour home en Liga, draw en Liga/Bundesliga/Serie A.</p>
          </div>
        </div>

        <h3 className="text-sm font-semibold text-zinc-300 mb-2">Hyperparametres</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {[
            { param: "max_depth", value: "4", desc: "Arbres peu profonds pour reduire l'overfitting" },
            { param: "learning_rate", value: "0.06", desc: "Taux d'apprentissage conservateur" },
            { param: "n_estimators", value: "100", desc: "Nombre d'arbres (avec early stopping a 20)" },
            { param: "min_child_weight", value: "10", desc: "Minimum de poids par feuille" },
            { param: "subsample", value: "0.66", desc: "66% des lignes par arbre" },
            { param: "colsample_bytree", value: "0.62", desc: "62% des features par arbre" },
            { param: "reg_alpha (L1)", value: "1.90", desc: "Regularisation Lasso" },
            { param: "reg_lambda (L2)", value: "4.86", desc: "Regularisation Ridge (forte)" },
            { param: "scale_pos_weight", value: "1.71", desc: "Correction du desequilibre de classes" },
          ].map((p) => (
            <div key={p.param} className="rounded-lg bg-black/30 p-3">
              <div className="flex items-center gap-2 mb-1">
                <code className="text-amber-300 text-xs">{p.param}</code>
                <span className="text-white font-mono text-sm">{p.value}</span>
              </div>
              <p className="text-zinc-500 text-xs">{p.desc}</p>
            </div>
          ))}
        </div>

        <h3 className="text-sm font-semibold text-zinc-300 mb-2 mt-4">50 features en entree</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
          {[
            { cat: "Probas de base (6)", features: "dc_home/draw/away_prob, elo_home/draw/away_prob", color: "text-blue-300" },
            { cat: "Force DC (4)", features: "dc_home/away_attack, dc_home/away_defense", color: "text-blue-300" },
            { cat: "ELO (3)", features: "elo_home/away_rating, elo_diff", color: "text-green-300" },
            { cat: "Forme 5 matchs (8)", features: "ppg, goals scored/conceded, home ppg, away ppg", color: "text-orange-300" },
            { cat: "Tirs 5 matchs (8)", features: "shots pg, sot pg, shot accuracy, sot ratio", color: "text-orange-300" },
            { cat: "Dominance 5 matchs (6)", features: "corners pg, fouls pg, dominance index", color: "text-orange-300" },
            { cat: "Differentiels (5)", features: "ppg_diff, goals_diff, sot_diff, corner_diff, dominance_diff", color: "text-pink-300" },
            { cat: "H2H (4)", features: "h2h_matches, home_win_rate, goals_pg, over25_rate", color: "text-cyan-300" },
            { cat: "Repos + contexte (6)", features: "home/away_rest_days, season_progress, match_importance, etc.", color: "text-cyan-300" },
          ].map((g) => (
            <div key={g.cat} className="rounded-lg bg-black/30 p-2">
              <span className={`font-medium ${g.color}`}>{g.cat}:</span>
              <span className="text-zinc-400 ml-1">{g.features}</span>
            </div>
          ))}
        </div>
      </section>

      {/* XGB Props (O/U) */}
      <section className="rounded-xl border border-orange-500/20 bg-orange-500/[0.03] p-6">
        <div className="flex items-center gap-3 mb-4">
          <h2 className="text-lg font-semibold text-orange-300">XGB Prop Model (Over/Under)</h2>
          <span className="text-xs px-2 py-0.5 rounded bg-orange-500/20 text-orange-400">Classification binaire</span>
        </div>
        <p className="text-zinc-400 text-sm mb-4">
          Modele XGBoost binaire dedie au marche Over/Under 2.5. Utilise les memes 50 features que le XGB 1X2
          mais predit P(total goals &gt; 2.5) directement. Alternative a la matrice de scores DC Poisson.
          Utilise dans les ligues ou il surperforme DC (PL, Bundesliga, Serie A, Ligue 1 pour over25).
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="rounded-lg bg-black/30 p-3">
            <div className="flex items-center gap-2 mb-1">
              <code className="text-orange-300 text-xs">market_name</code>
              <span className="text-white font-mono text-sm">over25</span>
            </div>
            <p className="text-zinc-500 text-xs">Classificateur binaire : 1 = plus de 2 buts, 0 = 2 buts ou moins.</p>
          </div>
          <div className="rounded-lg bg-black/30 p-3">
            <div className="flex items-center gap-2 mb-1">
              <code className="text-orange-300 text-xs">retrain</code>
              <span className="text-white font-mono text-sm">60 matchs</span>
            </div>
            <p className="text-zinc-500 text-xs">Re-entraine en meme temps que le XGB 1X2. Min 100 samples.</p>
          </div>
        </div>
      </section>

      {/* Calibration */}
      <section className="rounded-xl border border-purple-500/20 bg-purple-500/[0.03] p-6">
        <div className="flex items-center gap-3 mb-4">
          <h2 className="text-lg font-semibold text-purple-300">Calibration isotonique</h2>
          <span className="text-xs px-2 py-0.5 rounded bg-purple-500/20 text-purple-400">Post-hoc</span>
        </div>
        <p className="text-zinc-400 text-sm mb-4">
          Regression isotonique appliquee apres XGBoost pour corriger les biais systematiques de confiance.
          Si le modele dit 30% mais la realite est 25%, la calibration apprend a corriger ce decalage.
          Utilisee dans la strategie &quot;xgb_cal&quot; pour Liga (home, draw), Bundesliga (draw, away), Serie A (draw).
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            { param: "method", value: "isotonic", desc: "Regression isotonique (non-parametrique, monotone)" },
            { param: "retrain_interval", value: "100 matchs", desc: "Recalibre tous les 100 matchs avec les nouvelles donnees" },
            { param: "min_samples", value: "80", desc: "Ne calibre pas tant qu'il y a moins de 80 predictions" },
            { param: "out_of_bounds", value: "clip", desc: "Les predictions hors de l'intervalle d'entrainement sont clippees" },
          ].map((p) => (
            <div key={p.param} className="rounded-lg bg-black/30 p-3">
              <div className="flex items-center gap-2 mb-1">
                <code className="text-purple-300 text-xs">{p.param}</code>
                <span className="text-white font-mono text-sm">{p.value}</span>
              </div>
              <p className="text-zinc-500 text-xs">{p.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Edge & Betting */}
      <section className="rounded-xl border border-white/10 bg-white/[0.02] p-6">
        <div className="flex items-center gap-3 mb-4">
          <h2 className="text-lg font-semibold">Decision de pari</h2>
          <span className="text-xs px-2 py-0.5 rounded bg-zinc-500/20 text-zinc-400">3 filtres</span>
        </div>
        <p className="text-zinc-400 text-sm mb-4">
          Un pari est recommande uniquement si les 3 conditions sont remplies simultanement.
          <span className="text-pink-300"> Les seuils sont optimises par ligue x marche</span> (voir tableau ci-dessus).
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="rounded-lg bg-black/30 p-4 border border-white/5">
            <div className="text-lg font-bold text-white mb-1">1. Edge</div>
            <div className="font-mono text-sm text-emerald-300 mb-2">edge = (model_prob - fair_prob) / fair_prob</div>
            <p className="text-zinc-500 text-xs">
              La probabilite du modele doit depasser la probabilite implicite du marche (Pinnacle devigged)
              d&apos;un seuil minimum. Seuils optimaux : de 3% (Ligue 1 draw) a 20% (Liga home, Liga under25).
            </p>
          </div>
          <div className="rounded-lg bg-black/30 p-4 border border-white/5">
            <div className="text-lg font-bold text-white mb-1">2. Probabilite min</div>
            <div className="font-mono text-sm text-emerald-300 mb-2">model_prob &gt;= seuil par ligue x marche</div>
            <p className="text-zinc-500 text-xs">
              Filtre les paris sur des evenements trop improbables. Le facteur le plus decisif selon l&apos;optimisation.
              Exemples : Bundesliga home 65%, PL away 65%, Liga O/U 65%.
            </p>
          </div>
          <div className="rounded-lg bg-black/30 p-4 border border-white/5">
            <div className="text-lg font-bold text-white mb-1">3. Kelly &gt;= 1%</div>
            <div className="font-mono text-sm text-emerald-300 mb-2">kelly = (b*p - q) / b * 0.15</div>
            <p className="text-zinc-500 text-xs">
              Le critere de Kelly (fraction 0.15) doit recommander au moins 1% du bankroll.
              Filtre les edges insuffisants par rapport a la cote.
            </p>
          </div>
        </div>
      </section>

      {/* Training schedule */}
      <section className="rounded-xl border border-white/10 bg-white/[0.02] p-6">
        <h2 className="text-lg font-semibold mb-4">Frequence de re-entrainement (backtest walk-forward)</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/10 text-zinc-400">
                <th className="text-left py-2 pr-4">Modele</th>
                <th className="text-left py-2 px-4">Frequence</th>
                <th className="text-left py-2 px-4">Min. donnees</th>
                <th className="text-left py-2 px-4">Note</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-zinc-300">
              <tr>
                <td className="py-2 pr-4 text-blue-300">Dixon-Coles</td>
                <td className="py-2 px-4">30 matchs</td>
                <td className="py-2 px-4">120 matchs</td>
                <td className="py-2 px-4 text-zinc-500 text-xs">Re-optimise tous les parametres via MLE</td>
              </tr>
              <tr>
                <td className="py-2 pr-4 text-amber-300">XGBoost 1X2</td>
                <td className="py-2 px-4">60 matchs</td>
                <td className="py-2 px-4">200 samples</td>
                <td className="py-2 px-4 text-zinc-500 text-xs">Re-entraine avec early stopping (20 rounds)</td>
              </tr>
              <tr>
                <td className="py-2 pr-4 text-orange-300">XGB Props (O/U)</td>
                <td className="py-2 px-4">60 matchs</td>
                <td className="py-2 px-4">100 samples</td>
                <td className="py-2 px-4 text-zinc-500 text-xs">Classificateur binaire over/under 2.5</td>
              </tr>
              <tr>
                <td className="py-2 pr-4 text-purple-300">Calibration</td>
                <td className="py-2 px-4">100 matchs</td>
                <td className="py-2 px-4">80 predictions</td>
                <td className="py-2 px-4 text-zinc-500 text-xs">Regression isotonique sur les predictions XGB</td>
              </tr>
              <tr>
                <td className="py-2 pr-4 text-green-300">ELO</td>
                <td className="py-2 px-4">Chaque match</td>
                <td className="py-2 px-4">0</td>
                <td className="py-2 px-4 text-zinc-500 text-xs">Mise a jour incrementale apres chaque resultat</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
