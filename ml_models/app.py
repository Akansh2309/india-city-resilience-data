from flask import Flask, request, jsonify, render_template
import requests
import joblib
import pandas as pd
import os
import time

app = Flask(__name__)

# --- Caching Mechanism ---
# Prevents the probability from fluctuating due to live API micro-changes
# Keys: "lat_lon" rounded to 2 decimals (~1.1km area)
# Values: (data_dict, timestamp)
PREDICTION_CACHE = {}
CACHE_TTL_SECONDS = 60 # 1 hour

def get_cached_data(lat, lon):
    key = f"{round(lat, 2)}_{round(lon, 2)}"
    if key in PREDICTION_CACHE:
        data, timestamp = PREDICTION_CACHE[key]
        if time.time() - timestamp < CACHE_TTL_SECONDS:
            return data
    return None

def set_cached_data(lat, lon, data):
    key = f"{round(lat, 2)}_{round(lon, 2)}"
    PREDICTION_CACHE[key] = (data, time.time())


# --- Load Model ---
model_path = os.path.join(os.path.dirname(__file__), "flash_flood_model.joblib")
try:
    model = joblib.load(model_path)
except Exception as e:
    print(f"Failed to load model from {model_path}: {e}")
    model = None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    if not model:
        return jsonify({"error": "Model not loaded on server."}), 500

    data = request.get_json()
    lat = data.get('latitude')
    lon = data.get('longitude')

    if lat is None or lon is None:
        return jsonify({"error": "Latitude and longitude required"}), 400

    # 1. Check Cache
    cached_response = get_cached_data(lat, lon)
    if cached_response:
        return jsonify(cached_response)

    # 2. Fetch Extended Weather Data from Open-Meteo
    weather_url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,"
        "precipitation,rain,showers,snowfall,cloud_cover,pressure_msl,surface_pressure,"
        "wind_speed_10m,wind_direction_10m,wind_gusts_10m,shortwave_radiation"
    )
    
    try:
        w_res = requests.get(weather_url, timeout=8)
        w_res.raise_for_status()
        w_data = w_res.json()
        current = w_data.get('current', {})
        units = w_data.get('current_units', {})
        
        # Mapping to core model features
        temp_c = current.get('temperature_2m', 25.0)
        humidity_pct = current.get('relative_humidity_2m', 60.0)
        wind_speed_kmh = current.get('wind_speed_10m', 10.0)
        surface_pressure_hpa = current.get('surface_pressure', 1013.0)
        solar_radiation_w_m2 = current.get('shortwave_radiation', 200.0)
        
        # Convert pressure for model
        surface_pressure_kpa = surface_pressure_hpa / 10.0
        
    except Exception as e:
        return jsonify({"error": f"Failed to fetch weather data: {str(e)}"}), 502

    # 3. Fetch Location Name from Nominatim
    headers = {
        'User-Agent': 'FloodSafe-India-App/1.1 (Contact: admin@floodsafe.in)'
    }
    loc_url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
    location_name = ""
    try:
        l_res = requests.get(loc_url, headers=headers, timeout=5)
        if l_res.ok:
            l_data = l_res.json()
            address = l_data.get('address', {})
            city = address.get('city') or address.get('town') or address.get('village') or address.get('county')
            state = address.get('state', '')
            if city:
                location_name = f"{city}, {state}".strip(", ")
            else:
                location_name = l_data.get('display_name', '').split(',')[0]
    except Exception as e:
        location_name = f"Lat: {lat:.4f}, Lon: {lon:.4f}"

    if not location_name:
         location_name = f"Lat: {lat:.4f}, Lon: {lon:.4f}"

    # 4. Predict using the ML Model
    try:
        input_df = pd.DataFrame({
            'temperature_c': [temp_c],
            'humidity_pct': [humidity_pct],
            'wind_speed_kmh': [wind_speed_kmh],
            'surface_pressure_kpa': [surface_pressure_kpa],
            'solar_radiation_w_m2': [solar_radiation_w_m2]
        })
        
        prediction = int(model.predict(input_df)[0])
        probability = float(model.predict_proba(input_df)[0][1]) * 100
        
    except Exception as e:
        return jsonify({"error": f"Model prediction failed: {str(e)}"}), 500

    # 5. Build Final Response Object
    response_data = {
        "latitude": lat,
        "longitude": lon,
        "location_name": location_name,
        "prediction": prediction,
        "probability": probability,
        "elaborative": {
            "Temperature": f"{temp_c} {units.get('temperature_2m', '°C')}",
            "Feels Like": f"{current.get('apparent_temperature', '--')} {units.get('apparent_temperature', '°C')}",
            "Relative Humidity": f"{humidity_pct} {units.get('relative_humidity_2m', '%')}",
            "Precipitation": f"{current.get('precipitation', '--')} {units.get('precipitation', 'mm')}",
            "Rain": f"{current.get('rain', '--')} {units.get('rain', 'mm')}",
            "Showers": f"{current.get('showers', '--')} {units.get('showers', 'mm')}",
            "Snowfall": f"{current.get('snowfall', '--')} {units.get('snowfall', 'cm')}",
            "Cloud Cover": f"{current.get('cloud_cover', '--')} {units.get('cloud_cover', '%')}",
            "Mean Sea Level Pressure": f"{current.get('pressure_msl', '--')} {units.get('pressure_msl', 'hPa')}",
            "Surface Pressure": f"{surface_pressure_hpa} {units.get('surface_pressure', 'hPa')}",
            "Wind Speed": f"{wind_speed_kmh} {units.get('wind_speed_10m', 'km/h')}",
            "Wind Direction": f"{current.get('wind_direction_10m', '--')} {units.get('wind_direction_10m', '°')}",
            "Wind Gusts": f"{current.get('wind_gusts_10m', '--')} {units.get('wind_gusts_10m', 'km/h')}",
            "Solar Radiation": f"{solar_radiation_w_m2} {units.get('shortwave_radiation', 'W/m²')}",
            "Time of Day": "Day" if current.get('is_day') == 1 else "Night"
        }
    }

    # Save to cache to prevent fluctuation "fault"
    set_cached_data(lat, lon, response_data)

    return jsonify(response_data)

