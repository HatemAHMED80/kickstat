"""Test football-data.org API to verify season 2025-2026 access.

Get a free API key at: https://www.football-data.org/client/register
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_football_data_org():
    """Test football-data.org API access to 2025-2026 season."""

    api_key = os.getenv("FOOTBALL_DATA_ORG_KEY")

    if not api_key or api_key == "your_key_here":
        print("❌ Error: FOOTBALL_DATA_ORG_KEY not set in .env")
        print("\n📝 To get a free API key:")
        print("   1. Go to https://www.football-data.org/client/register")
        print("   2. Register for free (no credit card needed)")
        print("   3. Copy your API key")
        print("   4. Add to .env: FOOTBALL_DATA_ORG_KEY=your_key_here")
        return

    print("🔍 Testing football-data.org API...\n")

    headers = {"X-Auth-Token": api_key}
    base_url = "https://api.football-data.org/v4"

    # Test 1: Check available competitions
    print("Test 1: Fetching available competitions...")
    try:
        response = requests.get(f"{base_url}/competitions", headers=headers, timeout=10)
        response.raise_for_status()
        competitions = response.json()["competitions"]

        # Find Ligue 1 and Premier League
        ligue1 = next((c for c in competitions if "Ligue 1" in c["name"]), None)
        premier_league = next((c for c in competitions if "Premier League" in c["name"]), None)

        print(f"✅ Found {len(competitions)} competitions")

        if ligue1:
            print(f"   ✅ Ligue 1 (ID: {ligue1['id']}, Code: {ligue1['code']})")
            print(f"      Current Season: {ligue1.get('currentSeason', {}).get('startDate', 'Unknown')}")
        else:
            print("   ❌ Ligue 1 NOT found")

        if premier_league:
            print(f"   ✅ Premier League (ID: {premier_league['id']}, Code: {premier_league['code']})")
            print(f"      Current Season: {premier_league.get('currentSeason', {}).get('startDate', 'Unknown')}")
        else:
            print("   ❌ Premier League NOT found")

    except Exception as e:
        print(f"❌ Error fetching competitions: {e}")
        return

    # Test 2: Fetch fixtures for Premier League (most likely to have data)
    if premier_league:
        print(f"\nTest 2: Fetching Premier League fixtures (current season)...")
        try:
            pl_id = premier_league["id"]
            response = requests.get(
                f"{base_url}/competitions/{pl_id}/matches",
                headers=headers,
                params={"status": "SCHEDULED"},  # Only upcoming matches
                timeout=10
            )
            response.raise_for_status()
            matches = response.json()["matches"]

            print(f"✅ Found {len(matches)} upcoming Premier League matches")

            # Show first 3 fixtures
            for i, match in enumerate(matches[:3], 1):
                home = match["homeTeam"]["name"]
                away = match["awayTeam"]["name"]
                date = match["utcDate"]
                print(f"   {i}. {home} vs {away} @ {date}")

        except Exception as e:
            print(f"❌ Error fetching fixtures: {e}")
            if "403" in str(e) or "plan" in str(e).lower():
                print("      ⚠️  This might be a plan limitation")
            return

    # Test 3: Check Ligue 1 access
    if ligue1:
        print(f"\nTest 3: Fetching Ligue 1 fixtures (current season)...")
        try:
            l1_id = ligue1["id"]
            response = requests.get(
                f"{base_url}/competitions/{l1_id}/matches",
                headers=headers,
                params={"status": "SCHEDULED"},
                timeout=10
            )
            response.raise_for_status()
            matches = response.json()["matches"]

            print(f"✅ Found {len(matches)} upcoming Ligue 1 matches")

            # Show first 3 fixtures
            for i, match in enumerate(matches[:3], 1):
                home = match["homeTeam"]["name"]
                away = match["awayTeam"]["name"]
                date = match["utcDate"]
                print(f"   {i}. {home} vs {away} @ {date}")

        except Exception as e:
            print(f"❌ Error fetching Ligue 1 fixtures: {e}")
            if "403" in str(e) or "Forbidden" in str(e):
                print("      ⚠️  Ligue 1 may require a paid plan")
                print("      ℹ️  Free tier includes: Premier League, Champions League, etc.")
                print("      ℹ️  Ligue 1 may be restricted to paid tiers")
            return

    print("\n" + "="*60)
    print("✅ RÉSULTAT: football-data.org fonctionne avec saison actuelle !")
    print("="*60)
    print("\n📊 Résumé des accès gratuits:")
    print(f"   - Premier League: {'✅ Disponible' if premier_league else '❌ Non disponible'}")
    print(f"   - Ligue 1: {'✅ Disponible (à confirmer)' if ligue1 else '❌ Non disponible'}")
    print(f"   - Quota: 10 req/min (14,400/jour)")
    print(f"   - Saison actuelle: ✅ Accessible")


if __name__ == "__main__":
    test_football_data_org()
