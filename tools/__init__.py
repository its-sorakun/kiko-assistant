# Copyright (C) 2026 its-sorakun
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# Aggregating the modular tools here so main.py doesn't have to change import paths. This keeps the flat API surface intact for the LLM tool schemas while separating the underlying mechanics.
from .process import launch_program, force_kill_process
from .telemetry import get_system_stats, get_hardware_details
from .windowing import get_active_window, read_active_window_content, open_directory, list_directory_contents, open_file
from .registry import query_registry_value
from .media import control_system_media
from .power import manage_power_state
from .memory import memorize_preferences, get_all_preferences, recall_semantic_memory
from .search import perform_web_search
from .pdf_rag import advanced_pdf_query
from .job_application_helper import draft_and_copy_job_email
from .clipboard import copy_to_clipboard
from .vision import analyze_screen
from .mft_scanner import perform_global_search
from .weather import get_current_weather, get_hourly_forcast, get_weekly_forcast
from .permissions_handle import toggle_location_permission

__all__ = [
    "launch_program", 
    "get_system_stats", 
    "open_directory", 
    "get_active_window", 
    "get_hardware_details", 
    "query_registry_value", 
    "force_kill_process",
    "read_active_window_content",
    "control_system_media",
    "manage_power_state",
    "memorize_preferences",
    "get_all_preferences",
    "recall_semantic_memory",
    "perform_web_search",
    "list_directory_contents",
    "open_file",
    "advanced_pdf_query",
    "draft_and_copy_job_email",
    "copy_to_clipboard",
    "analyze_screen",
    "perform_global_search",
    "get_current_weather",
    "get_hourly_forcast",
    "get_weekly_forcast",
    "toggle_location_permission"
]
