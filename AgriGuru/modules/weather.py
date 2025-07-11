import streamlit as st
import requests
import os
import datetime
import pandas as pd
import plotly.express as px

# Ensure TOMORROW_IO_API_KEY is in your .env file and load_dotenv() is called in app.py

# Mapping Tomorrow.io weather codes to icons (example, expand as needed)
# Refer to: https://docs.tomorrow.io/reference/data-layers-weather-codes
WEATHER_CODE_TO_ICON = {
    0: "❓", # Unknown
    1000: "☀️", # Clear, Sunny
    1100: "🌤️", # Mostly Clear
    1101: "⛅",  # Partly Cloudy
    1102: "☁️", # Mostly Cloudy
    1001: "☁️", # Cloudy
    2000: "🌫️", # Fog
    2100: "🌫️", # Light Fog
    4000: "💧", # Drizzle
    4001: "💧", # Light Rain
    4200: "🌧️", # Rain
    4201: "🌧️", # Heavy Rain
    5000: "❄️", # Snow
    5001: "❄️", # Light Snow
    5100: "❄️", # Snow Showers
    5101: "❄️", # Heavy Snow
    6000: "🧊", # Freezing Drizzle
    6001: "🧊", # Light Freezing Rain
    6200: "🧊", # Freezing Rain
    6201: "🧊", # Heavy Freezing Rain
    7000: "🌨️", # Ice Pellets
    7101: "🌨️", # Heavy Ice Pellets
    7102: "🌨️", # Light Ice Pellets
    8000: "⛈️", # Thunderstorm
    # Add more specific codes if needed based on API response
}

DEFAULT_ICON = "❓"

def get_weather_icon(weather_code):
    """Returns an emoji icon for a given Tomorrow.io weather code."""
    return WEATHER_CODE_TO_ICON.get(weather_code, DEFAULT_ICON)

