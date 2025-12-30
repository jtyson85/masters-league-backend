"""
Master's League Fantasy Football Backend
Fetches ESPN data and serves to React dashboard
"""
from flask import Flask, jsonify
from flask_cors import CORS
from espn_api.football import League
import json
from pathlib import Path

app = Flask(__name__)
CORS(app)

# === CONFIGURATION ===
import os

LEAGUE_ID = int(os.environ.get('LEAGUE_ID', 123456))  # Your ESPN league ID
YEAR = 2025
ESPN_S2 = os.environ.get('ESPN_S2', '')   # Your espn_s2 cookie (for private leagues)
SWID = os.environ.get('SWID', '')     # Your SWID cookie (for private leagues)
REGULAR_SEASON_WEEKS = 13

# Pre-defined second H2H schedule - edit this at season start
# Format: {week: [[team1_id, team2_id], ...]}
# Team IDs match ESPN's team IDs (1-10 typically)
SCHEDULE_FILE = "schedule.json"

def load_schedule():
    """Load the pre-defined H2H schedule from JSON file."""
    path = Path(SCHEDULE_FILE)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    # Default 10-team round robin if no file exists
    return {
        "1": [[1,2],[3,4],[5,6],[7,8],[9,10]],
        "2": [[1,3],[2,5],[4,7],[6,9],[8,10]],
        "3": [[1,4],[2,6],[3,8],[5,9],[7,10]],
        "4": [[1,5],[2,7],[3,9],[4,6],[8,10]],
        "5": [[1,6],[2,8],[3,10],[4,5],[7,9]],
        "6": [[1,7],[2,9],[3,5],[4,8],[6,10]],
        "7": [[1,8],[2,10],[3,6],[4,9],[5,7]],
        "8": [[1,9],[2,4],[3,7],[5,10],[6,8]],
        "9": [[1,10],[2,3],[4,10],[5,8],[6,7]],
        "10": [[1,2],[3,4],[5,6],[7,8],[9,10]],
        "11": [[1,3],[2,5],[4,7],[6,9],[8,10]],
        "12": [[1,4],[2,6],[3,8],[5,9],[7,10]],
        "13": [[1,5],[2,7],[3,9],[4,6],[8,10]],
    }

def save_schedule(schedule):
    """Save schedule to JSON file."""
    with open(SCHEDULE_FILE, 'w') as f:
        json.dump(schedule, f, indent=2)

def get_league():
    """Connect to ESPN league."""
    if ESPN_S2 and SWID:
        return League(league_id=LEAGUE_ID, year=YEAR, espn_s2=ESPN_S2, swid=SWID)
    return League(league_id=LEAGUE_ID, year=YEAR)

def get_teams(league):
    """Get all teams in the league."""
    teams = []
    for team in league.teams:
        # Owner might be in 'owners' list or not available
        if hasattr(team, 'owners') and team.owners:
            owner = team.owners[0] if isinstance(team.owners, list) else team.owners
        elif hasattr(team, 'owner'):
            owner = team.owner
        else:
            owner = "Unknown"
        
        teams.append({
            "id": team.team_id,
            "name": team.team_name,
            "abbrev": team.team_abbrev,
            "owner": owner,
        })
    return teams

def get_weekly_data(league, week):
    """Get scores and ESPN matchups for a specific week."""
    scores = {}
    espn_matchups = []
    
    for box in league.box_scores(week):
        home_id = box.home_team.team_id
        away_id = box.away_team.team_id
        scores[home_id] = box.home_score
        scores[away_id] = box.away_score
        espn_matchups.append([home_id, away_id])
    
    return {
        "week": week,
        "scores": scores,
        "espnMatchups": espn_matchups,
    }

def get_all_weekly_data(league):
    """Get all weekly data up to current week."""
    current_week = min(league.current_week, REGULAR_SEASON_WEEKS)
    weeks = []
    for week in range(1, current_week + 1):
        try:
            week_data = get_weekly_data(league, week)
            if any(score > 0 for score in week_data["scores"].values()):
                weeks.append(week_data)
        except Exception as e:
            print(f"Error fetching week {week}: {e}")
    return weeks

@app.route('/api/league')
def league_info():
    """Get full league data for dashboard."""
    try:
        league = get_league()
        schedule = load_schedule()
        
        return jsonify({
            "leagueName": "Master's League",
            "year": YEAR,
            "regularSeasonWeeks": REGULAR_SEASON_WEEKS,
            "currentWeek": min(league.current_week, REGULAR_SEASON_WEEKS),
            "teams": get_teams(league),
            "weeks": get_all_weekly_data(league),
            "schedule": schedule,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/week/<int:week>')
def week_data(week):
    """Get data for a specific week."""
    try:
        league = get_league()
        return jsonify(get_weekly_data(league, week))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/schedule', methods=['GET'])
def get_schedule():
    """Get the pre-defined H2H schedule."""
    return jsonify(load_schedule())

@app.route('/api/schedule', methods=['POST'])
def update_schedule():
    """Update the pre-defined H2H schedule."""
    from flask import request
    schedule = request.json
    save_schedule(schedule)
    return jsonify({"status": "saved", "schedule": schedule})

@app.route('/api/refresh')
def refresh_data():
    """Force refresh data from ESPN."""
    try:
        league = get_league()
        return jsonify({
            "status": "refreshed",
            "currentWeek": league.current_week,
            "teams": len(league.teams),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === SCHEDULE GENERATOR UTILITIES ===
def generate_round_robin(team_ids, weeks=13):
    """
    Generate a round-robin schedule for the second H2H matchup.
    Each team plays every other team at least once.
    """
    n = len(team_ids)
    schedule = {}
    
    # Circle method for round-robin
    teams = team_ids.copy()
    if n % 2 == 1:
        teams.append(None)  # Bye
    
    n = len(teams)
    for week in range(1, weeks + 1):
        round_idx = (week - 1) % (n - 1)
        rotated = [teams[0]] + teams[1:][-(round_idx):] + teams[1:][:-(round_idx)] if round_idx else teams
        
        matchups = []
        for i in range(n // 2):
            t1, t2 = rotated[i], rotated[n - 1 - i]
            if t1 is not None and t2 is not None:
                matchups.append([t1, t2])
        
        schedule[str(week)] = matchups
    
    return schedule

@app.route('/api/schedule/generate')
def generate_schedule():
    """Generate a new round-robin schedule based on current teams."""
    try:
        league = get_league()
        team_ids = [t.team_id for t in league.teams]
        schedule = generate_round_robin(team_ids, REGULAR_SEASON_WEEKS)
        return jsonify(schedule)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Master's League Backend")
    print(f"League ID: {LEAGUE_ID}")
    print(f"Year: {YEAR}")
    print("-" * 40)
    
    # Test connection on startup
    try:
        league = get_league()
        print(f"Connected to: {league.settings.name}")
        print(f"Teams: {len(league.teams)}")
        print(f"Current Week: {league.current_week}")
    except Exception as e:
        print(f"Warning: Could not connect to ESPN: {e}")
        print("Update LEAGUE_ID, ESPN_S2, and SWID in config")
    
    print("-" * 40)
    print("Starting server on http://localhost:5000")
    app.run(debug=True, port=5000)