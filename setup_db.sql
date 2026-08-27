-- Create the database
CREATE DATABASE weather_data;

-- Connect to the database (run this separately in psql)
\c weather_data;

-- Create the 'cities' table
CREATE TABLE cities (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    latitude DECIMAL(10, 6) NOT NULL,
    longitude DECIMAL(10, 6) NOT NULL
);

-- Create the 'daily_weather' table (stores more than temperature)
-- Units: temperatures in °C, precipitation in millimeters, sunshine in seconds
CREATE TABLE daily_weather (
    id SERIAL PRIMARY KEY,
    city_id INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    day DATE NOT NULL,

    -- temperature (°C)
    daily_max DECIMAL(5,2),
    daily_min DECIMAL(5,2),

    -- precipitation (millimeters)
    rain_sum DECIMAL(7,2),
    snowfall_sum DECIMAL(7,2),

    -- apparent temperatures (°C)
    apparent_temperature_max DECIMAL(5,2),
    apparent_temperature_min DECIMAL(5,2),

    -- sunshine duration in seconds (as provided by your API)
    sunshine_duration_seconds INTEGER,

    -- creation timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),

    -- uniqueness per city/day
    UNIQUE (city_id, day)
);

-- Non-negative checks for applicable fields
ALTER TABLE daily_weather
  ADD CONSTRAINT chk_daily_weather_rain_nonneg CHECK (rain_sum IS NULL OR rain_sum >= 0),
  ADD CONSTRAINT chk_daily_weather_snow_nonneg CHECK (snowfall_sum IS NULL OR snowfall_sum >= 0),
  ADD CONSTRAINT chk_daily_weather_sun_nonneg CHECK (sunshine_duration_seconds IS NULL OR sunshine_duration_seconds >= 0);

-- Index to speed up queries by date
CREATE INDEX IF NOT EXISTS idx_daily_weather_day ON daily_weather(day);

-- Optional backfill from the existing temperature_data table (uncomment and run if you want to copy old rows)
-- BEGIN;
-- INSERT INTO daily_weather (city_id, day, daily_max, daily_min, created_at)
-- SELECT city_id, day, daily_max, daily_min, now() FROM temperature_data
--   ON CONFLICT (city_id, day) DO NOTHING;
-- COMMIT;