def get_tomorrow_io_forecast(latitude, longitude, api_key=None, days=7):
    """
    Fetches 7-day weather forecast from Tomorrow.io API.
    Includes temperature, precipitation, soil moisture, evapotranspiration, etc.
    """
    passed_api_key = api_key # Store the passed key if any
    api_key = os.getenv("TOMORROW_IO_API_KEY")

    if not api_key or api_key == "YOUR_TOMORROW_IO_API_KEY" or api_key.strip() == "":
        # st.warning("Tomorrow.io API key not configured in .env or is a placeholder. Weather data will be unavailable.")
        return {"error": "Tomorrow.io API key not configured."}

    # If a key was explicitly passed to the function, prefer that.
    # This allows for direct key injection for testing or specific scenarios,
    # overriding the .env one if needed.
    if passed_api_key:
        api_key = passed_api_key

    base_url = "https://api.tomorrow.io/v4/timelines"

    fields = [
        "temperatureMax", "temperatureMin", "temperatureApparent",
        "precipitationProbability", "precipitationType", "precipitationIntensity",
        "windSpeed", "windDirection", "windGust",
        "humidity",
        "pressureSurfaceLevel",
        "cloudCover",
        "weatherCode",
        "sunriseTime", "sunsetTime",
        "soilMoisture0To10cm",
        "evapotranspiration" # Corrected field name (was 'evapotranspiration')
    ]

    timesteps = ['1d']
    units = "metric"

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    startTime = now_utc.isoformat()
    endTime = (now_utc + datetime.timedelta(days=days)).isoformat()

    params = {
        "location": f"{latitude},{longitude}",
        "fields": ",".join(fields), # API expects comma-separated string for fields
        "units": units,
        "timesteps": ",".join(timesteps), # API expects comma-separated string
        "startTime": startTime,
        "endTime": endTime,
        "apikey": api_key
    }

    forecast_data_list = []
    error_message = None

    try:
        response = requests.get(base_url, params=params, timeout=15) # Increased timeout
        response.raise_for_status()
        data = response.json()

        if 'data' in data and 'timelines' in data['data'] and data['data']['timelines']:
            # Tomorrow.io returns timelines as a list, usually one for '1d' timestep
            timeline = data['data']['timelines'][0]
            if timeline['timestep'] == '1d' and 'intervals' in timeline:
                for day_data in timeline['intervals']:
                    dt_object = datetime.datetime.fromisoformat(day_data['startTime'].replace('Z', '+00:00'))
                    values = day_data.get('values', {})

                    # Helper to safely get and convert sunrise/sunset times
                    def format_datetime_field(time_str):
                        if not time_str: return "N/A"
                        try:
                            return datetime.datetime.fromisoformat(time_str.replace('Z', '+00:00')).strftime('%H:%M')
                        except ValueError:
                            return "N/A"

                    forecast_data_list.append({
                        "date": dt_object.strftime("%Y-%m-%d"),
                        "day": dt_object.strftime("%a"),
                        "temp_max": values.get("temperatureMax"),
                        "temp_min": values.get("temperatureMin"),
                        "temp_apparent": values.get("temperatureApparent"),
                        "precipitation_prob": values.get("precipitationProbability"),
                        "precipitation_intensity": values.get("precipitationIntensity"),
                        "precipitation_type": values.get("precipitationType"),
                        "wind_speed": values.get("windSpeed"),
                        "wind_direction": values.get("windDirection"),
                        "humidity": values.get("humidity"),
                        "cloud_cover": values.get("cloudCover"),
                        "weather_code": values.get("weatherCode"),
                        "icon": get_weather_icon(values.get("weatherCode")),
                        "sunrise": format_datetime_field(values.get("sunriseTime")),
                        "sunset": format_datetime_field(values.get("sunsetTime")),
                        "soil_moisture_0_10cm": values.get("soilMoisture0To10cm"),
                        "evapotranspiration": values.get("evapotranspiration")
                    })
            else:
                error_message = "Tomorrow.io API response malformed: 'intervals' or correct 'timestep' not found."
        else:
            # Check for specific error messages from Tomorrow.io
            if 'message' in data:
                error_message = f"Tomorrow.io API Error: {data.get('code', '')} - {data['message']}"
            elif 'type' in data and 'message' in data: # Another common error format
                 error_message = f"Tomorrow.io API Error: {data['type']} - {data['message']}"
            else:
                error_message = f"Tomorrow.io API response malformed: 'data' or 'timelines' missing. Response: {str(data)[:200]}"

    except requests.exceptions.Timeout:
        error_message = "Tomorrow.io API request timed out."
    except requests.exceptions.HTTPError as http_err:
        try:
            err_response_json = http_err.response.json()
            api_err_message = err_response_json.get('message', http_err.response.text)
            api_err_code = err_response_json.get('code', '')
            error_message = f"Tomorrow.io API HTTP error: {http_err.response.status_code} {api_err_code} - {api_err_message}"
        except ValueError: # If response is not JSON
            error_message = f"Tomorrow.io API HTTP error: {http_err} - Response: {http_err.response.text[:200]}"
    except requests.exceptions.RequestException as req_err:
        error_message = f"Tomorrow.io API request error: {req_err}"
    except Exception as e:
        error_message = f"Unexpected error processing Tomorrow.io response: {e}"

    if error_message:
        # st.error(error_message) # UI feedback in main app
        return {"error": error_message, "data": None}

    if not forecast_data_list and not error_message:
        error_message = "No forecast data parsed from Tomorrow.io response, though no explicit error was raised."
        return {"error": error_message, "data": None}

    return {"error": None, "data": forecast_data_list}


