import os
import spotipy
import logging
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

# Suppress annoying spotipy and urllib3 stdout HTTP warnings
logging.getLogger("spotipy").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)

# Ensure environment variables are loaded
load_dotenv()

# Need extensive scopes for playback modification, playlist creation, reading user playlists, and reading user stats.
SCOPE = "user-read-playback-state user-modify-playback-state playlist-modify-private playlist-modify-public user-library-modify playlist-read-private user-top-read"

_sp = None

def get_spotify_client():
    global _sp
    if _sp is None:
        # Use an absolute path for the cache file to prevent CWD confusion
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cache_path = os.path.join(base_dir, ".cache")
        
        _sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=SCOPE, cache_path=cache_path))
    return _sp

def spotify_search_and_play(query: str, search_type: str = "track") -> str:
    """
    Searches Spotify for a track, album, or artist and forces the active device to start playing it.
    """
    print(f"   [🎵 Kiko is searching Spotify for '{query}'...]")
    try:
        sp = get_spotify_client()
        # Perform the search
        results = sp.search(q=query, type=search_type, limit=1)
        
        items = results.get(search_type + "s", {}).get("items", [])
        if not items:
            return f"Spotify couldn't find any {search_type} matching '{query}'."
            
        item = items[0]
        uri = item['uri']
        name = item['name']
        
        # Inject the URI into the active player
        if search_type == "track":
            sp.start_playback(uris=[uri])
        else:
            # For albums/artists/playlists, we use context_uri instead of uris array
            sp.start_playback(context_uri=uri)
            
        return f"Successfully started playing {search_type}: {name}"
    except spotipy.exceptions.SpotifyException as e:
        if e.http_status == 404:
            return "Failed to play. Ensure you have an active Spotify device running (open Spotify on your PC or phone)."
        return f"Spotify API Error: {str(e)}"
    except Exception as e:
        return f"System Error: {str(e)}"

def spotify_transfer_playback(target_device_name: str) -> str:
    """
    Transfers active playback to a specific device (e.g., 'Phone' or 'Desktop').
    """
    print(f"   [🎵 Kiko is transferring Spotify playback to '{target_device_name}'...]")
    try:
        sp = get_spotify_client()
        devices = sp.devices().get('devices', [])
        
        if not devices:
            return "No active Spotify devices found on your network. Please wake up your phone screen or open the desktop app."
            
        for device in devices:
            # Match loosely (e.g. 'phone' in 'Rajat's iPhone')
            if target_device_name.lower() in device['name'].lower() or target_device_name.lower() in device['type'].lower():
                sp.transfer_playback(device_id=device['id'], force_play=True)
                return f"Successfully transferred playback to {device['name']}."
                
        # If exact match fails, just list available devices
        device_names = [d['name'] for d in devices]
        return f"Could not find '{target_device_name}'. Available devices are: {', '.join(device_names)}."
    except Exception as e:
        return f"System Error: {str(e)}"

def spotify_get_devices() -> str:
    """
    Retrieves all available Spotify devices that playback can be transferred to.
    """
    print("   [🎵 Kiko is querying available Spotify devices...]")
    try:
        sp = get_spotify_client()
        devices_response = sp.devices()
        devices = devices_response.get('devices', [])
        
        if not devices:
            return "No active Spotify devices found. Please open Spotify on your PC or Phone."
            
        output = ["Available Spotify Devices:"]
        for d in devices:
            active_str = " (Active)" if d['is_active'] else ""
            output.append(f"- {d['name']} ({d['type']}){active_str}")
        return "\n".join(output)
    except spotipy.exceptions.SpotifyException as e:
        return f"Spotify API Error: {str(e)}"
    except Exception as e:
        return f"System Error: {str(e)}"

def spotify_create_and_fill_playlist(playlist_name: str, seed_genres: list) -> str:
    """
    Creates a new playlist and fills it with recommended tracks based on seed genres.
    """
    print(f"   [🎵 Kiko is generating a new playlist '{playlist_name}'...]")
    try:
        sp = get_spotify_client()
        user_id = sp.me()['id']
        
        # 1. Get recommendations
        recs = sp.recommendations(seed_genres=seed_genres, limit=20)
        track_uris = [track['uri'] for track in recs['tracks']]
        
        if not track_uris:
            return f"Could not generate recommendations for genres: {seed_genres}"
            
        # 2. Create the playlist
        new_playlist = sp.user_playlist_create(user=user_id, name=playlist_name, public=False)
        playlist_id = new_playlist['id']
        
        # 3. Add the tracks
        sp.playlist_add_items(playlist_id=playlist_id, items=track_uris)
        
        # 4. Start playing it!
        sp.start_playback(context_uri=new_playlist['uri'])
        
        return f"Successfully created playlist '{playlist_name}' with {len(track_uris)} tracks and started playback!"
    except spotipy.exceptions.SpotifyException as e:
        return f"Spotify API Error: {str(e)}"
    except Exception as e:
        return f"System Error: {str(e)}"

