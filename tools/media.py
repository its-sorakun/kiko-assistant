# Copyright (C) 2026 Senpai
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# Hooking into the asynchronous Windows Runtime (WinRT) SMTC pipeline instead of faking media keypresses. This allows iterating through all suspended background sessions (like Spotify) and piping transport controls directly to specific applications, bypassing whatever browser happens to dominate the global DWM media session.
import asyncio

def control_system_media(action: str = "info", app_name: str = None) -> str:
    """
    Control or inspect the currently playing system media via WinRT System Media Transport Controls (SMTC).
    Bypasses high-level GUI automation by hooking directly into the Windows OS media pipeline.
    Action can be: 'info', 'play', 'pause', 'next', 'previous'.
    Optional app_name (e.g. 'spotify') targets a specific background application instead of the globally active one.
    """
    try:
        from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
    except ImportError:
        return "The 'winsdk' Python projection for WinRT is missing. Execute 'pip install winsdk'."

    async def _manage_media():
        manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
        
        session = None
        if app_name:
            # Iterate through all available media sessions to find the specific app
            sessions = manager.get_sessions()
            for s in sessions:
                if app_name.lower() in s.source_app_user_model_id.lower():
                    session = s
                    break
            if not session:
                return f"Could not find an active SMTC media session matching '{app_name}'."
        else:
            # Fall back to the dominant/global session
            session = manager.get_current_session()
            
        if not session:
            return "No active media session hooked into the Windows DWM."
            
        target_app = session.source_app_user_model_id
        action_lower = action.lower()
        
        if action_lower == "play":
            await session.try_play_async()
            return f"Sent Play command to {target_app}."
        elif action_lower == "pause":
            await session.try_pause_async()
            return f"Sent Pause command to {target_app}."
        elif action_lower == "next":
            await session.try_skip_next_async()
            return f"Sent Skip Next command to {target_app}."
        elif action_lower == "previous":
            await session.try_skip_previous_async()
            return f"Sent Skip Previous command to {target_app}."
        
        # Default fallback is 'info'
        properties = await session.try_get_media_properties_async()
        title = properties.title
        artist = properties.artist
        return f"Currently playing: '{title}' by {artist} (Host Process: {target_app})"
        
    try:
        return asyncio.run(_manage_media())
    except Exception as e:
        return f"Failed to interface with WinRT SMTC APIs: {e}"