def display_weather_forecast(weather_data_result):
    """
    Displays the 7-day weather forecast in Streamlit columns.
    Expects the result from get_tomorrow_io_forecast which is a dict with 'error' and 'data'.
    """
    if weather_data_result is None: # Should not happen if get_tomorrow_io_forecast is called correctly
        st.error("Weather data result is unexpectedly None.")
        return

    if weather_data_result.get("error"):
        st.error(f"Could not display weather: {weather_data_result['error']}")
        # Optionally display any partial data if available and desired
        # if weather_data_result.get("data"):
        #     st.warning("Displaying potentially incomplete weather data due to earlier error.")
        # else:
        return

    weather_data = weather_data_result.get("data")

    if not weather_data:
        st.info("No weather data available to display (it might be empty or an error occurred).")
        return

    st.subheader("🌦️ 7-Day Weather Forecast")

    # Ensure weather_data is a list and not empty before trying to make columns
    if not isinstance(weather_data, list) or not weather_data:
        st.warning("Weather data is not in the expected list format or is empty.")
        return

    cols = st.columns(min(len(weather_data), 7)) # Max 7 columns for display

    for i, day_weather in enumerate(weather_data[:len(cols)]): # Iterate only for the number of columns created
        with cols[i]:
            st.markdown(f"**{day_weather.get('day', 'N/A')}**")
            date_str = day_weather.get('date', 'N/A')
            st.markdown(f"`{date_str[-5:] if date_str != 'N/A' else 'N/A'}`")
            st.markdown(f"<h1 style='text-align: center; font-size: 2em;'>{day_weather.get('icon', DEFAULT_ICON)}</h1>", unsafe_allow_html=True)

            temp_max = day_weather.get('temp_max')
            temp_min = day_weather.get('temp_min')
            if temp_max is not None and temp_min is not None:
                st.metric(label="Temp", value=f"{temp_max:.0f}°/{temp_min:.0f}°C")
            else:
                st.caption("Temp N/A")

            precip_prob = day_weather.get('precipitation_prob')
            if precip_prob is not None:
                st.write(f"💧 {precip_prob:.0f}%")
            else:
                st.caption("Precip N/A")

            with st.expander("Details", expanded=False):
                if day_weather.get("temp_apparent") is not None:
                    st.write(f"Feels like: {day_weather['temp_apparent']:.0f}°C")
                if day_weather.get("humidity") is not None:
                    st.write(f"Humidity: {day_weather['humidity']:.0f}%")
                if day_weather.get("wind_speed") is not None:
                    st.write(f"Wind: {day_weather['wind_speed']:.1f} m/s")
                if day_weather.get("soil_moisture_0_10cm") is not None:
                    st.write(f"Soil Moist (0-10cm): {day_weather['soil_moisture_0_10cm']:.1f}%")
                if day_weather.get("evapotranspiration") is not None:
                    st.write(f"ET₀: {day_weather['evapotranspiration']:.2f} mm/day")
                if day_weather.get("sunrise") != "N/A":
                    st.write(f"Sunrise: {day_weather['sunrise']}")
                if day_weather.get("sunset") != "N/A":
                    st.write(f"Sunset: {day_weather['sunset']}")

    # Weather Trend Graphs
    try:
        df_weather = pd.DataFrame(weather_data)
        if df_weather.empty:
            st.info("No data available for trend graphs.")
            return

        df_weather['date'] = pd.to_datetime(df_weather['date'], errors='coerce')
        df_weather.dropna(subset=['date'], inplace=True) # Remove rows where date conversion failed
        if df_weather.empty:
            st.info("No valid date data for trend graphs after conversion.")
            return
    except Exception as e:
        st.error(f"Could not process data for trend graphs: {e}")
        return

    st.subheader("📈 Weather Trends")

    # Temperature Trend
    if 'temp_max' in df_weather.columns and df_weather['temp_max'].notna().any() and \
       'temp_min' in df_weather.columns and df_weather['temp_min'].notna().any():
        fig_temp = px.line(df_weather, x='date', y=['temp_max', 'temp_min'],
                           title="Temperature Trend (°C)",
                           labels={'value':'Temperature (°C)', 'date':'Date', 'variable': 'Metric'},
                           markers=True)
        fig_temp.update_layout(legend_title_text='')
        st.plotly_chart(fig_temp, use_container_width=True)

    # Precipitation Probability Trend
    if 'precipitation_prob' in df_weather.columns and df_weather['precipitation_prob'].notna().any():
        fig_precip = px.bar(df_weather, x='date', y='precipitation_prob',
                            title="Precipitation Probability (%)",
                            labels={'precipitation_prob':'Probability (%)', 'date':'Date'},
                            color='precipitation_prob', color_continuous_scale=px.colors.sequential.Blues)
        st.plotly_chart(fig_precip, use_container_width=True)

    # Soil Moisture Trend (if available)
    if 'soil_moisture_0_10cm' in df_weather.columns and df_weather['soil_moisture_0_10cm'].notna().any():
        # Convert to numeric, coercing errors, then drop NaNs that might result from coercion
        df_weather['soil_moisture_0_10cm'] = pd.to_numeric(df_weather['soil_moisture_0_10cm'], errors='coerce')
        df_plot_soil = df_weather.dropna(subset=['soil_moisture_0_10cm'])
        if not df_plot_soil.empty:
            fig_soil = px.line(df_plot_soil, x='date', y='soil_moisture_0_10cm',
                               title="Soil Moisture (0-10cm) Trend (%)",
                               labels={'soil_moisture_0_10cm':'Soil Moisture (%)', 'date':'Date'},
                               markers=True)
            st.plotly_chart(fig_soil, use_container_width=True)