def spotify_get_queue() -> str:
    """
    Retrieves the user's current playback queue and returns the next few upcoming tracks.
    """
    print("   [🎵 Kiko is retrieving your Spotify queue...]")
    try:
        sp = get_spotify_client()
        queue_data = sp.queue()
        
        currently_playing = queue_data.get('currently_playing')
        queue_items = queue_data.get('queue', [])
        
        if not currently_playing and not queue_items:
            return "Your Spotify queue is completely empty and nothing is currently playing."
            
        output = []
        if currently_playing:
            output.append(f"Currently Playing: {currently_playing.get('name')} by {currently_playing['artists'][0]['name']}")
            
        if queue_items:
            output.append("Up Next in Queue:")
            # Limit to next 5 tracks to prevent massive prompt injections
            for idx, track in enumerate(queue_items[:5]):
                output.append(f" {idx + 1}. {track.get('name')} by {track['artists'][0]['name']}")
                
        return "\n".join(output)
    except spotipy.exceptions.SpotifyException as e:
        return f"Spotify API Error: {str(e)}"
    except Exception as e:
        return f"System Error: {str(e)}"

def spotify_get_user_playlists() -> str:
    """
    Retrieves the user's saved/created playlists.
    """
    print("   [🎵 Kiko is fetching your Spotify playlists...]")
    try:
        sp = get_spotify_client()
        playlists = sp.current_user_playlists(limit=50)
        items = playlists.get('items', [])
        if not items:
            return "You don't have any Spotify playlists saved in your library."
        
        output = ["Your Spotify Playlists:"]
        for p in items:
            track_count = p.get('tracks', {}).get('total', '?')
            output.append(f"- {p['name']} ({track_count} tracks)")
        return "\n".join(output)
    except spotipy.exceptions.SpotifyException as e:
        return f"Spotify API Error: {str(e)}"
    except Exception as e:
        return f"System Error: {str(e)}"

def spotify_play_user_playlist(playlist_name: str) -> str:
    """
    Finds a playlist in the user's library by name and plays it.
    """
    print(f"   [🎵 Kiko is trying to play your playlist '{playlist_name}'...]")
    try:
        sp = get_spotify_client()
        playlists = sp.current_user_playlists(limit=50)
        
        for p in playlists.get('items', []):
            if playlist_name.lower() in p['name'].lower():
                sp.start_playback(context_uri=p['uri'])
                return f"Successfully started playing your playlist: {p['name']}"
                
        return f"Could not find a playlist named '{playlist_name}' in your library."
    except spotipy.exceptions.SpotifyException as e:
        if e.http_status == 404:
            return "Failed to play. Ensure you have an active Spotify device running."
        return f"Spotify API Error: {str(e)}"
    except Exception as e:
        return f"System Error: {str(e)}"

def spotify_get_user_stats(stat_type: str = "tracks", time_range: str = "short_term") -> str:
    """
    Gets the user's top tracks or artists.
    stat_type: 'tracks' or 'artists'
    time_range: 'short_term' (4 weeks), 'medium_term' (6 months), or 'long_term' (all time)
    """
    print(f"   [🎵 Kiko is fetching your Spotify stats ({stat_type}, {time_range})...]")
    try:
        sp = get_spotify_client()
        if stat_type == "artists":
            results = sp.current_user_top_artists(time_range=time_range, limit=10)
            items = results.get('items', [])
            if not items:
                return "Not enough data to calculate top artists."
            output = [f"Your Top 10 Artists ({time_range.replace('_', ' ')}):"]
            for idx, artist in enumerate(items):
                output.append(f"{idx + 1}. {artist['name']}")
            return "\n".join(output)
        else:
            results = sp.current_user_top_tracks(time_range=time_range, limit=10)
            items = results.get('items', [])
            if not items:
                return "Not enough data to calculate top tracks."
            output = [f"Your Top 10 Tracks ({time_range.replace('_', ' ')}):"]
            for idx, track in enumerate(items):
                output.append(f"{idx + 1}. {track['name']} by {track['artists'][0]['name']}")
            return "\n".join(output)
    except spotipy.exceptions.SpotifyException as e:
        return f"Spotify API Error: {str(e)}"
    except Exception as e:
        return f"System Error: {str(e)}"
