import requests
import pandas as pd
from geopy.geocoders import Nominatim
from tqdm import tqdm
import time
import os

# --- 1. CONFIGURATION ---
# Because European APIs blocked us with anti-DDoS, we are upgrading to NASA.
# NASA's POWER API provides ultra-precise satellite data with no aggressive IP bans.
# We will pull an additional 10 years of hourly data (2004-2013) to double the size.
YEARS = list(range(2004, 2014))
CSV_FILENAME = "india_resilience_data_nasa.csv"

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

def get_coordinates(city_name):
    geolocator = Nominatim(user_agent="india_climate_nasa_research")
    try:
        location = geolocator.geocode(f"{city_name}, India")
        if location:
            return round(location.latitude, 4), round(location.longitude, 4)
        return None, None
    except:
        return None, None

def fetch_nasa_data_for_year(city, lat, lon, year):
    """Fetches exactly 1 year of hourly data from NASA POWER API."""
    start_date = f"{year}0101"
    end_date = f"{year}1231"
    
    # T2M = Temp, RH2M = Humidity, PRECTOTCORR = Precipitation, WS10M = Wind Speed
    # PS = Surface Pressure, ALLSKY_SFC_SW_DWN = Solar Radiation
    url = f"https://power.larc.nasa.gov/api/temporal/hourly/point?parameters=T2M,RH2M,PRECTOTCORR,WS10M,PS,ALLSKY_SFC_SW_DWN&community=RE&longitude={lon}&latitude={lat}&start={start_date}&end={end_date}&format=JSON"
    
    try:
        res = requests.get(url).json()
        if "properties" not in res:
            return None
            
        params = res["properties"]["parameter"]
        
        # NASA returns dicts where keys are timestamps (e.g., "2014010100")
        timestamps = list(params["T2M"].keys())
        
        df = pd.DataFrame({
            "datetime_utc": timestamps,
            "city": city,
            "latitude": lat,
            "longitude": lon,
            "temperature_c": list(params["T2M"].values()),
            "humidity_pct": list(params["RH2M"].values()),
            "precipitation_mm": list(params["PRECTOTCORR"].values()),
            "wind_speed_kmh": list(params["WS10M"].values()),
            "surface_pressure_kpa": list(params["PS"].values()),
            "solar_radiation_w_m2": list(params["ALLSKY_SFC_SW_DWN"].values())
        })
        
        # NASA uses -999.0 for missing data. Replace with None (NaN)
        df = df.replace(-999.0, pd.NA)
        return df
    except Exception as e:
        print(f"Failed {city} {year}: {e}")
        return None

def run_pipeline():
    print("Starting NASA Satellite Data Engineering Pipeline...")
        
    total_rows = 0

    for city in tqdm(INDIAN_CITIES, desc="Processing Cities"):
        lat, lon = get_coordinates(city)
        if lat is None:
            continue
            
        for year in YEARS:
            df = fetch_nasa_data_for_year(city, lat, lon, year)
            if df is not None and not df.empty:
                write_header = not os.path.exists(CSV_FILENAME)
                df.to_csv(CSV_FILENAME, mode='a', index=False, header=write_header)
                total_rows += len(df)
            
            # Polite delay for NASA's servers
            time.sleep(1)
            
    print("\n" + "="*50)
    print("NASA PIPELINE COMPLETE.")
    print(f"Total Rows Inserted: {total_rows:,}")
    print(f"Data saved to: {CSV_FILENAME}")
    print("="*50)

if __name__ == "__main__":
    run_pipeline()
