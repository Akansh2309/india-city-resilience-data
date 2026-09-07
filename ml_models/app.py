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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
