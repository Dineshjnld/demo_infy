import streamlit as st
from dotenv import load_dotenv
import os
import datetime
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium

# Import modules
from modules import location, weather, maps, market, chatbot # Ensure these are correctly named

# For browser location - requires streamlit_js_eval (ensure it's in requirements.txt)
try:
    from streamlit_js_eval import streamlit_js_eval, copy_to_clipboard
except ImportError:
    streamlit_js_eval = None
    st.warning("`streamlit-js-eval` not installed. Browser geolocation will not work. Please install it: pip install streamlit-js-eval")


# Load environment variables from .env file
load_dotenv() # Make sure this is at the top

# --- App State Initialization ---
if "user_location" not in st.session_state:
    st.session_state.user_location = None # Will store dict: {lat, lon, village, district, state, country, error}
if "weather_data" not in st.session_state:
    st.session_state.weather_data = None # Will store dict: {data, error}
if "market_data_result" not in st.session_state:
    st.session_state.market_data_result = {"data": None, "error": None}
if "messages" not in st.session_state: # For chatbot
    st.session_state.messages = [{"role": "assistant", "content": "Namaste! How can I help you today?"}]


# --- Helper function for Mock Soil Data (until real API/data is integrated) ---
def get_mock_soil_data(lat, lon):
    """Returns mock soil data."""
    # Simple mock, can be expanded
    return {
        "type": "Loamy Clay (Mock)",
        "ph": round(6.0 + (lat % 1.5) + (lon % 0.5), 1), # Some variation
        "organic_matter": "Medium (Mock)",
        "nutrients": {"N": "Good", "P": "Fair", "K": "Good"}
    }

# --- Helper function for Mock Crop Suggestions ---
def get_mock_crop_suggestions(weather_conditions, soil_conditions, region_info):
    """Generates mock crop suggestions based on simplified rules."""
    suggestions = []
    if not weather_conditions or not soil_conditions:
        return ["Mock: Weather/Soil data needed"]

    # Example: Use average max temperature from the first few days of forecast
    avg_temp_max = 0
    count = 0
    if weather_conditions.get("data"):
        for day_weather in weather_conditions["data"][:3]: # Look at next 3 days
            if day_weather.get("temp_max") is not None:
                avg_temp_max += day_weather["temp_max"]
                count += 1
        if count > 0:
            avg_temp_max /= count

    soil_ph = soil_conditions.get("ph", 7.0)

    if avg_temp_max > 25 and soil_ph > 6.0 and soil_ph < 7.5:
        suggestions.extend(["Mock Rice", "Mock Cotton", "Mock Maize"])
    elif avg_temp_max > 15:
        suggestions.extend(["Mock Wheat", "Mock Mustard"])
    else:
        suggestions.append("Mock Barley")

    if not suggestions:
        suggestions.append("Mock: No specific suggestions for current conditions.")
    return suggestions


# --- Streamlit App Layout ---
st.set_page_config(layout="wide", page_title="🌾 AgriGuru")
st.title("🌾 AgriGuru: Your Smart Farming Assistant")

# --- 1. Location Detection and Display ---
st.sidebar.header("📍 Location")

# Button to trigger geolocation
if streamlit_js_eval and st.sidebar.button("Detect My Location"):
    with st.spinner("Detecting your location... Please allow browser permission."):
        js_code = location.get_browser_location_javascript()
        loc_js = streamlit_js_eval(js_expressions=js_code, key='GEO_LOCATION_DETECTION')

        if loc_js and loc_js.get("latitude") is not None:
            lat, lon = loc_js["latitude"], loc_js["longitude"]
            # st.sidebar.info(f"Coordinates: Lat {lat:.4f}, Lon {lon:.4f}. Fetching address...")

            # Using Google Geocoding first, then OSM as fallback (as per location module logic)
            # The get_detailed_location function handles API key check and fallback logic
            addr_details = location.get_detailed_location(lat, lon, provider="google")

            if addr_details and not addr_details.get("error"):
                st.session_state.user_location = addr_details
                # st.sidebar.success("Location detected and address found!")
            elif addr_details and addr_details.get("error"):
                st.session_state.user_location = {"latitude": lat, "longitude": lon, "error": addr_details["error"]}
                # st.sidebar.error(f"Geocoding Error: {addr_details['error']}")
            else: # Should not happen if get_detailed_location returns consistently
                st.session_state.user_location = {"latitude": lat, "longitude": lon, "error": "Unknown error during geocoding."}
                # st.sidebar.error("Could not fetch address details.")
        elif loc_js and loc_js.get("error"):
            st.session_state.user_location = {"error": loc_js["error"]}
            # st.sidebar.error(f"Browser Geolocation Error: {loc_js['error']}")
        else: # loc_js is None or timeout
            st.session_state.user_location = {"error": "Could not get location from browser (timeout or no data)."}
            # st.sidebar.warning("Could not get location from browser.")
    # Force a rerun to update the UI with new location data
    st.experimental_rerun()


