import os
from flask import Flask, request, jsonify, redirect, url_for, session, g
from flask_cors import CORS
from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow
import requests
import json
import traceback

# Import your functions from the backend module
# Ensure the 'backend' folder is in the same directory as main.py
# and contains __init__.py and matches.py
try:
    from backend import matches
except ImportError as e:
    print(f"Error importing 'matches' module from 'backend': {e}")
    print("Ensure 'backend' folder exists, contains '__init__.py', and 'matches.py'")
    # You might want to exit or raise the error depending on requirements
    matches = None # Set to None so later checks fail gracefully

# --- App Initialization ---
load_dotenv()
app = Flask(__name__)
CORS(app, supports_credentials=True) # supports_credentials=True allows cookies to be sent/received
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'default-secret-key-please-change')
if app.config['SECRET_KEY'] == 'default-secret-key-please-change':
    print("Warning: FLASK_SECRET_KEY is not set. Using default (unsafe) key.")


# --- Google OAuth Setup ---
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")

if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    print("Error: Google Client ID or Secret not found in environment variables.")
    # Exit or raise error in a real app if critical
    client_secrets = {} # Prevent further errors if credentials missing
else:
    client_secrets = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [
                "http://localhost:5000/callback/google", # For local testing
                # Add deployed URI later, e.g., "https://your-app.elasticbeanstalk.com/callback/google"
                ],
            "javascript_origins": [
                "http://localhost:5173" # Your Vite frontend URL
                # Add deployed frontend URL later
                ]
        }
    }
SCOPES = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']

# --- API Endpoint ---
@app.route("/api/analyze", methods=['POST'])
def analyze_games():
    # Check if user info is in session
    if not session.get('logged_in'):
        return jsonify({"error": "Login required"}), 401

    if not matches: # Check if import failed
        return jsonify({"error": "Analysis module not loaded"}), 500

    user_email = session.get('user_email', 'Unknown User')
    print(f"Analyze request received for user: {user_email}")

    data = request.json
    username_from_request = data.get('username')
    if not username_from_request:
        return jsonify({"error": "Username is required in request body"}), 400

    print(f"Analyzing games for username (from request): {username_from_request}")

    try:
        stockfish_path = os.environ.get("STOCKFISH_PATH")
        if not stockfish_path:
             print("Warning: STOCKFISH_PATH environment variable not set. Trying default 'stockfish'.")
             # Use a path relative to main.py or an absolute path
             # Adjust this default based on your stockfish location
             stockfish_path = os.path.join(os.path.dirname(__file__), "stockfish", "stockfish-windows-x86-64-avx2.exe") # Example path
             if not os.path.exists(stockfish_path):
                 print(f"Error: Default stockfish path does not exist: {stockfish_path}")
                 # Try a system-wide path if available
                 stockfish_path = "stockfish"


        # Fetch games
        games_data = matches.get_player_matches(username_from_request, 2023, 1) # Example year/month
        if not games_data or not games_data.get('games'):
            return jsonify({"message": f"Could not fetch games for {username_from_request}. Check username and API availability."}), 404

        # Parse the first game
        first_game_pgn = games_data['games'][0].get('pgn')
        game = matches.pgn_parse(first_game_pgn)
        if not game:
            return jsonify({"error": "Failed to parse the first game PGN."}), 500

        # --- THIS IS THE FIX ---
        # Call the correct function name and pass the engine path
        results = matches.stockfish_analyze_game(game, stockfish_path)
        # --- END OF FIX ---

        if results is None:
             # Function returns None if engine path invalid or analysis fails internally
             return jsonify({"error": "Failed to analyze game with Stockfish. Check engine path and game validity. See server logs for details."}), 500

        return jsonify(results)

    except Exception as e:
        print(f"Error during analysis for {username_from_request}: {e}")
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred during analysis."}), 500

# --- Google Login Route ---
@app.route('/login/google')
def google_login():
    if not client_secrets or not client_secrets["web"]["client_id"] or not client_secrets["web"]["client_secret"]:
         return jsonify({"error": "Server configuration error: Google credentials missing or invalid"}), 500

    try:
        flow = Flow.from_client_config(
            client_config=client_secrets,
            scopes=SCOPES,
            redirect_uri=url_for('google_callback', _external=True) # _external=True ensures absolute URL
        )
        authorization_url, state = flow.authorization_url(
            access_type='offline',    # Request refresh token
            include_granted_scopes='true', # Include scopes user previously granted
            # prompt='consent' # Optional: Force consent screen every time
        )
        session['state'] = state # Store state in Flask session for CSRF check
        print(f"Redirecting to Google: {authorization_url}")
        return redirect(authorization_url)
    except Exception as e:
        print(f"Error creating Google Auth flow: {e}")
        traceback.print_exc()
        return jsonify({"error": "Server configuration error during Google login setup"}), 500


