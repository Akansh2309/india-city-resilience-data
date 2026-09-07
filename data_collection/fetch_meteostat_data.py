import pandas as pd
from meteostat import hourly, Point, config
from datetime import datetime
from geopy.geocoders import Nominatim
from tqdm import tqdm
import time
import os

# --- 1. CONFIGURATION ---
# Because Open-Meteo rate-limited us, we are upgrading to Meteostat.
# Meteostat uses decentralized CDN bulk downloads, meaning ZERO API rate limits!
# To hit 800MB+, we are going massive: 100 Indian Cities over 24 years (2000-2024).
START_DATE = datetime(2000, 1, 1)
END_DATE = datetime(2024, 1, 1)
CSV_FILENAME = "india_resilience_data_meteostat.csv"

# Bypass the 3-year safety block to allow massive 24-year data pulls
config.block_large_requests = False

# 100 Indian Cities (Tier 1, Tier 2, and Tier 3)
INDIAN_CITIES = [
    "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Ahmedabad", "Chennai",
    "Kolkata", "Surat", "Pune", "Jaipur", "Lucknow", "Kanpur", "Nagpur",
    "Indore", "Thane", "Bhopal", "Visakhapatnam", "Pimpri-Chinchwad",
    "Patna", "Vadodara", "Ghaziabad", "Ludhiana", "Agra", "Nashik",
    "Faridabad", "Meerut", "Rajkot", "Kalyan-Dombivli", "Vasai-Virar",
    "Varanasi", "Srinagar", "Aurangabad", "Dhanbad", "Amritsar",
    "Navi Mumbai", "Allahabad", "Howrah", "Ranchi", "Gwalior", "Jabalpur",
    "Coimbatore", "Vijayawada", "Jodhpur", "Madurai", "Raipur", "Kota",
    "Guwahati", "Chandigarh", "Solapur", "Hubli-Dharwad", "Bareilly",
    "Moradabad", "Mysore", "Gurgaon", "Aligarh", "Jalandhar", "Tiruchirappalli",
    "Bhubaneswar", "Salem", "Mira-Bhayandar", "Warangal", "Thiruvananthapuram",
    "Guntur", "Bhiwandi", "Bikaner", "Amravati", "Noida", "Jamshedpur",
    "Bhilai", "Cuttack", "Firozabad", "Kochi", "Nellore", "Bhavnagar",
    "Dehradun", "Durgapur", "Asansol", "Rourkela", "Nanded", "Kolhapur",
    "Ajmer", "Akola", "Gulbarga", "Jamnagar", "Ujjain", "Loni", "Siliguri",
    "Jhansi", "Ulhasnagar", "Jammu", "Sangli-Miraj-Kupwad", "Mangalore",
    "Erode", "Belgaum", "Ambattur", "Tirunelveli", "Malegaon", "Gaya",
    "Jalgaon", "Udaipur", "Maheshtala"
]

def get_coordinates(city_name):
    geolocator = Nominatim(user_agent="india_climate_research")
    try:
        location = geolocator.geocode(f"{city_name}, India")
        if location:
            return location.latitude, location.longitude
        return None, None
    except Exception as e:
        return None, None

def run_pipeline():
    print(f"Starting V2 Meteostat Data Engineering Pipeline...")
    print(f"Targeting {len(INDIAN_CITIES)} cities from {START_DATE.year} to {END_DATE.year}")
    
    if os.path.exists(CSV_FILENAME):
        os.remove(CSV_FILENAME)
        
    total_rows = 0

    for city in tqdm(INDIAN_CITIES, desc="Processing Cities"):
        lat, lon = get_coordinates(city)
        if lat is None:
            continue
            
        try:
            # Fetch 24 years of hourly data (approx 210,000 rows per city)
            point = Point(lat, lon)
            data = hourly(point, START_DATE, END_DATE)
            df = data.fetch()
            
            if not df.empty:
                # Format dataframe
                df = df.reset_index()
                df.insert(0, 'city', city)
                df.insert(1, 'latitude', lat)
                df.insert(2, 'longitude', lon)
                
                # Drop fully empty rows
                df = df.dropna(subset=['temp', 'prcp'], how='all')
                
                write_header = not os.path.exists(CSV_FILENAME)
                df.to_csv(CSV_FILENAME, mode='a', index=False, header=write_header)
                total_rows += len(df)
        except Exception as e:
            print(f"Failed to fetch {city}: {e}")
            
        time.sleep(1) # Be polite to Geopy
        
    print("\n" + "="*50)
    print("PIPELINE COMPLETE.")
    print(f"Total Rows Inserted: {total_rows:,}")
    print(f"Data saved to: {CSV_FILENAME}")
    print("="*50)

if __name__ == "__main__":
    run_pipeline()
