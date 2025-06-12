import requests
import json
import datetime
import time
import os

# Trakt API credentials
TRAKT_CLIENT_ID = "<YOURS>"
TRAKT_CLIENT_SECRET = "<YOURS>"
TRAKT_API_URL = "https://api.trakt.tv"
TRAKT_TOKEN_FILE = "C:\\Users\\danaramapyjama\\scripts\\trakt\\trakt_token.json"


def load_json_token(filename):
    if not os.path.exists(filename):
        return None
    with open(filename, "r") as f:
        return json.load(f)

def save_json_token(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

def generate_device_code():
    url = f"{TRAKT_API_URL}/oauth/device/code"
    payload = {
        "client_id": TRAKT_CLIENT_ID
    }
    r = requests.post(url, json=payload)
    if r.status_code != 200:
        print("Failed to get device code:", r.status_code, r.text)
        return None
    return r.json()

def get_token(device_code):
    url = f"{TRAKT_API_URL}/oauth/device/token"
    payload = {
        "code": device_code,
        "client_id": TRAKT_CLIENT_ID,
        "client_secret": TRAKT_CLIENT_SECRET
    }
    while True:
        r = requests.post(url, json=payload)
        if r.status_code == 200:
            token_data = r.json()
            # Add expires_at timestamp (current time + expires_in seconds)
            now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
            token_data["expires_at"] = now_ts + token_data.get("expires_in", 0)
            return token_data
        elif r.status_code == 400:
            # Authorization pending, keep polling
            time.sleep(3)
        else:
            print("Failed to get token:", r.status_code, r.text)
            return None

def refresh_trakt_token():
    token_data = load_json_token(TRAKT_TOKEN_FILE)
    now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()

    if not token_data:
        # No token saved, start manual auth
        print(" No Trakt token found. Starting manual device authentication...")
        device_info = generate_device_code()
        if not device_info:
            return None
        print(f"\n1. Go to: {device_info['verification_url']}")
        print(f"2. Enter this code: {device_info['user_code']}")
        input("\n3. Press Enter after you have authorized the app...")
        token_data = get_token(device_info["device_code"])
        if token_data:
            save_json_token(TRAKT_TOKEN_FILE, token_data)
        return token_data

    # Token exists, check expiration
    if token_data.get("expires_at", 0) < now_ts:
        print(" Trakt token expired. Attempting to refresh token...")
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
            new_token["expires_at"] = now_ts + new_token["expires_in"]
            save_json_token(TRAKT_TOKEN_FILE, new_token)
            print("Trakt token refreshed successfully.")
            return new_token
        else:
            print(f"Failed to refresh token: {response.status_code} {response.text}")
            # fallback to manual auth
            print("Starting manual device authentication as fallback...")
            device_info = generate_device_code()
            if not device_info:
                return None
            print(f"\n1. Go to: {device_info['verification_url']}")
            print(f"2. Enter this code: {device_info['user_code']}")
            input("\n3. Press Enter after you have authorized the app...")
            token_data = get_token(device_info["device_code"])
            if token_data:
                save_json_token(TRAKT_TOKEN_FILE, token_data)
            return token_data

    # Token still valid
    return token_data

def main():
    token = refresh_trakt_token()
    if not token:
        print("Failed to authenticate with Trakt.")
        return

    # Example: Make an authenticated request to Trakt
    headers = {
        "Authorization": f"Bearer {token['access_token']}",
        "trakt-api-version": "2",
        "trakt-api-key": TRAKT_CLIENT_ID
    }
    r = requests.get(f"{TRAKT_API_URL}/users/me", headers=headers)
    if r.status_code == 200:
        user = r.json()
        print(f"Hello, {user['username']}!")
    else:
        print("Failed to get user info:", r.status_code, r.text)

if __name__ == "__main__":
    main()
