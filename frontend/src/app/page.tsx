'use client';

import { useEffect, useRef } from 'react';
import Link from 'next/link';

// =============================================================================
// NAV COMPONENT
// =============================================================================
function Nav() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-[rgba(8,8,13,0.85)] backdrop-blur-xl border-b border-border px-8">
      <div className="max-w-[1100px] mx-auto flex items-center justify-between h-[52px]">
        <Link href="/" className="flex items-center gap-2 no-underline">
          <div className="w-[26px] h-[26px] bg-gradient-to-br from-green to-[#00cc6a] rounded-md flex items-center justify-center font-mono font-bold text-[11px] text-bg">
            K
          </div>
          <span className="font-extrabold text-[17px] text-text-1 tracking-tight">kickstat</span>
        </Link>
        <div className="flex items-center gap-4">
          <Link href="#method" className="text-[11.5px] text-text-2 no-underline font-medium hover:text-text-1 transition-colors hidden md:block">
            Méthode
          </Link>
          <Link href="#proof" className="text-[11.5px] text-text-2 no-underline font-medium hover:text-text-1 transition-colors hidden md:block">
            Résultats
          </Link>
          <Link href="/login" className="btn-outline">
            Se connecter
          </Link>
          <Link href="#cta" className="btn-green text-[10px] px-3.5 py-1.5">
            Voir les opportunités →
          </Link>
        </div>
      </div>
    </nav>
  );
}

// =============================================================================
// HERO SECTION
// =============================================================================
function Hero() {
  return (
    <section className="min-h-screen flex flex-col items-center justify-center text-center px-8 pt-[120px] pb-20 relative overflow-hidden">
      {/* Glow effect */}
      <div className="absolute top-[-30%] left-1/2 -translate-x-1/2 w-[800px] h-[800px] bg-[radial-gradient(ellipse,rgba(0,232,123,0.06)_0%,transparent_65%)] pointer-events-none" />
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-border to-transparent" />

      <p className="font-mono text-[10px] text-green tracking-[4px] uppercase mb-4 opacity-0 animate-[fadeUp_0.6s_ease_0.2s_forwards]">
        Modèle prédictif · Ligue 1 &amp; Ligue 2
      </p>

      <h1 className="text-[clamp(32px,5.5vw,60px)] font-black tracking-tight leading-[1.05] mb-[18px] opacity-0 animate-[fadeUp_0.6s_ease_0.35s_forwards]">
        Les bookmakers font<br />des erreurs. <span className="gradient-text">On les trouve.</span>
      </h1>

      <p className="text-[clamp(14px,1.8vw,18px)] text-text-2 max-w-[560px] leading-relaxed mb-8 opacity-0 animate-[fadeUp_0.6s_ease_0.5s_forwards]">
        Notre IA analyse chaque match de Ligue 1 et identifie les paris où les bookmakers sous-estiment la probabilité réelle. On appelle ça un avantage.
      </p>

      <div className="flex gap-2.5 justify-center flex-wrap opacity-0 animate-[fadeUp_0.6s_ease_0.65s_forwards]">
        <Link href="#cta" className="btn-green text-[12px] px-[22px] py-2.5 rounded-lg">
          Voir les opportunités de la J21 →
        </Link>
        <Link href="#method" className="btn-outline text-[12px] px-[22px] py-2.5 rounded-lg">
          Comment ça marche
        </Link>
      </div>

      <div className="mt-10 flex gap-7 justify-center flex-wrap opacity-0 animate-[fadeUp_0.6s_ease_0.8s_forwards]">
        <div className="text-center">
          <div className="font-mono text-[28px] font-bold text-green leading-none">68.4%</div>
          <div className="font-mono text-[9px] text-text-3 uppercase tracking-[1.5px] mt-0.5">Taux de réussite</div>
        </div>
        <div className="text-center">
          <div className="font-mono text-[28px] font-bold text-green leading-none">361</div>
          <div className="font-mono text-[9px] text-text-3 uppercase tracking-[1.5px] mt-0.5">Prédictions analysées</div>
        </div>
        <div className="text-center">
          <div className="font-mono text-[28px] font-bold text-green leading-none">+11.3%</div>
          <div className="font-mono text-[9px] text-text-3 uppercase tracking-[1.5px] mt-0.5">ROI sur 3 mois</div>
        </div>
      </div>
    </section>
  );
}

