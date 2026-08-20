#!/usr/bin/env python3
"""
Populate the `cities` table with a small set of cities.

Usage:
  - Set DB via DATABASE_URL (preferred) or PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE.
  - Run: python populate_cities.py

This script inserts the following cities if they do not already exist (by name):
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

CITIES = [
    {"name": "Tallinn, Estonia", "latitude": 59.437000, "longitude": 24.753600},
    {"name": "Toulouse, France", "latitude": 43.604500, "longitude": 1.444000},
    {"name": "Paris, France", "latitude": 48.856600, "longitude": 2.352200},
    {"name": "London, UK", "latitude": 51.507400, "longitude": -0.127800},
]


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


def insert_city(conn, city):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO cities (name, latitude, longitude) VALUES (%s, %s, %s) RETURNING id",
            (city["name"], city["latitude"], city["longitude"]),
        )
        new_id = cur.fetchone()[0]
    conn.commit()
    return new_id


def main():
    conn = get_db_conn()
    try:
        ensure_cities_table_exists(conn)
        for c in CITIES:
            name = c["name"]
            if city_exists(conn, name):
                log.info("City already exists, skipping: %s", name)
                continue
            new_id = insert_city(conn, c)
            log.info("Inserted city %s with id=%s", name, new_id)
    except Exception:
        log.exception("Error while populating cities")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