if __name__ == '__main__':
    # Example Usage (for testing module standalone)
    # Requires TOMORROW_IO_API_KEY in .env in the parent directory
    print("Testing weather module...")

    from dotenv import load_dotenv
    # Load .env from parent directory relative to this modules/ script
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(dotenv_path=dotenv_path)

    api_key = os.getenv("TOMORROW_IO_API_KEY")

    if not api_key or api_key == "YOUR_TOMORROW_IO_API_KEY":
        print("TOMORROW_IO_API_KEY not set in .env or is placeholder. Skipping API call test.")
    else:
        print(f"Using Tomorrow.io API Key: {api_key[:5]}...{api_key[-5:]}")
        # New Delhi coordinates
        test_lat, test_lon = 28.6139, 77.2090

        print(f"\nFetching weather for Lat: {test_lat}, Lon: {test_lon}")
        forecast = get_tomorrow_io_forecast(test_lat, test_lon, api_key=api_key)

        if forecast:
            print(f"Successfully fetched {len(forecast)}-day forecast.")
            for day in forecast:
                print(f"  {day['date']} ({day['day']}): {day['icon']} {day['temp_min']}-{day['temp_max']}°C, Precip: {day['precipitation_prob']}%")
                if day.get('soil_moisture_0_10cm') is not None:
                    print(f"    Soil Moisture (0-10cm): {day['soil_moisture_0_10cm']}%")
                if day.get('evapotranspiration') is not None:
                    print(f"    Evapotranspiration: {day['evapotranspiration']} mm/day")

            # To test display functions in Streamlit, you'd run:
            # import streamlit as st
            # from modules import weather
            # test_lat, test_lon = 28.6139, 77.2090
            # forecast = weather.get_tomorrow_io_forecast(test_lat, test_lon)
            # if forecast:
            #     weather.display_weather_forecast(forecast)
            # else:
            #     st.error("Failed to get forecast for testing display.")
        else:
            print("Failed to fetch weather forecast.")

    # Test icon mapping
    print("\nTesting weather icon mapping:")
    print(f"Code 1000 (Clear, Sunny): {get_weather_icon(1000)}")
    print(f"Code 4200 (Rain): {get_weather_icon(4200)}")
    print(f"Code 9999 (Unknown): {get_weather_icon(9999)}")
```
