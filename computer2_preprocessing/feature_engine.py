"""
SkyGuard — Feature Engine (Computer 2)
========================================
Extract and compute features from raw ADS-B flight data.
Migrated from modules/feature_engine.py.
Adapted for batch processing (Spark-compatible).
"""

import logging
from shared.config.airspace import (
    is_near_airport,
    is_in_restricted_zone,
    calculate_distance_km,
)

logger = logging.getLogger("skyguard.preprocessing")


class FeatureEngine:
    """Stateful feature extraction — tracks per-flight history."""

    def __init__(self):
        self.flight_history = {}

    def extract_features(self, flight_data):
        """
        Extract features from a single raw flight record.

        Args:
            flight_data: dict with raw ADS-B fields

        Returns:
            dict with enriched features
        """
        icao24 = flight_data.get("icao24")

        features = {
            # identity
            "icao24": icao24,
            "callsign": flight_data.get("callsign", "N/A"),
            "origin_country": flight_data.get("origin_country", "Unknown"),
            "latitude": flight_data.get("latitude", 0),
            "longitude": flight_data.get("longitude", 0),
            "on_ground": flight_data.get("on_ground", False),
            "squawk": flight_data.get("squawk"),
            "registration": flight_data.get("registration", ""),
            "aircraft_type": flight_data.get("aircraft_type", ""),
            "aircraft_desc": flight_data.get("aircraft_desc", ""),
            "raw_timestamp": flight_data.get("timestamp"),

            # converted features
            "altitude_feet": flight_data.get("baro_altitude", 0) or 0,
            "speed_knots": (
                flight_data.get("velocity", 0) * 1.94384
                if flight_data.get("velocity") else 0
            ),
            "heading": flight_data.get("true_track", 0) or 0,
            "climb_rate_fpm": (
                flight_data.get("vertical_rate", 0) * 196.85
                if flight_data.get("vertical_rate") else 0
            ),
        }

        # --- Airport proximity ---
        near_airport, airport_code, airport_name = is_near_airport(
            features["latitude"], features["longitude"]
        )
        features["near_airport"] = near_airport
        features["airport_code"] = airport_code
        features["airport_name"] = airport_name

        # --- Restricted zone ---
        in_zone, zone_id, zone_name, risk_mult = is_in_restricted_zone(
            features["latitude"], features["longitude"]
        )
        features["in_restricted_zone"] = in_zone
        features["restricted_zone_id"] = zone_id
        features["restricted_zone_name"] = zone_name
        features["zone_risk_multiplier"] = risk_mult

        # --- Behavioral features (from history) ---
        if icao24 not in self.flight_history:
            self.flight_history[icao24] = []

        self.flight_history[icao24].append({
            "lat": features["latitude"],
            "lon": features["longitude"],
            "alt": features["altitude_feet"],
            "speed": features["speed_knots"],
            "heading": features["heading"],
            "timestamp": features["raw_timestamp"],
        })

        # Keep last 100 positions
        if len(self.flight_history[icao24]) > 100:
            self.flight_history[icao24] = self.flight_history[icao24][-100:]

        if len(self.flight_history[icao24]) >= 2:
            prev = self.flight_history[icao24][-2]
            curr = self.flight_history[icao24][-1]

            # Altitude change
            if prev["alt"] is not None and curr["alt"] is not None:
                features["altitude_change"] = curr["alt"] - prev["alt"]
            else:
                features["altitude_change"] = 0

            # Heading change
            if prev["heading"] is not None and curr["heading"] is not None:
                diff = abs(curr["heading"] - prev["heading"])
                if diff > 180:
                    diff = 360 - diff
                features["heading_change"] = diff
            else:
                features["heading_change"] = 0

            # Distance traveled
            if all(v is not None for v in [prev["lat"], prev["lon"], curr["lat"], curr["lon"]]):
                features["distance_traveled_km"] = calculate_distance_km(
                    prev["lat"], prev["lon"], curr["lat"], curr["lon"]
                )
            else:
                features["distance_traveled_km"] = 0
        else:
            features["altitude_change"] = 0
            features["heading_change"] = 0
            features["distance_traveled_km"] = 0

        return features

    def get_flight_history(self, icao24, limit=10):
        """Get recent positions for a specific flight."""
        return self.flight_history.get(icao24, [])[-limit:]
