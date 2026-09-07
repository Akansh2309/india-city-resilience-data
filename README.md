<h1 align="center">
  FloodSafe India 🇮🇳
</h1>

<p align="center">
  <strong>AI-powered dual prediction for Flash Floods and Landslides using live, hyperlocal meteorological and topographic data.</strong>
</p>

<p align="center">
  <a href="https://india-city-resilience-data.onrender.com"><strong>🔴 LIVE DEMO</strong></a>
</p>

---

## 🌟 Overview

FloodSafe India is a comprehensive disaster prediction web application designed to keep communities safe. By combining Machine Learning with real-time satellite data, the application predicts the risk of both **Flash Floods** and **Landslides** within a 10km radius of the user's current location.

The platform features a highly immersive, cinematic user interface that dynamically reacts to the environment and the predictions.

## ✨ Key Features

- 📍 **Hyperlocal Live Tracking:** Uses browser Geolocation and Nominatim to accurately pinpoint your city and elevation.
- 🌦️ **15-Parameter Atmospheric Analysis:** Fetches deep weather data (Temperature, Wind Gusts, Cloud Cover, Solar Radiation, Precipitation, etc.) via the Open-Meteo API.
- 🤖 **Machine Learning Flood Prediction:** Utilizes a pre-trained `scikit-learn` Random Forest model to calculate flood probability based on current atmospheric conditions.
- ⛰️ **Heuristic Landslide Intelligence:** Analyzes live elevation and heavy precipitation data to warn users in mountainous or hilly terrains about impending landslides.
- 🎬 **Cinematic UI/UX:** Features dynamic HTML5 background videos that crossfade based on the predicted disaster (Rain, Flood, or Landslide) with clean, glassmorphic design elements.

## 🚀 Live Demo

You can test the application live here:  
**[👉 india-city-resilience-data.onrender.com](https://india-city-resilience-data.onrender.com)**

## 💻 Tech Stack

- **Frontend:** HTML5, CSS3 (Glassmorphism), Vanilla JavaScript, FontAwesome
- **Backend:** Python, Flask, Gunicorn
- **Machine Learning:** `scikit-learn`, `pandas`, `joblib`
- **APIs:** 
  - Open-Meteo API (Live Weather & Elevation)
  - Nominatim API (Reverse Geocoding)
- **Deployment:** Render

## 🛠️ Local Installation

If you want to run this project locally on your machine:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Akansh2309/india-city-resilience-data.git
   cd india-city-resilience-data
   ```

2. **Install the dependencies:**
   Make sure you have Python installed, then run:
   ```bash
   pip install -r ml_models/requirements.txt
   ```

3. **Run the Flask application:**
   ```bash
   python ml_models/app.py
   ```

4. **Open in Browser:**
   Navigate to `http://localhost:5000` in your web browser.

## 📁 Repository Structure

```
.
├── ml_models
│   ├── app.py                     # Main Flask backend application
│   ├── flash_flood_model.joblib   # Trained Machine Learning Model
│   ├── requirements.txt           # Python dependencies
│   └── templates
│       └── index.html             # Immersive Cinematic Frontend
└── README.md                      # Project documentation
```

## ⚠️ Disclaimer
*This application is a predictive tool and should not replace official government or meteorological warnings. Always follow local emergency services' instructions during a disaster.*
