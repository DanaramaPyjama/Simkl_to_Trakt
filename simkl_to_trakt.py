import requests
import json
import datetime
import webbrowser

# Simkl API credentials
SIMKL_CLIENT_ID = "<yours>"
SIMKL_API_URL = "https://api.simkl.com"
SIMKL_TOKEN_FILE = "/path/to/trakt/simkl_token.json"

# Trakt API credentials
TRAKT_CLIENT_ID = "<yours>"
TRAKT_CLIENT_SECRET = "<yours>"
TRAKT_API_URL = "https://api.trakt.tv"
TRAKT_TOKEN_FILE = "/path/to/scripts/trakt/trakt_token.json"
# Output files
FULL_SIMKL_OUTPUT = "full_simkl_output.json"
FILTERED_OUTPUT_FILE = "simkl_output.txt"
DEBUG_LOG_FILE = "debug_log.txt"

def log_debug(message):
    """Write debug messages to a file instead of printing."""
    with open(DEBUG_LOG_FILE, "a", encoding="utf-8") as log_file:
        log_file.write(message + "\n")

def load_json_token(file_path):
    """Load API tokens from a JSON file."""
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def save_json_token(file_path, token_data):
    """Save API tokens to a JSON file."""
    with open(file_path, "w") as f:
        json.dump(token_data, f, indent=4)

def refresh_trakt_token():
    """Refresh the Trakt API token if expired."""
    token_data = load_json_token(TRAKT_TOKEN_FILE)
    if not token_data:
        print("Trakt token missing. Authenticate first.")
        return None

    expires_at = token_data.get("expires_at")
    if expires_at is None or datetime.datetime.now(datetime.timezone.utc).timestamp() >= expires_at:
        print("Trakt token expired or missing expiration. Refreshing...")
        url = f"{TRAKT_API_URL}/oauth/token"
        payload = {
            "refresh_token": token_data.get("refresh_token"),
            "client_id": TRAKT_CLIENT_ID,
            "client_secret": TRAKT_CLIENT_SECRET,
            "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
            "grant_type": "refresh_token"
        }
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            new_token = response.json()
            new_token["expires_at"] = datetime.datetime.now(datetime.timezone.utc).timestamp() + new_token["expires_in"]
            save_json_token(TRAKT_TOKEN_FILE, new_token)
            print("Trakt token refreshed successfully.")
            return new_token["access_token"]
        else:
            print(f"Failed to refresh Trakt token: {response.status_code} - {response.text}")
            return None
    return token_data.get("access_token")

def get_last_12_hours_iso():
    """Get the timestamp for 12 hours ago in ISO 8601 format."""
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=12)).isoformat()

def get_trakt_episode_id(show_ids, season, episode):
    """Fetch the correct Trakt episode ID based on season and episode number."""
    trakt_slug = show_ids.get("traktslug")
    if not trakt_slug:
        return None

    url = f"{TRAKT_API_URL}/shows/{trakt_slug}/seasons/{season}/episodes/{episode}"
    headers = {
        "Authorization": f"Bearer {load_json_token(TRAKT_TOKEN_FILE)['access_token']}",
        "trakt-api-key": TRAKT_CLIENT_ID,
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        episode_data = response.json()
        return episode_data.get("ids", {}).get("trakt")  # Return the Trakt episode ID
    
    log_debug(f"Failed to fetch Trakt episode ID for {trakt_slug} S{season}E{episode}: {response.status_code}")
    return None

def fetch_simkl_watch_history(token, date_from):
    """Fetch Simkl watch history, filtered by date."""
    url = f"{SIMKL_API_URL}/sync/all-items/?extended=full&episode_watched_at=yes&date_from={date_from}"
    headers = {
        "Authorization": f"Bearer {token}",
        "simkl-api-key": SIMKL_CLIENT_ID,
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        
        with open(FULL_SIMKL_OUTPUT, "w") as f:
            json.dump(data, f, indent=4)

        cutoff_time = get_last_12_hours_iso()
        log_debug(f"Filtering for items watched after: {cutoff_time}")

        watched_items = {"movies": [], "episodes": []}

        for movie in data.get("movies", []):
            last_watched_at = movie.get("last_watched_at")
            if last_watched_at and last_watched_at >= cutoff_time:
                watched_items["movies"].append({
                    "watched_at": last_watched_at,
                    "title": movie["movie"]["title"],
                    "year": movie["movie"]["year"],
                    "ids": movie["movie"]["ids"]
                })

        for show in data.get("shows", []):
            for season in show.get("seasons", []):
                for episode in season.get("episodes", []):
                    last_watched_at = episode.get("watched_at")
                    season_num = season.get("number")
                    episode_num = episode.get("number")

                    if last_watched_at and last_watched_at >= cutoff_time:
                        trakt_episode_id = get_trakt_episode_id(show["show"]["ids"], season_num, episode_num)
                        if trakt_episode_id:
                            watched_items["episodes"].append({
                                "watched_at": last_watched_at,
                                "ids": {"trakt": trakt_episode_id}
                            })

        with open(FILTERED_OUTPUT_FILE, "w") as f:
            json.dump(watched_items, f, indent=4)

        log_debug("Episodes After Filtering:")
        log_debug(json.dumps(watched_items["episodes"], indent=4))
        
        return watched_items
    
    log_debug(f"Failed to fetch Simkl watch history: {response.status_code} - {response.text}")
    return None

def sync_to_trakt(trakt_token, watched_items):
    """Sync filtered watch history from Simkl to Trakt."""
    url = f"{TRAKT_API_URL}/sync/history"
    headers = {
        "Authorization": f"Bearer {trakt_token}",
        "trakt-api-key": TRAKT_CLIENT_ID,
        "Content-Type": "application/json"
    }

    payload = {"movies": watched_items["movies"], "episodes": watched_items["episodes"]}

    if not payload["movies"] and not payload["episodes"]:
        print("No movies or episodes to sync. Skipping Trakt update.")
        return

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code in [200, 201]:
        print("Successfully synced to Trakt!")
    else:
        log_debug(f"Failed to sync to Trakt: {response.status_code} - {response.text}")

def main():
    """Main function to fetch Simkl history and sync to Trakt."""
    simkl_token = load_json_token(SIMKL_TOKEN_FILE)
    trakt_token = refresh_trakt_token()

    if not simkl_token or not trakt_token:
        print("Missing API tokens. Authenticate first.")
        return

    print("Using saved API tokens.")
    print("Syncing Simkl to Trakt...")

    history = fetch_simkl_watch_history(simkl_token["access_token"], get_last_12_hours_iso())
    if history:
        sync_to_trakt(trakt_token, history)

if __name__ == "__main__":
    main()