import concurrent.futures

def fetch_weather_for_town(town):
    """Helper to fetch weather and predict risk for a single town."""
    lat = town.get('lat')
    lon = town.get('lon')
    name = town.get('tags', {}).get('name', 'Unknown')
    
    weather_url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,surface_pressure,shortwave_radiation"
    )
    
    try:
        w_res = requests.get(weather_url, timeout=5)
        if w_res.status_code != 200:
            return None
        current = w_res.json().get('current', {})
        
        input_data = {
            "T2M": current.get('temperature_2m', 25.0),
            "RH2M": current.get('relative_humidity_2m', 60.0),
            "WS10M": current.get('wind_speed_10m', 10.0),
            "PS": current.get('surface_pressure', 1013.0) / 10.0,
            "ALLSKY_SFC_SW_DWN": current.get('shortwave_radiation', 200.0)
        }
        input_df = pd.DataFrame([input_data])
        
        if model:
            prob = float(model.predict_proba(input_df)[0][1]) * 100
        else:
            prob = 0.0
            
        return {
            "name": name,
            "lat": lat,
            "lon": lon,
            "risk_probability": round(prob, 2),
            "safe": prob < 50.0
        }
    except Exception:
        return None

@app.route('/nearby_advisory', methods=['POST'])
def nearby_advisory():
    data = request.get_json()
    lat = data.get('latitude')
    lon = data.get('longitude')
    
    if lat is None or lon is None:
        return jsonify({"error": "Latitude and longitude required"}), 400

    # 1. Fetch nearby towns (within ~50km radius) using Nominatim Bounding Box Search
    # Nominatim viewbox format: left,top,right,bottom (lon_min, lat_max, lon_max, lat_min)
    lat_f = float(lat)
    lon_f = float(lon)
    # Approx 50km is 0.45 degrees
    delta = 0.45
    viewbox = f"{lon_f - delta},{lat_f + delta},{lon_f + delta},{lat_f - delta}"
    
    nominatim_url = f"https://nominatim.openstreetmap.org/search?q=[town]&format=json&limit=15&viewbox={viewbox}&bounded=1"
    
    elements = []
    try:
        nom_res = requests.get(nominatim_url, headers={'User-Agent': 'FloodSafe-App/1.0'}, timeout=10)
        if nom_res.status_code == 200:
            data = nom_res.json()
            for item in data:
                # Format to match existing downstream logic
                elements.append({
                    'lat': float(item.get('lat')),
                    'lon': float(item.get('lon')),
                    'tags': {'name': item.get('name') or item.get('display_name', '').split(',')[0]}
                })
        else:
            return jsonify({"error": f"Nominatim API failed with status {nom_res.status_code}"}), 502
    except Exception as e:
        return jsonify({"error": f"Nominatim API failed: {str(e)}"}), 502
        
    # Deduplicate by name just in case
    seen_names = set()
    unique_towns = []
    for el in elements:
        name = el.get('tags', {}).get('name')
        if name and name not in seen_names:
            seen_names.add(name)
            unique_towns.append(el)
            
    # We don't want to query too many, limit to 8
    unique_towns = unique_towns[:8]

    # 2. Concurrently fetch weather and predict risk
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_weather_for_town, town) for town in unique_towns]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                results.append(res)
                
    # 3. Separate into Safe and Restricted
    safe_zones = [r for r in results if r['safe']]
    restricted_zones = [r for r in results if not r['safe']]
    
    # Sort by risk (lowest risk first for safe, highest risk first for restricted)
    safe_zones.sort(key=lambda x: x['risk_probability'])
    restricted_zones.sort(key=lambda x: x['risk_probability'], reverse=True)

    return jsonify({
        "safe_zones": safe_zones,
        "restricted_zones": restricted_zones
    })

@app.route('/historical_rainfall', methods=['POST'])
def historical_rainfall():
    data = request.get_json()
    lat = data.get('latitude')
    lon = data.get('longitude')
    
    if lat is None or lon is None:
        return jsonify({"error": "Latitude and longitude required"}), 400
        
    # Open-Meteo provides past_days=7 natively in the forecast endpoint!
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=precipitation_sum&past_days=7&forecast_days=1&timezone=auto"
    
    try:
        res = requests.get(url, timeout=5)
        res.raise_for_status()
        data = res.json().get('daily', {})
        
        # Open-Meteo returns 'time' and 'precipitation_sum' arrays
        times = data.get('time', [])
        precip = data.get('precipitation_sum', [])
        
        # We only want the past 7 days (exclude today/tomorrow if they are at the end)
        return jsonify({
            "labels": times[:7],
            "data": precip[:7]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
