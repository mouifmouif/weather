#!/usr/bin/env python3
"""
Fetch daily weather data from Open-Meteo archive and insert into Postgres.

Usage:
  - Set DB via DATABASE_URL (preferred) or PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE.
  - Adjust START_DATE / END_DATE or pass them as command-line args.
  - Run: python fetch_and_insert_weather.py
"""

import os
import sys
import logging
from datetime import datetime, timedelta
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
import requests_cache
from retry_requests import retry
import openmeteo_requests
import json
import pandas as pd

# Config
# Load environment variables from .env
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")  # e.g. "postgres://user:pass@host:port/dbname"
START_DATE = "1970-01-01"
END_DATE = os.getenv("END_DATE", "2026-08-27")
OPENMETEO_URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY_VARS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "apparent_temperature_max",
    "apparent_temperature_min",
    "sunshine_duration",
    "rain_sum",
    "snowfall_sum"
]

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

def get_db_conn():
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

def build_openmeteo_client():
    cache_session = requests_cache.CachedSession(".cache", expire_after=-1)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    return openmeteo_requests.Client(session=retry_session)

def ensure_table(conn):
    """Verify table exists (no creation needed, table already exists)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'daily_weather'
            );
        """)
        exists = cur.fetchone()[0]
        if not exists:
            raise RuntimeError("daily_weather table does not exist. Please create it first.")
    conn.commit()

