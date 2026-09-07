from flask import Flask, request, jsonify, render_template
import requests
import joblib
import pandas as pd
import os

app = Flask(__name__)

# Load the model
# For Render deployment, the root might be ml_models or the parent.
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

    # 1. Fetch Weather from Open-Meteo
    weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m,shortwave_radiation"
    
    try:
        w_res = requests.get(weather_url, timeout=5)
        w_res.raise_for_status()
        w_data = w_res.json()
        current = w_data.get('current', {})
        
        # Mapping to model features
        temp = current.get('temperature_2m', 25.0)
        humidity = current.get('relative_humidity_2m', 60.0)
        wind = current.get('wind_speed_10m', 10.0)
        pressure_hpa = current.get('surface_pressure', 1013.0)
        solar = current.get('shortwave_radiation', 200.0)
        
        # Conversion
        pressure_kpa = pressure_hpa / 10.0
        
    except Exception as e:
        return jsonify({"error": f"Failed to fetch weather data: {str(e)}"}), 502

    # 2. Fetch Location Name from Nominatim (OpenStreetMap)
    # Important: Nominatim requires a User-Agent
    headers = {
        'User-Agent': 'FloodSafe-India-App/1.0 (Contact: admin@floodsafe.in)'
    }
    loc_url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
    location_name = ""
    try:
        l_res = requests.get(loc_url, headers=headers, timeout=5)
        if l_res.ok:
            l_data = l_res.json()
            address = l_data.get('address', {})
            # Try to get the most relevant local name
            city = address.get('city') or address.get('town') or address.get('village') or address.get('county')
            state = address.get('state', '')
            if city:
                location_name = f"{city}, {state}".strip(", ")
            else:
                location_name = l_data.get('display_name', '').split(',')[0]
    except Exception as e:
        # Failsafe, don't crash the prediction if geocoding fails
        location_name = f"Lat: {lat:.4f}, Lon: {lon:.4f}"

    if not location_name:
         location_name = f"Lat: {lat:.4f}, Lon: {lon:.4f}"

    # 3. Predict using the ML Model
    try:
        input_df = pd.DataFrame({
            'temperature_c': [temp],
            'humidity_pct': [humidity],
            'wind_speed_kmh': [wind],
            'surface_pressure_kpa': [pressure_kpa],
            'solar_radiation_w_m2': [solar]
        })
        
        prediction = int(model.predict(input_df)[0])
        probability = float(model.predict_proba(input_df)[0][1]) * 100
        
    except Exception as e:
        return jsonify({"error": f"Model prediction failed: {str(e)}"}), 500

    # 4. Return results
    return jsonify({
        "latitude": lat,
        "longitude": lon,
        "location_name": location_name,
        "weather": {
            "temperature_c": temp,
            "humidity_pct": humidity,
            "wind_speed_kmh": wind,
            "surface_pressure_kpa": pressure_kpa,
            "solar_radiation_w_m2": solar
        },
        "prediction": prediction,
        "probability": probability
    })

if __name__ == '__main__':
    # Used only for local development
    app.run(debug=True, host='0.0.0.0', port=5000)
