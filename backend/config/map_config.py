import os

from dotenv import load_dotenv

load_dotenv()

# Geocoding: turns a listing's address into coordinates.
# Base URL of the geocoding service. Any Nominatim-compatible provider works; the public
# server is fine for light use (max 1 request/second, identifying User-Agent, cache results).
GEOCODER_URL = os.getenv("GEOCODER_URL", "https://nominatim.openstreetmap.org").rstrip("/")

# Sent as the `key` query parameter when set. Leave empty for the public Nominatim server.
GEOCODER_API_KEY = os.getenv("GEOCODER_API_KEY", "")

# Address autocomplete: suggestions while the user types. It is a separate service from the
# geocoder, because the public Nominatim server forbids search-as-you-type. The request format
# is Geoapify's (`text`, `filter`, `apiKey`, a `results` list); the default URL is theirs.
# Without AUTOCOMPLETE_API_KEY autocomplete is switched off.
AUTOCOMPLETE_URL = os.getenv(
    "AUTOCOMPLETE_URL", "https://api.geoapify.com/v1/geocode/autocomplete"
).rstrip("/")
AUTOCOMPLETE_API_KEY = os.getenv("AUTOCOMPLETE_API_KEY", "")

# Nominatim rejects requests that do not identify the application.
MAP_USER_AGENT = os.getenv("MAP_USER_AGENT", "CampusNest/1.0")

# Comma-separated ISO 3166-1 alpha-2 codes that limit where addresses are searched.
MAP_COUNTRY_CODES = os.getenv("MAP_COUNTRY_CODES", "us")
