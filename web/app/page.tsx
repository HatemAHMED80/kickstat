import Link from 'next/link';

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      {/* Navigation */}
      <nav className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <div className="flex items-center">
              <span className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-cyan-600 bg-clip-text text-transparent">
                ⚽ SmartBet
              </span>
            </div>
            <div className="hidden md:flex items-center space-x-8">
              <Link href="#features" className="text-gray-600 hover:text-gray-900">Features</Link>
              <Link href="#pricing" className="text-gray-600 hover:text-gray-900">Pricing</Link>
              <Link href="#results" className="text-gray-600 hover:text-gray-900">Results</Link>
              <Link href="/dashboard" className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition">
                Dashboard
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-20 pb-32 px-4">
        <div className="max-w-7xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-green-50 border border-green-200 text-green-700 text-sm font-medium mb-8">
            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
            Validated on 3,800+ matches • +6.7% ROI
          </div>

          <h1 className="text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-gray-900 via-blue-800 to-gray-900 bg-clip-text text-transparent">
            Stop Losing Money<br />
            on <span className="text-blue-600">Bad Bets</span>
          </h1>

          <p className="text-xl md:text-2xl text-gray-600 mb-12 max-w-3xl mx-auto">
            AI-powered predictions for Ligue 1 & Premier League.<br />
            Validated +6.7% ROI on 985 underdog bets. Free daily picks.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-16">
            <Link
              href="/dashboard"
              className="px-8 py-4 rounded-lg bg-blue-600 text-white text-lg font-semibold hover:bg-blue-700 transition shadow-lg hover:shadow-xl"
            >
              View Today's Predictions →
            </Link>
            <Link
              href="#results"
              className="px-8 py-4 rounded-lg bg-white text-gray-900 text-lg font-semibold hover:bg-gray-50 transition border-2 border-gray-200"
            >
              See Track Record
            </Link>
          </div>

          {/* Social Proof */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 max-w-4xl mx-auto">
            <div className="text-center">
              <div className="text-3xl font-bold text-gray-900">3,800+</div>
              <div className="text-sm text-gray-600">Matches Analyzed</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-green-600">+6.7%</div>
              <div className="text-sm text-gray-600">Underdog ROI</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-blue-600">+8.1%</div>
              <div className="text-sm text-gray-600">Favorites ROI</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-gray-900">2</div>
              <div className="text-sm text-gray-600">Top Leagues</div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4">Why SmartBet Works</h2>
            <p className="text-xl text-gray-600">
              Academic-grade models validated on 5 years of historical data
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <div className="p-8 rounded-2xl bg-gradient-to-br from-blue-50 to-cyan-50 border border-blue-100">
              <div className="text-4xl mb-4">📊</div>
              <h3 className="text-2xl font-bold mb-3">Dixon-Coles Model</h3>
              <p className="text-gray-600">
                Industry-standard bivariate Poisson model used by professional betting syndicates.
                Accounts for low-scoring game correlation.
              </p>
            </div>

            <div className="p-8 rounded-2xl bg-gradient-to-br from-green-50 to-emerald-50 border border-green-100">
              <div className="text-4xl mb-4">🎯</div>
              <h3 className="text-2xl font-bold mb-3">ELO Ratings</h3>
              <p className="text-gray-600">
                Dynamic team strength ratings updated after every match.
                Captures recent form better than static models.
              </p>
            </div>

            <div className="p-8 rounded-2xl bg-gradient-to-br from-purple-50 to-pink-50 border border-purple-100">
              <div className="text-4xl mb-4">💰</div>
              <h3 className="text-2xl font-bold mb-3">Edge Detection</h3>
              <p className="text-gray-600">
                Only shows bets where our model finds +5% edge vs bookmaker odds.
                Quality over quantity.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Results Section */}
      <section id="results" className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4">Proven Track Record</h2>
            <p className="text-xl text-gray-600">
              Validated on Ligue 1 & Premier League (2020-2024)
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8 max-w-5xl mx-auto">
            <div className="p-8 bg-white rounded-2xl shadow-lg border border-gray-100">
              <h3 className="text-2xl font-bold mb-6">Underdogs (30-45% win prob)</h3>
              <div className="space-y-4">
                <div className="flex justify-between">
                  <span className="text-gray-600">Total Bets (5 years)</span>
                  <span className="font-bold">985 bets</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Win Rate</span>
                  <span className="font-bold">33.0%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">ROI</span>
                  <span className="font-bold text-green-600 text-2xl">+6.7%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Profit (100€/bet)</span>
                  <span className="font-bold text-green-600">+6,595€</span>
                </div>
              </div>
            </div>

            <div className="p-8 bg-white rounded-2xl shadow-lg border border-gray-100">
              <h3 className="text-2xl font-bold mb-6">Strong Favorites (75%+ win prob)</h3>
              <div className="space-y-4">
                <div className="flex justify-between">
                  <span className="text-gray-600">Total Bets (5 years)</span>
                  <span className="font-bold">159 bets</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Win Rate</span>
                  <span className="font-bold">79.2%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">ROI</span>
                  <span className="font-bold text-green-600 text-2xl">+5.7%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Profit (100€/bet)</span>
                  <span className="font-bold text-green-600">+906€</span>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-12 p-6 bg-blue-50 rounded-xl border border-blue-200 max-w-3xl mx-auto">
            <p className="text-center text-gray-700">
              <strong>Transparency:</strong> All results are from walk-forward backtests using Pinnacle closing odds.
              No cherry-picking, no curve-fitting.
            </p>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4">Simple Pricing</h2>
            <p className="text-xl text-gray-600">
              Start free, upgrade when you're winning
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
            {/* Free Tier */}
            <div className="p-8 rounded-2xl border-2 border-gray-200 bg-white">
              <h3 className="text-2xl font-bold mb-2">Free</h3>
              <div className="text-4xl font-bold mb-6">€0<span className="text-lg text-gray-600">/month</span></div>
              <ul className="space-y-3 mb-8">
                <li className="flex items-start">
                  <span className="text-green-600 mr-2">✓</span>
                  <span>Daily 1X2 predictions</span>
                </li>
                <li className="flex items-start">
                  <span className="text-green-600 mr-2">✓</span>
                  <span>Ligue 1 & Premier League</span>
                </li>
                <li className="flex items-start">
                  <span className="text-green-600 mr-2">✓</span>
                  <span>Best odds comparison</span>
                </li>
                <li className="flex items-start">
                  <span className="text-gray-400 mr-2">✗</span>
                  <span className="text-gray-400">SMS/Email alerts</span>
                </li>
              </ul>
              <button className="w-full py-3 rounded-lg border-2 border-gray-300 text-gray-700 font-semibold hover:bg-gray-50 transition">
                Get Started
              </button>
            </div>

            {/* Pro Tier */}
            <div className="p-8 rounded-2xl border-2 border-blue-600 bg-gradient-to-br from-blue-50 to-white relative">
              <div className="absolute -top-4 left-1/2 -translate-x-1/2 px-4 py-1 bg-blue-600 text-white text-sm font-bold rounded-full">
                POPULAR
              </div>
              <h3 className="text-2xl font-bold mb-2">Pro</h3>
              <div className="text-4xl font-bold mb-6">€9<span className="text-lg text-gray-600">/month</span></div>
              <ul className="space-y-3 mb-8">
                <li className="flex items-start">
                  <span className="text-green-600 mr-2">✓</span>
                  <span><strong>Everything in Free</strong></span>
                </li>
                <li className="flex items-start">
                  <span className="text-green-600 mr-2">✓</span>
                  <span>Real-time SMS/Email alerts</span>
                </li>
                <li className="flex items-start">
                  <span className="text-green-600 mr-2">✓</span>
                  <span>Kelly Calculator</span>
                </li>
                <li className="flex items-start">
                  <span className="text-green-600 mr-2">✓</span>
                  <span>ROI Tracker</span>
                </li>
                <li className="flex items-start">
                  <span className="text-green-600 mr-2">✓</span>
                  <span>Historical performance data</span>
                </li>
              </ul>
              <button className="w-full py-3 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700 transition">
                Start 7-Day Trial
              </button>
            </div>

            {/* Premium Tier */}
            <div className="p-8 rounded-2xl border-2 border-gray-200 bg-white">
              <h3 className="text-2xl font-bold mb-2">Premium</h3>
              <div className="text-4xl font-bold mb-6">€29<span className="text-lg text-gray-600">/month</span></div>
              <ul className="space-y-3 mb-8">
                <li className="flex items-start">
                  <span className="text-green-600 mr-2">✓</span>
                  <span><strong>Everything in Pro</strong></span>
                </li>
                <li className="flex items-start">
                  <span className="text-green-600 mr-2">✓</span>
                  <span>API Access</span>
                </li>
                <li className="flex items-start">
                  <span className="text-green-600 mr-2">✓</span>
                  <span>Custom alerts & filters</span>
                </li>
                <li className="flex items-start">
                  <span className="text-green-600 mr-2">✓</span>
                  <span>Priority support</span>
                </li>
                <li className="flex items-start">
                  <span className="text-green-600 mr-2">✓</span>
                  <span>Private Discord access</span>
                </li>
              </ul>
              <button className="w-full py-3 rounded-lg border-2 border-gray-300 text-gray-700 font-semibold hover:bg-gray-50 transition">
                Contact Sales
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-gradient-to-r from-blue-600 to-cyan-600">
        <div className="max-w-4xl mx-auto px-4 text-center">
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-6">
            Ready to Stop Guessing?
          </h2>
          <p className="text-xl text-blue-100 mb-8">
            Join hundreds of smart bettors making data-driven decisions
          </p>
          <Link
            href="/dashboard"
            className="inline-block px-8 py-4 rounded-lg bg-white text-blue-600 text-lg font-semibold hover:bg-gray-50 transition shadow-xl"
          >
            View Free Predictions →
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-400 py-12">
        <div className="max-w-7xl mx-auto px-4">
          <div className="grid md:grid-cols-4 gap-8">
            <div>
              <div className="text-white font-bold text-xl mb-4">⚽ SmartBet</div>
              <p className="text-sm">
                AI-powered football predictions for Ligue 1 & Premier League
              </p>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Product</h4>
              <ul className="space-y-2 text-sm">
                <li><Link href="/dashboard">Dashboard</Link></li>
                <li><Link href="/#features">Features</Link></li>
                <li><Link href="/#pricing">Pricing</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Resources</h4>
              <ul className="space-y-2 text-sm">
                <li><Link href="/blog">Blog</Link></li>
                <li><Link href="/methodology">Methodology</Link></li>
                <li><Link href="/faq">FAQ</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Legal</h4>
              <ul className="space-y-2 text-sm">
                <li><Link href="/terms">Terms</Link></li>
                <li><Link href="/privacy">Privacy</Link></li>
                <li><Link href="/disclaimer">Disclaimer</Link></li>
              </ul>
            </div>
          </div>
          <div className="border-t border-gray-800 mt-8 pt-8 text-center text-sm">
            <p>&copy; 2024 SmartBet. All rights reserved.</p>
            <p className="mt-2 text-xs text-gray-500">
              Gambling can be addictive. Play responsibly. 18+
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
