-- Create the database
CREATE DATABASE weather_data;
-- Run this inside psql after connecting to your database (e.g. \c weather_data)

-- Table: daily_weather
-- Units: temperatures in °C, precipitation in millimeters, sunshine in minutes

CREATE TABLE IF NOT EXISTS daily_weather (
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

    -- sunshine duration in minutes
    sunshine_duration_minutes INTEGER,

    -- timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),

    -- uniqueness per city/day
    UNIQUE (city_id, day)
);

-- Non-negative checks for appropriate fields
ALTER TABLE daily_weather
  ADD CONSTRAINT chk_daily_weather_rain_nonneg CHECK (rain_sum IS NULL OR rain_sum >= 0),
  ADD CONSTRAINT chk_daily_weather_snow_nonneg CHECK (snowfall_sum IS NULL OR snowfall_sum >= 0),
  ADD CONSTRAINT chk_daily_weather_sun_nonneg CHECK (sunshine_duration_minutes IS NULL OR sunshine_duration_minutes >= 0);

-- Helpful index if you query by date across cities
CREATE INDEX IF NOT EXISTS idx_daily_weather_day ON daily_weather(day);

-- Optional: Backfill existing temperature_data rows into daily_weather
-- This will copy city_id, day, daily_max, daily_min from temperature_data. Other new columns will remain NULL.
-- Run only once (and inside a transaction if you want rollback on error).
-- Example:
-- BEGIN;
-- INSERT INTO daily_weather (city_id, day, daily_max, daily_min, created_at, updated_at)
-- SELECT city_id, day, daily_max, daily_min, now(), now() FROM temperature_data
--   ON CONFLICT (city_id, day) DO NOTHING;
-- COMMIT;

-- Note:
-- - I used DECIMAL for controlled precision (no floating rounding surprises). If you prefer double precision, replace DECIMAL(...) with DOUBLE PRECISION.
-- - If you prefer sunshine in hours, change sunshine_duration_minutes to DECIMAL(5,2) and store hours instead.
-- - I set ON DELETE CASCADE on the FK so a removed city removes associated daily rows; remove that if you prefer RESTRICT.