def get_latest_date_for_city(conn, city_id):
    """
    Get the most recent date we have data for this city.
    Returns the date as a string (YYYY-MM-DD), or None if no data exists.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT MAX(day) FROM daily_weather WHERE city_id = %s;",
            (city_id,)
        )
        result = cur.fetchone()
        latest_date = result[0] if result and result[0] else None
    return latest_date

def fetch_for_city(client, lat, lon, start_date, end_date):
    params = {
        "latitude": float(lat),
        "longitude": float(lon),
        "start_date": start_date,
        "end_date": end_date,
        "daily": DAILY_VARS,
        # optional: timezone="UTC"
    }
    # openmeteo_requests.Client returns a list of response objects
    responses = client.weather_api(OPENMETEO_URL, params=params)
    return responses[0] if responses else None

def parse_daily_entries(response):
    """
    Parse Open-Meteo response object (not JSON dict).
    Returns list of dicts with all daily weather variables.
    """
    if response is None:
        return []
    
    # Get daily data from response object
    daily = response.Daily()
    
    # Extract time series (Variables are indexed in order: 0-6 match DAILY_VARS order)
    daily_temperature_2m_max = daily.Variables(0).ValuesAsNumpy()
    daily_temperature_2m_min = daily.Variables(1).ValuesAsNumpy()
    daily_apparent_temperature_max = daily.Variables(2).ValuesAsNumpy()
    daily_apparent_temperature_min = daily.Variables(3).ValuesAsNumpy()
    daily_sunshine_duration = daily.Variables(4).ValuesAsNumpy()
    daily_rain_sum = daily.Variables(5).ValuesAsNumpy()
    daily_snowfall_sum = daily.Variables(6).ValuesAsNumpy()
    
    # Build date range
    dates = pd.date_range(
        start=pd.to_datetime(daily.Time(), unit="s", utc=True),
        end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
        freq=pd.Timedelta(seconds=daily.Interval()),
        inclusive="left"
    )
    
    log.info("Parsed - times: %d entries, tmax: %d, tmin: %d, apparent_tmax: %d, apparent_tmin: %d, sunshine: %d, rain: %d, snowfall: %d",
             len(dates), len(daily_temperature_2m_max), len(daily_temperature_2m_min), 
             len(daily_apparent_temperature_max), len(daily_apparent_temperature_min),
             len(daily_sunshine_duration), len(daily_rain_sum), len(daily_snowfall_sum))
    
    rows = []
    for i, date in enumerate(dates):
        row = {
            "day": date.strftime("%Y-%m-%d"),
            "daily_max": float(daily_temperature_2m_max[i]) if i < len(daily_temperature_2m_max) else None,
            "daily_min": float(daily_temperature_2m_min[i]) if i < len(daily_temperature_2m_min) else None,
            "apparent_temperature_max": float(daily_apparent_temperature_max[i]) if i < len(daily_apparent_temperature_max) else None,
            "apparent_temperature_min": float(daily_apparent_temperature_min[i]) if i < len(daily_apparent_temperature_min) else None,
            "sunshine_duration_minutes": int(float(daily_sunshine_duration[i])) if i < len(daily_sunshine_duration) else None,
            "rain_sum": float(daily_rain_sum[i]) if i < len(daily_rain_sum) else None,
            "snowfall_sum": float(daily_snowfall_sum[i]) if i < len(daily_snowfall_sum) else None,
        }
        rows.append(row)
    return rows

def upsert_daily_weather(conn, city_id, parsed_rows):
    if not parsed_rows:
        return 0
    sql = """
    INSERT INTO daily_weather (city_id, day, daily_max, daily_min, apparent_temperature_max, apparent_temperature_min, sunshine_duration_minutes, rain_sum, snowfall_sum)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (city_id, day) DO UPDATE
      SET daily_max = EXCLUDED.daily_max,
          daily_min = EXCLUDED.daily_min,
          apparent_temperature_max = EXCLUDED.apparent_temperature_max,
          apparent_temperature_min = EXCLUDED.apparent_temperature_min,
          sunshine_duration_minutes = EXCLUDED.sunshine_duration_minutes,
          rain_sum = EXCLUDED.rain_sum,
          snowfall_sum = EXCLUDED.snowfall_sum,
          updated_at = now();
    """
    params = []
    for r in parsed_rows:
        params.append((
            city_id,
            r["day"],
            r["daily_max"],
            r["daily_min"],
            r["apparent_temperature_max"],
            r["apparent_temperature_min"],
            r["sunshine_duration_minutes"],
            r["rain_sum"],
            r["snowfall_sum"]
        ))
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, params, page_size=100)
        conn.commit()
        return len(params)
    except Exception as e:
        conn.rollback()
        raise

def main():
    client = build_openmeteo_client()
    conn = get_db_conn()

    try:
        ensure_table(conn)
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id, name, latitude, longitude FROM cities;")
            cities = cur.fetchall()
        if not cities:
            log.warning("No cities found in the cities table.")
            return

        total = 0
        for c in cities:
            city_id = c["id"]
            name = c["name"]
            lat = c["latitude"]
            lon = c["longitude"]
            
            # Determine the date range to fetch
            latest_date = get_latest_date_for_city(conn, city_id)
            
            if latest_date:
                # Convert datetime.date to string if needed
                if hasattr(latest_date, 'strftime'):
                    latest_date_str = latest_date.strftime("%Y-%m-%d")
                else:
                    latest_date_str = str(latest_date)
                
                # We have data; fetch from day after latest to END_DATE
                latest = datetime.strptime(latest_date_str, "%Y-%m-%d")
                next_date = (latest + timedelta(days=1)).strftime("%Y-%m-%d")
                fetch_start = next_date
                fetch_end = END_DATE
                log.info("City %s (id=%s) has data up to %s. Fetching from %s to %s", 
                         name, city_id, latest_date_str, fetch_start, fetch_end)
            else:
                # No data; fetch from START_DATE to END_DATE
                fetch_start = START_DATE
                fetch_end = END_DATE
                log.info("City %s (id=%s) has no data. Fetching from %s to %s", 
                         name, city_id, fetch_start, fetch_end)
            
            # Only fetch if there's a date range to cover (use datetime comparison)
            fetch_start_dt = datetime.strptime(fetch_start, "%Y-%m-%d")
            fetch_end_dt = datetime.strptime(fetch_end, "%Y-%m-%d")
            if fetch_start_dt > fetch_end_dt:
                log.info("City %s (id=%s) is already up to date.", name, city_id)
                continue
            
            try:
                response = fetch_for_city(client, lat, lon, fetch_start, fetch_end)
                parsed = parse_daily_entries(response)
                n = upsert_daily_weather(conn, city_id, parsed)
                log.info("Inserted/updated %d rows for city %s", n, name)
                total += n
            except Exception as e:
                log.exception("Failed for city %s: %s", name, e)
        log.info("Done. Total rows inserted/updated: %d", total)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