// =============================================================================
// DEMO CARD SECTION
// =============================================================================
function DemoCard() {
  const barRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const modelBar = document.getElementById('model-bar');
            const bookBar = document.getElementById('book-bar');
            if (modelBar) modelBar.style.width = '62%';
            if (bookBar) bookBar.style.width = '49%';
          }
        });
      },
      { threshold: 0.3 }
    );

    if (barRef.current) observer.observe(barRef.current);
    return () => observer.disconnect();
  }, []);

  return (
    <section className="py-[60px] px-8 relative">
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-[radial-gradient(ellipse,rgba(0,232,123,0.04)_0%,transparent_70%)] pointer-events-none" />

      <div className="max-w-[680px] mx-auto" ref={barRef}>
        <div className="font-mono text-[9px] text-text-3 uppercase tracking-[3px] text-center mb-4">
          Exemple d&apos;opportunité détectée
        </div>

        <div className="card-gradient p-7 relative">
          {/* Left accent */}
          <div className="absolute top-0 left-0 w-1 h-full bg-green rounded-l-xl" />

          <div className="flex items-center gap-2 mb-1">
            <span className="badge-safe">Opportunité</span>
            <span className="font-mono text-[10px] text-text-3 tracking-wide">PSG vs Marseille · Samedi 21h · Ligue 1</span>
          </div>

          <div className="text-[20px] font-bold text-text-1 tracking-tight my-2.5 mb-4">
            Victoire du PSG
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
            {/* Bars */}
            <div className="flex flex-col gap-3.5">
              <div className="flex flex-col gap-1">
                <div className="flex justify-between items-center">
                  <span className="font-mono text-[10px] text-text-2 uppercase tracking-wider">Notre modèle</span>
                  <span className="font-mono text-[13px] font-bold text-green">62%</span>
                </div>
                <div className="h-2 bg-bg rounded border border-border overflow-hidden">
                  <div
                    id="model-bar"
                    className="h-full bg-gradient-to-r from-green to-[#00cc6a] rounded transition-[width] duration-[1.2s] ease-out"
                    style={{ width: '0%' }}
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1">
                <div className="flex justify-between items-center">
                  <span className="font-mono text-[10px] text-text-2 uppercase tracking-wider">Les bookmakers</span>
                  <span className="font-mono text-[13px] font-bold text-text-2">49%</span>
                </div>
                <div className="h-2 bg-bg rounded border border-border overflow-hidden">
                  <div
                    id="book-bar"
                    className="h-full bg-text-4 rounded transition-[width] duration-[1.2s] ease-out"
                    style={{ width: '0%' }}
                  />
                </div>
              </div>
            </div>

            {/* Edge box */}
            <div className="text-center p-5 bg-bg border border-border rounded-[10px]">
              <div className="font-mono text-[8px] text-text-3 uppercase tracking-[2px] mb-0.5">Avantage détecté</div>
              <div className="font-mono text-[42px] font-extrabold text-green leading-none">+13%</div>
              <div className="font-mono text-[9px] text-text-3 mt-1.5 leading-relaxed">
                Notre modèle donne 13 points<br />de plus que le marché
              </div>
            </div>
          </div>

          {/* Odds row */}
          <div className="mt-4 flex items-center justify-between pt-4 border-t border-border">
            <div className="flex flex-col gap-0.5">
              <span className="font-mono text-[8px] text-text-3 uppercase tracking-wider">Cote disponible</span>
              <span className="font-mono text-[22px] font-bold text-cyan">2.04</span>
            </div>
            <div className="text-[12px] text-green font-semibold flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-green shadow-[0_0_8px_rgba(0,232,123,0.3)]" />
              Pari sous-estimé par le marché
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// =============================================================================
// METHOD SECTION
// =============================================================================
function Method() {
  return (
    <section id="method" className="py-20 px-8 relative">
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-border to-transparent" />

      <div className="max-w-[900px] mx-auto">
        <div className="section-header">
          <div className="section-overline">La méthode</div>
          <h2 className="section-title">
            Chaque cote cache une probabilité.<br />On vérifie si elle est juste.
          </h2>
          <p className="section-subtitle">
            Quand un bookmaker propose une cote de 2.00, il estime la probabilité à 50%. Mais est-ce vraiment 50% ? C&apos;est là qu&apos;on intervient.
          </p>
        </div>

        <div className="flex flex-col">
          {/* Step 1 */}
          <Step
            number={1}
            title="Notre IA calcule la vraie probabilité"
            text={<>Notre modèle analyse <strong className="text-text-1 font-semibold">des dizaines de paramètres</strong> pour chaque match : classement ELO, forme récente, historique des confrontations, avantage du terrain, dynamique d&apos;équipe et bien plus. Il en sort une probabilité précise pour chaque résultat.</>}
            visual={
              <div className="mt-4 bg-bg-3 border border-border rounded-[10px] p-[18px] max-w-[480px]">
                <StepRow label="Classement ELO" value="1847 vs 1721" />
                <StepRow label="Forme domicile" value="V V V V N" valueClass="text-green" />
                <StepRow label="Confrontations directes" value="4V 1N 0D" />
                <StepRow label="xG moyen" value="2.1 vs 1.0" valueClass="text-green" />
                <StepRow label="+ 50 autres paramètres" value="..." valueClass="text-text-3" />
                <div className="text-center mt-3 pt-3 border-t border-border">
                  <div className="font-mono text-[8px] text-text-3 uppercase tracking-[1.5px] mb-0.5">Probabilité calculée</div>
                  <div className="font-mono text-[20px] font-bold text-green">62%</div>
                </div>
              </div>
            }
            isLast={false}
          />

          {/* Step 2 */}
          <Step
            number={2}
            title="On compare avec les bookmakers"
            text={<>Les bookmakers aussi estiment des probabilités — c&apos;est ce qui détermine les cotes. On compare <strong className="text-text-1 font-semibold">leur estimation avec la nôtre</strong>. Quand il y a un écart significatif, c&apos;est qu&apos;ils se trompent. Cet écart, c&apos;est <span className="text-green font-semibold">l&apos;avantage</span>.</>}
            visual={
              <div className="mt-4 bg-bg-3 border border-border rounded-[10px] p-[18px] max-w-[480px]">
                <div className="grid grid-cols-3 gap-3 items-center">
                  <div className="text-center">
                    <div className="font-mono text-[8px] text-text-3 uppercase tracking-[1.5px] mb-0.5">Notre modèle</div>
                    <div className="font-mono text-[26px] font-bold text-green">62%</div>
                  </div>
                  <div className="font-mono text-[10px] text-text-3 tracking-[2px] text-center">VS</div>
                  <div className="text-center">
                    <div className="font-mono text-[8px] text-text-3 uppercase tracking-[1.5px] mb-0.5">Bookmakers</div>
                    <div className="font-mono text-[26px] font-bold text-text-3">49%</div>
                  </div>
                </div>
                <div className="text-center mt-3 pt-3 border-t border-border">
                  <div className="font-mono text-[8px] text-text-3 uppercase tracking-[1.5px] mb-0.5">Avantage</div>
                  <div className="font-mono text-[20px] font-bold text-green">+13%</div>
                  <div className="text-[11px] text-text-3 mt-1">Le marché sous-estime cette probabilité de 13 points</div>
                </div>
              </div>
            }
            isLast={false}
          />

          {/* Step 3 */}
          <Step
            number={3}
            title="On vous montre les meilleures opportunités"
            text={<>On ne vous dit pas &quot;pariez ici&quot;. On vous montre <strong className="text-text-1 font-semibold">où le marché se trompe</strong>, classé par niveau de confiance. Paris simples, combinés, buteurs — chaque opportunité affiche la probabilité de notre modèle, la cote disponible et l&apos;avantage détecté.</>}
            visual={
              <div className="mt-4 bg-bg-3 border border-border rounded-[10px] p-[18px] max-w-[480px]">
                <StepRow label="🟢 Sûr — Forte proba, bon avantage" value="PSG gagne · 62% · cote 2.04" valueClass="text-green" />
                <StepRow label="🟠 Moyen — Proba correcte, cote élevée" value="Ramos buteur · 42% · cote 2.90" valueClass="text-amber" />
                <StepRow label="🔴 Risqué — Faible proba, très forte cote" value="Combiné 4 legs · 5.8% · cote 42.5" valueClass="text-red" />
              </div>
            }
            isLast={true}
          />
        </div>
      </div>
    </section>
  );
}

function Step({
  number,
  title,
  text,
  visual,
  isLast
}: {
  number: number;
  title: string;
  text: React.ReactNode;
  visual: React.ReactNode;
  isLast: boolean;
}) {
  return (
    <div className="grid grid-cols-[60px_1fr] gap-0 relative">
      <div className="flex flex-col items-center">
        <div className="w-9 h-9 rounded-full bg-bg-3 border-2 border-border-2 flex items-center justify-center font-mono text-[12px] font-bold text-green relative z-10">
          {number}
        </div>
        <div
          className={`flex-1 w-0.5 my-1 ${isLast ? 'bg-gradient-to-b from-border-2 to-transparent' : 'bg-gradient-to-b from-border-2 to-border'}`}
        />
      </div>
      <div className="pt-1 pb-12 pl-2">
        <h3 className="text-[17px] font-bold text-text-1 mb-1.5 tracking-tight">{title}</h3>
        <p className="text-[13.5px] text-text-2 leading-relaxed max-w-[500px]">{text}</p>
        {visual}
      </div>
    </div>
  );
}

function StepRow({ label, value, valueClass = '' }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-border last:border-0">
      <span className="text-[12px] text-text-2">{label}</span>
      <span className={`font-mono text-[13px] font-semibold ${valueClass || 'text-text-1'}`}>{value}</span>
    </div>
  );
}

