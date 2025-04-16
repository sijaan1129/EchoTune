import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
from dotenv import load_dotenv

load_dotenv()

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET")
))

def get_spotify_track(url):
    try:
        track = sp.track(url)
        artist = track['artists'][0]['name']
        name = track['name']
        return f"{artist} - {name}"
    except Exception as e:
        print(f"Error getting Spotify track: {e}")
        return url