# --- Google Callback Route ---
@app.route('/callback/google')
def google_callback():
    state = session.get('state')
    print(f"Callback received. State from session: {state}, State from Google: {request.args.get('state')}")

    # CSRF Protection
    if not state or state != request.args.get('state'):
        print("Error: State mismatch.")
        # Clear potentially compromised session state
        session.pop('state', None)
        return redirect(f'http://localhost:5173/login?error=state_mismatch')

    # Handle user denying access on Google's page
    if 'error' in request.args:
        print(f"User denied access: {request.args['error']}")
        session.pop('state', None) # Clear state
        return redirect(f'http://localhost:5173/login?error=access_denied')

    # Check server config again
    if not client_secrets or not client_secrets["web"]["client_id"] or not client_secrets["web"]["client_secret"]:
         print("Error: Server configuration error: Google credentials missing during callback.")
         session.pop('state', None) # Clear state
         return redirect(f'http://localhost:5173/login?error=server_config')

    try:
        flow = Flow.from_client_config(
            client_config=client_secrets,
            scopes=SCOPES,
            state=state, # Pass state back for validation
            redirect_uri=url_for('google_callback', _external=True)
        )

        # Exchange the authorization code for tokens
        authorization_response = request.url
        # Fix for http vs https behind proxies if needed later:
        # if not authorization_response.startswith('https://') and 'localhost' not in authorization_response:
        #    authorization_response = 'https://' + authorization_response[len('http://'):]

        flow.fetch_token(authorization_response=authorization_response)
        credentials = flow.credentials # Contains access_token, refresh_token, etc.
        print("Successfully fetched tokens.")

        # Get user info using the access token
        userinfo_response = requests.get(
            'https://openidconnect.googleapis.com/v1/userinfo',
            headers={'Authorization': f'Bearer {credentials.token}'}
        )

        userinfo_response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        user_info = userinfo_response.json()
        google_id = user_info.get('sub') # 'sub' is the standard field for unique ID
        email = user_info.get('email')
        name = user_info.get('name')

        if not google_id:
             print("Error: 'sub' (Google ID) not found in user info response.")
             raise ValueError("Google ID not found in user info")

        print(f"User Info from Google: ID={google_id}, Email={email}, Name={name}")

        # --- Store user info directly in the Flask session ---
        session['google_id'] = google_id
        session['user_name'] = name
        session['user_email'] = email
        session['logged_in'] = True # Set flag

        # State is no longer needed after successful token exchange
        session.pop('state', None)

        print("User data stored in session. Redirecting to frontend dashboard.")
        # Redirect to your frontend dashboard page
        return redirect('http://localhost:5173/dashboard')

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error fetching user info: {http_err}")
        print(f"Response Body: {userinfo_response.text if 'userinfo_response' in locals() else 'N/A'}")
        traceback.print_exc()
        session.pop('state', None) # Clear state on error
        return redirect(f'http://localhost:5173/login?error=userinfo_fetch_failed')
    except Exception as e:
        print(f"Error during Google callback processing: {e}")
        traceback.print_exc()
        session.pop('state', None) # Clear state on error
        return redirect(f'http://localhost:5173/login?error=oauth_processing_failed')

# --- Login Status Check ---
@app.route('/api/user/status')
def user_status():
    if session.get('logged_in'):
        return jsonify({
            "logged_in": True,
            "user_info": {
                "google_id": session.get('google_id'),
                "name": session.get('user_name'),
                "email": session.get('user_email')
            }
        })
    else:
        return jsonify({"logged_in": False})

# --- Logout Route ---
@app.route('/logout')
def logout():
    session.clear() # Clear all data from the session
    print("User logged out (session cleared).")
    # Redirect back to the frontend homepage (or login page)
    return redirect('http://localhost:5173/')


# --- Run the server ---
if __name__ == "__main__":
    # Ensure OAUTHLIB_INSECURE_TRANSPORT is set for local HTTP testing
    if os.environ.get("OAUTHLIB_INSECURE_TRANSPORT") != "1" and not os.environ.get("WERKZEUG_RUN_MAIN"):
         print("\nWarning: Running locally over HTTP without OAUTHLIB_INSECURE_TRANSPORT=1 set.")
         print("OAuth flow might fail. Set the environment variable if needed for testing.\n")

    app.run(port=5000, debug=True)

