import requests
import pandas as pd
from geopy.geocoders import Nominatim
from tqdm import tqdm
import time
import os

# --- 1. CONFIGURATION ---
# We are pulling 14 years (2010-2024) of hourly data for major Indian cities.
START_DATE = "2010-01-01"
END_DATE = "2024-01-01"
CSV_FILENAME = "india_resilience_data.csv"

# 50 Indian Cities
INDIAN_CITIES = [
    "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Ahmedabad", "Chennai",
    "Kolkata", "Surat", "Pune", "Jaipur", "Lucknow", "Kanpur", "Nagpur",
    "Indore", "Thane", "Bhopal", "Visakhapatnam", "Pimpri-Chinchwad",
    "Patna", "Vadodara", "Ghaziabad", "Ludhiana", "Agra", "Nashik",
    "Faridabad", "Meerut", "Rajkot", "Kalyan-Dombivli", "Vasai-Virar",
    "Varanasi", "Srinagar", "Aurangabad", "Dhanbad", "Amritsar",
    "Navi Mumbai", "Allahabad", "Howrah", "Ranchi", "Gwalior", "Jabalpur",
    "Coimbatore", "Vijayawada", "Jodhpur", "Madurai", "Raipur", "Kota",
    "Guwahati", "Chandigarh", "Solapur", "Hubli-Dharwad"
]

# --- 2. GEOCODING FUNCTION ---
def get_coordinates(city_name):
    geolocator = Nominatim(user_agent="india_climate_research")
    try:
        location = geolocator.geocode(f"{city_name}, India")
        if location:
            return location.latitude, location.longitude
        return None, None
    except Exception as e:
        return None, None

# --- 3. DATA FETCHING FUNCTION ---
def fetch_weather_and_aqi(city, lat, lon):
    weather_url = "https://archive-api.open-meteo.com/v1/archive"
    weather_params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,surface_pressure,cloud_cover,direct_radiation,diffuse_radiation,soil_temperature_0_to_7cm,soil_moisture_0_to_7cm",
        "timezone": "Asia/Kolkata"
    }

    aqi_url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    aqi_params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "hourly": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,aerosol_optical_depth,dust,uv_index",
        "timezone": "Asia/Kolkata"
    }

    try:
        # Fetch Weather (Must succeed)
        weather_res = requests.get(weather_url, params=weather_params).json()
        if "error" in weather_res:
            return None
            
        time_len = len(weather_res["hourly"]["time"])
        
        # Fetch AQI (Graceful fallback if historical data is unavailable for this city/date)
        aqi_res = requests.get(aqi_url, params=aqi_params).json()
        
        if "error" in aqi_res or "hourly" not in aqi_res:
            aqi_hourly = {} # Fill with None later
        else:
            aqi_hourly = aqi_res["hourly"]

        # Safely extract variables
        def get_aqi_var(var_name):
            if var_name in aqi_hourly:
                return aqi_hourly[var_name]
            return [None] * time_len

        df = pd.DataFrame({
            "datetime": weather_res["hourly"]["time"],
            "city": city,
            "latitude": lat,
            "longitude": lon,
            "temperature_c": weather_res["hourly"]["temperature_2m"],
            "humidity_pct": weather_res["hourly"]["relative_humidity_2m"],
            "precipitation_mm": weather_res["hourly"]["precipitation"],
            "wind_speed_kmh": weather_res["hourly"]["wind_speed_10m"],
            "surface_pressure_hpa": weather_res["hourly"]["surface_pressure"],
            "cloud_cover_pct": weather_res["hourly"]["cloud_cover"],
            "direct_radiation_w_m2": weather_res["hourly"]["direct_radiation"],
            "diffuse_radiation_w_m2": weather_res["hourly"]["diffuse_radiation"],
            "soil_temperature_c": weather_res["hourly"]["soil_temperature_0_to_7cm"],
            "soil_moisture_m3_m3": weather_res["hourly"]["soil_moisture_0_to_7cm"],
            "pm10_ug_m3": get_aqi_var("pm10"),
            "pm25_ug_m3": get_aqi_var("pm2_5"),
            "carbon_monoxide_ug_m3": get_aqi_var("carbon_monoxide"),
            "nitrogen_dioxide_ug_m3": get_aqi_var("nitrogen_dioxide"),
            "sulphur_dioxide_ug_m3": get_aqi_var("sulphur_dioxide"),
            "ozone_ug_m3": get_aqi_var("ozone"),
            "aerosol_optical_depth": get_aqi_var("aerosol_optical_depth"),
            "dust_ug_m3": get_aqi_var("dust"),
            "uv_index": get_aqi_var("uv_index")
        })
        
        return df

    except Exception as e:
        print(f"API Request failed for {city}: {e}")
        return None

# --- 4. MAIN PIPELINE ---
def run_pipeline():
    print(f"Starting Data Engineering Pipeline...")
    print(f"Targeting {len(INDIAN_CITIES)} cities from {START_DATE} to {END_DATE}")
    
    if os.path.exists(CSV_FILENAME):
        os.remove(CSV_FILENAME)
        
    total_rows_inserted = 0

    for city in tqdm(INDIAN_CITIES, desc="Processing Cities"):
        lat, lon = get_coordinates(city)
        if lat is None:
            continue
            
        df = fetch_weather_and_aqi(city, lat, lon)
        
        if df is not None:
            # Drop rows where everything is null
            df = df.dropna(subset=["temperature_c", "precipitation_mm"], how="all")
            
            write_header = not os.path.exists(CSV_FILENAME)
            df.to_csv(CSV_FILENAME, mode='a', index=False, header=write_header)
            
            total_rows_inserted += len(df)
            
        time.sleep(1)
        
    print("\n" + "="*50)
    print("PIPELINE COMPLETE.")
    print(f"Total Rows Inserted: {total_rows_inserted:,}")
    print(f"Data saved to: {CSV_FILENAME}")
    print("="*50)

if __name__ == "__main__":
    run_pipeline()
