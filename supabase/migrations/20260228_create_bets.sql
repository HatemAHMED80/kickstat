CREATE TABLE IF NOT EXISTS bets (
  id TEXT PRIMARY KEY,
  date DATE NOT NULL,
  kickoff TEXT,
  home_team TEXT NOT NULL,
  away_team TEXT NOT NULL,
  league TEXT NOT NULL,
  recommended_bet TEXT NOT NULL,
  odds NUMERIC,
  model_prob NUMERIC,
  edge_pct NUMERIC,
  confidence_badge TEXT,
  home_score INTEGER,
  away_score INTEGER,
  won BOOLEAN,
  pnl NUMERIC,
  resolved BOOLEAN NOT NULL DEFAULT false
);
ALTER TABLE bets ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Public read" ON bets;
CREATE POLICY "Public read" ON bets FOR SELECT USING (true);