# Display current location from session state
if st.session_state.user_location:
    current_loc = st.session_state.user_location
    if current_loc.get("error"):
        st.sidebar.error(f"Location Error: {current_loc['error']}")
        # Fallback display if only coords are available but geocoding failed
        if current_loc.get("latitude") is not None:
             st.sidebar.write(f"Lat: {current_loc['latitude']:.4f}, Lon: {current_loc['longitude']:.4f} (Address lookup failed)")
             st.header(f"📍 Lat: {current_loc['latitude']:.2f}, Lon: {current_loc['longitude']:.2f} (Location Details Pending)")
        else:
            st.header("📍 Location Undetected or Error")
    else:
        loc_display_name = current_loc.get('village', 'N/A')
        if loc_display_name == 'N/A': loc_display_name = current_loc.get('district', 'N/A')

        st.sidebar.success("Location Set:")
        st.sidebar.write(f"**Village/Area:** {current_loc.get('village', 'N/A')}")
        st.sidebar.write(f"**District:** {current_loc.get('district', 'N/A')}")
        st.sidebar.write(f"**State:** {current_loc.get('state', 'N/A')}")
        st.sidebar.write(f"**Country:** {current_loc.get('country', 'N/A')}")
        st.sidebar.write(f"**Lat:** {current_loc.get('latitude'):.4f}, **Lon:** {current_loc.get('longitude'):.4f}")
        st.sidebar.caption(f"Provider: {current_loc.get('provider_used', 'N/A')}")

        header_loc_name = f"{current_loc.get('village', '')}, {current_loc.get('district', '')}".strip(", ")
        if not header_loc_name: header_loc_name = f"{current_loc.get('state', 'Location Set')}"
        st.header(f"📍 {header_loc_name}")
else:
    st.sidebar.info("Click 'Detect My Location' or ensure location services are enabled.")
    st.header("📍 Location Not Set")


# --- Main Dashboard Area (Tabs) ---
# Only show tabs if location coordinates are available
if st.session_state.user_location and st.session_state.user_location.get("latitude") is not None:
    lat = st.session_state.user_location["latitude"]
    lon = st.session_state.user_location["longitude"]

    tab1, tab2, tab3, tab4 = st.tabs(["🌦️ Weather", "🗺️ Map & Soil", "🌱 Crop Suggestions", "💹 Market Prices"])

    # --- Weather Tab ---
    with tab1:
        st.subheader("🌦️ Weather Forecast")
        with st.spinner("Fetching weather data..."):
            # Fetch weather only if not already fetched or location changed
            # (Simple check, can be more sophisticated with coords comparison)
            if st.session_state.weather_data is None or \
               st.session_state.weather_data.get("_latlon") != (lat, lon) :
                st.session_state.weather_data = weather.get_tomorrow_io_forecast(lat, lon)
                st.session_state.weather_data["_latlon"] = (lat,lon) # Store coords with data

        weather.display_weather_forecast(st.session_state.weather_data)

    # --- Map & Soil Tab ---
    with tab2:
        maps.display_interactive_map(st.session_state.user_location) # Pass full location dict

        st.subheader("Soil Profile (Mock Data)")
        # Using mock soil data for now
        soil_data = get_mock_soil_data(lat, lon)
        if soil_data:
            st.write(f"**Soil Type:** {soil_data['type']}")
            st.write(f"**pH Level:** {soil_data['ph']}")
            st.write(f"**Organic Matter:** {soil_data['organic_matter']}")
            st.write("**Key Nutrients (Mock):**")
            for nutrient, level in soil_data['nutrients'].items():
                st.write(f"  - {nutrient}: {level}")
        else:
            st.warning("Mock soil data not available.")

    # --- Crop Suggestions Tab ---
    with tab3:
        st.subheader("🌱 Crop Suggestions (Rule-Based Mock)")
        # Needs weather and soil data
        current_weather_conditions = st.session_state.weather_data # From weather tab
        current_soil_conditions = get_mock_soil_data(lat, lon) # Still using mock soil
        region_info = {"district": st.session_state.user_location.get("district", "N/A")}

        if current_weather_conditions and not current_weather_conditions.get("error") and current_soil_conditions:
            suggestions = get_mock_crop_suggestions(current_weather_conditions, current_soil_conditions, region_info)
            st.write("Based on current local conditions (mock logic), suitable crops might include:")
            for crop in suggestions:
                st.success(f"**{crop}**")
        else:
            st.warning("Cannot provide crop suggestions without valid weather or soil data.")
            if current_weather_conditions and current_weather_conditions.get("error"):
                st.error(f"Weather data error: {current_weather_conditions['error']}")

    # --- Market Prices Tab ---
    with tab4:
        # The market.display_market_prices function now handles its own UI for inputs and display
        # It returns an error if user_location is insufficient, which we handle by not calling it
        # or by it displaying its own warning.
        if st.session_state.user_location and \
           st.session_state.user_location.get("district") and \
           st.session_state.user_location.get("state"):
            market.display_market_prices(st.session_state.user_location)
        else:
            st.warning("Market prices require District and State information from your detected location.")

