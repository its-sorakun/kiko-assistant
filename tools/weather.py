import os
import urllib.request
import urllib.parse
import json
from datetime import datetime
from dotenv import load_dotenv
from .permissions_handle import get_location_permission_status

# load environment variables natively to keep mechanisms visible and simple
load_dotenv()
API_KEY = os.getenv("OMAP_API_KEY")

def get_location() -> dict:
    """
    Fetches the current geographic location based on IP address to bypass hardcoded coordinates.
    Relies on standard ip-api for unauthenticated geo-lookups.
    Returns a dictionary containing 'city', 'lat', and 'lon'.
    """
    # Enforce Windows-level permission checks before attempting IP geolocation
    if not get_location_permission_status():
        return {"error": "CRITICAL SYSTEM ERROR: WINDOWS LOCATION PERMISSION IS CURRENTLY DENIED. DO NOT GUESS THE WEATHER. YOU MUST ASK THE USER FOR PERMISSION TO TURN ON LOCATION, OR ASK FOR A CITY NAME."}
        
    try:
        # User-Agent is explicitly required by ip-api to avoid blocks
        req = urllib.request.Request("http://ip-api.com/json/", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            if "city" in data and "lat" in data and "lon" in data:
                return {
                    "city": data["city"],
                    "lat": data["lat"],
                    "lon": data["lon"]
                }
            else:
                return {"error": "Could not determine exact location coordinates from IP."}
    except Exception as e:
        # Avoid hardcoding fallbacks. Pass the failure forward.
        return {"error": f"IP Geolocation failed: {str(e)}"}

def _build_weather_url(endpoint: str, city_name: str = None) -> tuple:
    """Helper to construct the OWM API URL based on city name or native coordinates."""
    if city_name:
        encoded_city = urllib.parse.quote(city_name)
        url = f"https://api.openweathermap.org/data/2.5/{endpoint}?q={encoded_city}&appid={API_KEY}&units=metric"
        return url, city_name
    else:
        loc = get_location()
        if "error" in loc:
            return None, loc["error"]
        
        lat = loc["lat"]
        lon = loc["lon"]
        url = f"https://api.openweathermap.org/data/2.5/{endpoint}?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
        return url, loc["city"]

def get_current_weather(city_name: str = None) -> str:
    """
    Retrieves the real-time current weather data. Call this tool whenever the user asks for the current temperature, weather conditions, or climate.
    If city_name is omitted, Kiko uses native location tracking (if OS permissions allow).
    """
    print("   [☁️ Kiko is looking into the current weather...]")
    url, context = _build_weather_url("weather", city_name)
    if not url: return context # Returns error string (like LOCATION_PERMISSION_OFF)
    
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            
            temp = data["main"].get("temp")
            feels_like = data["main"].get("feels_like")
            humidity = data["main"].get("humidity")
            visibility = data.get("visibility", 0) / 1000 # convert meters to km for readability
            wind_speed = data["wind"].get("speed")
            desc = data["weather"][0].get("description")
            
            return (f"Current Weather in {context}:\n"
                    f"Condition: {desc}\n"
                    f"Temperature: {temp}°C (Feels like {feels_like}°C)\n"
                    f"Humidity: {humidity}%\n"
                    f"Wind Speed: {wind_speed} m/s\n"
                    f"Visibility: {visibility} km\n"
                    f"(Note: UV index and exact chance of rain require premium API access)")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return f"Failed to find weather for '{context}'. Please check the city name."
        return f"HTTP Error fetching weather: {e.code}"
    except Exception as e:
        return f"Failed to fetch current weather: {str(e)}"

def get_hourly_forcast(city_name: str = None) -> str:
    """
    Retrieves the weather forecast for the next 5 hours.
    (Because the free OWM API returns 3-hour steps, this returns the next 2 blocks covering 6 hours).
    If city_name is omitted, it uses native location tracking.
    """
    print("   [🕒 Kiko is looking at the hourly forecast...]")
    url, context = _build_weather_url("forecast", city_name)
    if not url: return context
    
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            forecast_list = data.get("list", [])
            
            # extract the first 2 array blocks (next 6 hours)
            result = f"Hourly Forecast (3-hour steps) in {context}:\n"
            for item in forecast_list[:2]:
                dt = datetime.fromtimestamp(item["dt"]).strftime('%Y-%m-%d %H:%M:%S')
                temp = item["main"].get("temp")
                desc = item["weather"][0].get("description")
                pop = item.get("pop", 0) * 100 # Probability of precipitation is given as 0 to 1
                result += f"- At {dt}: {temp}°C, {desc}, Chance of rain: {pop:.0f}%\n"
            
            return result
    except Exception as e:
        return f"Failed to fetch hourly forecast: {str(e)}"

def get_weekly_forcast(city_name: str = None) -> str:
    """
    Retrieves the daily weather forecast for the upcoming week.
    (OpenWeatherMap free tier only returns up to 5 days natively).
    If city_name is omitted, it uses native location tracking.
    """
    print("   [📅 Kiko is looking at the weekly forecast...]")
    url, context = _build_weather_url("forecast", city_name)
    if not url: return context
    
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            forecast_list = data.get("list", [])
            
            # mechanically group the 3-hour steps into days to synthesize a weekly overview
            daily_forecast = {}
            for item in forecast_list:
                dt = datetime.fromtimestamp(item["dt"])
                day_str = dt.strftime('%A, %Y-%m-%d')
                
                if day_str not in daily_forecast:
                    daily_forecast[day_str] = {
                        "temps": [],
                        "desc": item["weather"][0].get("description")
                    }
                daily_forecast[day_str]["temps"].append(item["main"].get("temp"))
            
            result = f"5-Day Forecast for {context} (Free API limit):\n"
            for day, info in daily_forecast.items():
                temps = info["temps"]
                avg_temp = sum(temps) / len(temps)
                max_temp = max(temps)
                min_temp = min(temps)
                result += f"- {day}: Avg {avg_temp:.1f}°C (Min: {min_temp}°C, Max: {max_temp}°C), {info['desc']}\n"
                
            return result
    except Exception as e:
        return f"Failed to fetch weekly forecast: {str(e)}"
