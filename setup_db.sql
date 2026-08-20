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

-- Create the 'temperature_data' table
CREATE TABLE temperature_data (
    id SERIAL PRIMARY KEY,
    city_id INTEGER NOT NULL,
    day DATE NOT NULL,
    daily_max DECIMAL(5, 2),
    daily_min DECIMAL(5, 2),
    FOREIGN KEY (city_id) REFERENCES cities(id),
    UNIQUE(city_id, day)
);