else: # If no valid location coordinates
    st.info("Please detect your location to view detailed dashboards.")


# --- 5. Integrated AI Chatbot ---
st.sidebar.header("🤖 AgriGuru Chatbot")

# Chat history display
for msg in st.session_state.messages:
    with st.sidebar: # Ensure chat messages are within the sidebar
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

# Chat input: Text
text_prompt = st.sidebar.chat_input("Ask me anything (text)...")
if text_prompt:
    with st.sidebar:
        with st.chat_message("user"):
            st.write(text_prompt)
    st.session_state.messages.append({"role": "user", "content": text_prompt})

    with st.spinner("AgriGuru is thinking..."):
        chat_response = chatbot.handle_chat_input(
            user_input_text=text_prompt,
            user_location=st.session_state.user_location
        )

    with st.sidebar:
        with st.chat_message("assistant"):
            st.write(chat_response.get("bot_response_text", "Sorry, I encountered an issue."))
            if chat_response.get("bot_response_audio_bytes"):
                st.audio(chat_response["bot_response_audio_bytes"], format=chat_response.get("bot_audio_format", "audio/mp3"))
            if chat_response.get("error"):
                st.error(f"Chatbot Error: {chat_response['error']}")

    st.session_state.messages.append({"role": "assistant", "content": chat_response.get("bot_response_text")})
    # Rerun to show new messages immediately
    st.experimental_rerun()


# Chat input: Audio (using file uploader for now)
st.sidebar.markdown("---")
st.sidebar.subheader("Voice Input (Upload)")
uploaded_audio_file = st.sidebar.file_uploader("Upload an audio query (WAV, MP3):", type=['wav', 'mp3', 'ogg', 'm4a'])

if uploaded_audio_file is not None:
    if st.sidebar.button("Process Voice Query"):
        audio_bytes = uploaded_audio_file.read()
        st.session_state.messages.append({"role": "user", "content": f"[Audio query: {uploaded_audio_file.name}]"})
        with st.sidebar: # Show user's "audio sent" message
             with st.chat_message("user"):
                st.write(f"[Audio query sent: {uploaded_audio_file.name}]")

        with st.spinner("Transcribing and processing your voice query... This might take a moment."):
            chat_response = chatbot.handle_chat_input(
                audio_bytes_data=audio_bytes,
                user_location=st.session_state.user_location
            )

        with st.sidebar: # Display ASR transcript and bot response
            if chat_response.get("user_transcript"):
                 st.info(f"Heard: \"{chat_response['user_transcript']}\"")

            with st.chat_message("assistant"):
                st.write(chat_response.get("bot_response_text", "Sorry, I couldn't process the audio properly."))
                if chat_response.get("bot_response_audio_bytes"):
                    st.audio(chat_response["bot_response_audio_bytes"], format=chat_response.get("bot_audio_format", "audio/mp3"))
                if chat_response.get("error"):
                    st.error(f"Chatbot Audio Error: {chat_response['error']}")

        st.session_state.messages.append({"role": "assistant", "content": chat_response.get("bot_response_text")})
        # Rerun to update chat display
        st.experimental_rerun()


st.sidebar.markdown("---")
st.sidebar.info("Note: AgriGuru is a prototype. Some data may be mocked or sourced from services with usage limits.")

# --- Footer ---
st.markdown("---")
st.markdown("Built with ❤️ using Streamlit for the AgriGuru Project.")

# To run this app:
# 1. Ensure all dependencies from requirements.txt are installed.
# 2. Create a .env file with your API keys (GOOGLE_MAPS_API_KEY, TOMORROW_IO_API_KEY).
# 3. Run: streamlit run AgriGuru/app.py
st.markdown("Built with ❤️ using Streamlit for the AgriGuru Project.")

# To run this app:
# 1. Make sure you have streamlit and other libraries installed: pip install -r requirements.txt
# 2. Save this as app.py in your AgriGuru folder.
# 3. Run: streamlit run app.py
```
