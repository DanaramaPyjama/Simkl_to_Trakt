# trakt_auth
This script will look for a JSON auth token.  If it does not exist, it will get you a device code, and give you a link to authenticate.  This should only need to be done once.

"No Trakt token found. Starting manual device authentication...

1. Go to: https://trakt.tv/activate
2. Enter this code: xxxxxxx

3. Press Enter after you have authorized the app..."

This will save trakt_token.json

Existing, expired tokens will be refreshed automatically when the script runs.
Script is written for Windows (See path and escape chars)

Success test:

"Hello, <Trakt username>!"


# Simkl_to_Trakt
This script is actually broken, I think it is an older version of the one I used in production.