// =============================================================================
// CONTRAST SECTION (Tipsters vs Kickstat)
// =============================================================================
function Contrast() {
  return (
    <section className="py-[60px] px-8">
      <div className="max-w-[900px] mx-auto">
        <div className="section-header">
          <div className="section-overline">La différence</div>
          <h2 className="section-title">On ne vous vend pas des pronostics.</h2>
          <p className="section-subtitle">On vous donne les outils pour décider vous-même, en toute transparence.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-7">
          {/* Bad - Tipsters */}
          <div className="rounded-xl p-6 border border-border relative overflow-hidden bg-gradient-to-br from-[rgba(255,68,102,0.03)] to-bg-2">
            <div className="absolute top-0 left-0 w-[3px] h-full bg-red" />
            <div className="text-[20px] mb-2.5">💬</div>
            <h3 className="text-[15px] font-bold mb-2 text-red">Les tipsters classiques</h3>
            <ul className="flex flex-col gap-1.5">
              <ContrastItem bad>&quot;Jouez Lyon, c&apos;est sûr&quot; — sans aucune donnée</ContrastItem>
              <ContrastItem bad>Pas de méthodologie visible</ContrastItem>
              <ContrastItem bad>Résultats invérifiables, screenshots truqués</ContrastItem>
              <ContrastItem bad>Profits basés sur votre abonnement, pas vos gains</ContrastItem>
              <ContrastItem bad>Émotions et intuitions présentées comme des analyses</ContrastItem>
            </ul>
          </div>

          {/* Good - Kickstat */}
          <div className="rounded-xl p-6 border border-border relative overflow-hidden bg-gradient-to-br from-[rgba(0,232,123,0.03)] to-bg-2">
            <div className="absolute top-0 left-0 w-[3px] h-full bg-green" />
            <div className="text-[20px] mb-2.5">📊</div>
            <h3 className="text-[15px] font-bold mb-2 text-green">Kickstat</h3>
            <ul className="flex flex-col gap-1.5">
              <ContrastItem good>Chaque prédiction est chiffrée avec une probabilité</ContrastItem>
              <ContrastItem good>Modèle IA transparent avec historique vérifiable</ContrastItem>
              <ContrastItem good>On montre quand on se trompe — 31.6% d&apos;échec visible</ContrastItem>
              <ContrastItem good>On détecte les erreurs du marché, pas des &quot;coups sûrs&quot;</ContrastItem>
              <ContrastItem good>Vous décidez, on vous donne juste les maths</ContrastItem>
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}

function ContrastItem({ children, bad, good }: { children: React.ReactNode; bad?: boolean; good?: boolean }) {
  return (
    <li className="text-[12.5px] text-text-2 leading-relaxed flex items-start gap-1.5">
      <span className={`font-mono text-[10px] font-bold mt-0.5 flex-shrink-0 ${bad ? 'text-red' : 'text-green'}`}>
        {bad ? '✗' : '✓'}
      </span>
      {children}
    </li>
  );
}

// =============================================================================
// PROOF SECTION
// =============================================================================
function Proof() {
  return (
    <section id="proof" className="py-[60px] px-8 relative">
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-border to-transparent" />

      <div className="max-w-[900px] mx-auto text-center">
        <div className="section-overline">Résultats vérifiables</div>
        <h2 className="section-title mb-8">Les chiffres parlent. Tous publics.</h2>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-9">
          <ProofCard value="68.4%" label="Taux de réussite sur 3 mois" />
          <ProofCard value="361" label="Prédictions analysées" />
          <ProofCard value="+11.3%" label="Retour sur investissement" />
          <ProofCard value="+8.2%" label="Avantage moyen par opportunité" />
        </div>

        {/* History mini grid */}
        <div className="flex gap-[3px] justify-center flex-wrap max-w-[500px] mx-auto">
          {['w','w','l','w','w','l','w','w','w','l','w','w','l','w','w','w','l','w','w','w','w','l','w','w','w','l','w','w','l','w'].map((r, i) => (
            <div
              key={i}
              className={`w-[22px] h-[22px] rounded-[3px] flex items-center justify-center font-mono text-[7px] font-semibold ${
                r === 'w'
                  ? 'bg-green-dark text-green border border-[rgba(0,232,123,0.08)]'
                  : 'bg-red-dark text-red border border-[rgba(255,68,102,0.08)]'
              }`}
            >
              {r === 'w' ? '✓' : '✗'}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ProofCard({ value, label }: { value: string; label: string }) {
  return (
    <div className="bg-bg-3 border border-border rounded-[10px] p-5">
      <div className="font-mono text-[28px] font-bold text-green leading-none">{value}</div>
      <div className="text-[11px] text-text-3 mt-1.5 leading-snug">{label}</div>
    </div>
  );
}

// =============================================================================
// FINAL CTA SECTION
// =============================================================================
function FinalCTA() {
  return (
    <section id="cta" className="py-20 px-8 text-center relative">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center_30%,rgba(0,232,123,0.06)_0%,transparent_55%)] pointer-events-none" />

      <h2 className="text-[clamp(26px,4vw,44px)] font-black tracking-tight mb-2 relative">
        Les maths, pas les émotions.
      </h2>
      <p className="text-[15px] text-text-2 mb-7 relative">
        Découvrez les opportunités détectées pour la Journée 21.
      </p>

      <div className="flex gap-2.5 justify-center flex-wrap relative">
        <Link href="/signup" className="btn-green text-[13px] px-[26px] py-3 rounded-lg">
          Voir les opportunités gratuites →
        </Link>
        <Link href="/signup" className="btn-outline text-[13px] px-[26px] py-3 rounded-lg">
          9,99€/mois → Accès complet
        </Link>
      </div>

      <p className="font-mono text-[8.5px] text-text-3 mt-4 relative">
        Quelques opportunités sont visibles gratuitement. L&apos;accès complet débloque tous les matchs, combinés et alertes.
      </p>
    </section>
  );
}

// =============================================================================
// FOOTER
// =============================================================================
function Footer() {
  return (
    <footer className="border-t border-border py-6 px-8">
      <div className="max-w-[1100px] mx-auto flex flex-col md:flex-row justify-between items-center gap-2 text-center md:text-left">
        <span className="font-mono text-[8.5px] text-text-3">
          © 2026 Kickstat · Modèle ELO/ML · v2.4
        </span>
        <span className="font-mono text-[7.5px] text-text-3 max-w-[380px] md:text-right leading-relaxed opacity-60">
          Analyse statistique uniquement. Ne constitue pas un conseil en investissement ni une incitation au jeu. Les performances passées ne préjugent pas des résultats futurs.
        </span>
      </div>
    </footer>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================
export default function LandingPage() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <DemoCard />
        <Method />
        <Contrast />
        <Proof />
        <FinalCTA />
      </main>
      <Footer />
    </>
  );
}
