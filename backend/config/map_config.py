import os

from dotenv import load_dotenv

load_dotenv()

# Base URL of the geocoding service. Any Nominatim-compatible provider works; the public
# server is fine for light use (max 1 request/second, identifying User-Agent, cache results).
MAP_URL = os.getenv("MAP_URL", "https://nominatim.openstreetmap.org").rstrip("/")

# Sent as the `key` query parameter when set. Leave empty for the public Nominatim server.
# It is also the key for address autocomplete below, which needs a Geoapify key.
GEOCODER_API_KEY = os.getenv("GEOCODER_API_KEY", "")

# Address autocomplete (suggestions while typing). The public Nominatim server forbids this,
# so it uses Geoapify's autocomplete API with GEOCODER_API_KEY. Without a key it is switched off.
AUTOCOMPLETE_URL = os.getenv(
    "AUTOCOMPLETE_URL", "https://api.geoapify.com/v1/geocode/autocomplete"
).rstrip("/")

# Nominatim rejects requests that do not identify the application.
MAP_USER_AGENT = os.getenv("MAP_USER_AGENT", "CampusNest/1.0")

# Comma-separated ISO 3166-1 alpha-2 codes that limit where addresses are searched.
MAP_COUNTRY_CODES = os.getenv("MAP_COUNTRY_CODES", "us")
