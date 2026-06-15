"""
SkyGuard — Historical OpenSky Data Fetcher
==========================================
Provides easy-to-use methods for fetching historical or specific data
using the official OpenSky Network python API and TokenManager.

Endpoints implemented:
- GET /flights/arrival
- GET /flights/departure
- GET /flights/aircraft
- GET /tracks
"""

import os
import time
import logging
from opensky_api import OpenSkyApi, TokenManager

logger = logging.getLogger("skyguard.historical")

class HistoricalOpenSky:
    def __init__(self, credentials_path="credentials.json"):
        # Resolve the path from root directory if it's relative
        if not os.path.isabs(credentials_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.cred_path = os.path.join(base_dir, credentials_path)
        else:
            self.cred_path = credentials_path

    def _get_api(self):
        """Helper to get an authenticated API instance."""
        tm = None
        if os.path.exists(self.cred_path):
            try:
                tm = TokenManager.from_json_file(self.cred_path)
            except Exception as e:
                logger.error("Failed to load TokenManager from %s: %s", self.cred_path, e)
        else:
            logger.warning("credentials.json not found at %s. Proceeding unauthenticated.", self.cred_path)
        
        return OpenSkyApi(token_manager=tm) if tm else OpenSkyApi()

    def get_arrivals(self, airport_icao: str, begin_unix: int, end_unix: int):
        """
        GET /flights/arrival
        Retrieve flights arriving at a given airport within a time interval.
        """
        logger.info(f"Fetching arrivals for {airport_icao} from {begin_unix} to {end_unix}")
        with self._get_api() as api:
            return api.get_arrivals_by_airport(airport_icao, begin_unix, end_unix)

    def get_departures(self, airport_icao: str, begin_unix: int, end_unix: int):
        """
        GET /flights/departure
        Retrieve flights departing from a given airport within a time interval.
        """
        logger.info(f"Fetching departures for {airport_icao} from {begin_unix} to {end_unix}")
        with self._get_api() as api:
            return api.get_departures_by_airport(airport_icao, begin_unix, end_unix)

    def get_aircraft_flights(self, icao24: str, begin_unix: int, end_unix: int):
        """
        GET /flights/aircraft
        Retrieve flights for a particular aircraft within a time interval.
        """
        logger.info(f"Fetching flights for aircraft {icao24} from {begin_unix} to {end_unix}")
        with self._get_api() as api:
            return api.get_flights_by_aircraft(icao24, begin_unix, end_unix)

    def get_aircraft_track(self, icao24: str, time_unix: int = 0):
        """
        GET /tracks
        Retrieve the trajectory for a certain aircraft at a given time.
        """
        logger.info(f"Fetching track for aircraft {icao24} around time {time_unix}")
        with self._get_api() as api:
            return api.get_track_by_aircraft(icao24, time_unix)


if __name__ == "__main__":
    # Setup simple logging for testing
    logging.basicConfig(level=logging.INFO)
    
    historical = HistoricalOpenSky()
    
    # Test parameters (last 2 hours)
    end = int(time.time())
    begin = end - (2 * 3600)
    
    # You can test specific endpoints by uncommenting below:
    # print("Arrivals WIII:", historical.get_arrivals("WIII", begin, end))
    # print("Departures WIII:", historical.get_departures("WIII", begin, end))
