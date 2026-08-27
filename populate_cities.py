#!/usr/bin/env python3


"""
Populate the `cities` table with a small set of cities.

Usage:
  - Set DB via DATABASE_URL (preferred) or PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE.
  - Run: python populate_cities.py

This script automatically retrieves latitude/longitude for each city using
Nominatim (OpenStreetMap geocoding).

Cities to populate:
  - Tallinn, Estonia
  - Toulouse, France
  - Paris, France
  - London, UK

It performs an existence check by name to avoid creating duplicates.
"""

import os
import logging
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

CITIES = [
    {"city": "Tallinn", "country": "Estonia"},
    {"city": "Toulouse", "country": "France"},
    {"city": "Paris", "country": "France"},
    {"city": "London", "country": "UK"},
]


def get_db_conn():
    # Load environment variables from .env
    load_dotenv()
  
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url)
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", ""),
        dbname=os.getenv("PGDATABASE", "weather_data"),
    )


def get_coordinates(city, country):
    """
    Retrieve latitude and longitude for a city using Nominatim geocoding.
    
    Args:
        city: City name (e.g., "Paris")
        country: Country name (e.g., "France")
    
    Returns:
        Tuple of (latitude, longitude) or None if geocoding fails
    """
    try:
        geolocator = Nominatim(user_agent="weather_app")
        location = geolocator.geocode(f"{city}, {country}")
        if location:
            return (location.latitude, location.longitude)
        else:
            log.warning("Could not geocode: %s, %s", city, country)
            return None
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        log.error("Geocoding service error for %s, %s: %s", city, country, e)
        return None


def ensure_cities_table_exists(conn):
    # In case the table wasn't created, we don't want the script to fail silently.
    create_sql = """
    CREATE TABLE IF NOT EXISTS cities (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        latitude DECIMAL(10,6) NOT NULL,
        longitude DECIMAL(10,6) NOT NULL
    );
    """
    with conn.cursor() as cur:
        cur.execute(create_sql)
    conn.commit()


def city_exists(conn, name):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM cities WHERE name = %s LIMIT 1", (name,))
        return cur.fetchone() is not None


def insert_city(conn, city_name, latitude, longitude):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO cities (name, latitude, longitude) VALUES (%s, %s, %s) RETURNING id",
            (city_name, latitude, longitude),
        )
        new_id = cur.fetchone()[0]
    conn.commit()
    return new_id


def main():
    conn = get_db_conn()
    try:
        ensure_cities_table_exists(conn)
        for city_info in CITIES:
            city = city_info["city"]
            country = city_info["country"]
            full_name = f"{city}, {country}"
            
            if city_exists(conn, full_name):
                log.info("City already exists, skipping: %s", full_name)
                continue
            
            # Retrieve coordinates
            coords = get_coordinates(city, country)
            if coords is None:
                log.error("Skipping %s - could not retrieve coordinates", full_name)
                continue
            
            latitude, longitude = coords
            new_id = insert_city(conn, full_name, latitude, longitude)
            log.info("Inserted city %s (lat=%s, lon=%s) with id=%s", 
                     full_name, latitude, longitude, new_id)
    except Exception:
        log.exception("Error while populating cities")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
