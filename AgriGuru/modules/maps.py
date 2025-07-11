import streamlit as st
import folium
from streamlit_folium import st_folium
import os
import requests
import pandas as pd # For potential data overlays later

# Placeholder for actual soil data fetching/integration
# For now, we'll use mock data or simple markers.
# Real integration would involve APIs like SoilGrids or static datasets (e.g., ICAR for India).

# --- Map Configuration ---
DEFAULT_ZOOM = 12
SATELLITE_TILE = {
    "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    "attr": "Esri",
    "name": "Esri Satellite"
}
OPENSTREETMAP_TILE = {
    "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "attr": "OpenStreetMap",
    "name": "OpenStreetMap"
}

def create_base_map(latitude, longitude, zoom=DEFAULT_ZOOM):
    """Creates a Folium map centered at the given lat/lon."""
    if latitude is None or longitude is None:
        st.warning("Map cannot be displayed without location coordinates.")
        return None
    m = folium.Map(location=[latitude, longitude], zoom_start=zoom, control_scale=True)
    return m

def add_location_marker(folium_map, latitude, longitude, popup_text="Your Location", tooltip_text="Click for details"):
    """Adds a marker to the Folium map."""
    if folium_map and latitude is not None and longitude is not None:
        folium.Marker(
            [latitude, longitude],
            popup=folium.Popup(popup_text, max_width=250),
            tooltip=tooltip_text,
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(folium_map)
    return folium_map

def add_tile_layers(folium_map):
    """Adds standard and satellite tile layers to the map."""
    if folium_map:
        # Default OpenStreetMap layer is usually added by folium.Map()
        # Explicitly add it for clarity and if we want to customize
        folium.TileLayer(
            tiles=OPENSTREETMAP_TILE["url"],
            attr=OPENSTREETMAP_TILE["attr"],
            name=OPENSTREETMAP_TILE["name"],
            overlay=False, # Base layer
            control=True
        ).add_to(folium_map)

        # Satellite Layer
        folium.TileLayer(
            tiles=SATELLITE_TILE["url"],
            attr=SATELLITE_TILE["attr"],
            name=SATELLITE_TILE["name"],
            overlay=True, # Can be overlaid
            control=True,
            show=False # Initially not shown, user can toggle
        ).add_to(folium_map)
    return folium_map

# --- Soil Data and Crop Suitability (Placeholders) ---
def get_mock_soil_ph_data(latitude, longitude):
    """
    Placeholder function to simulate fetching soil pH data.
    In a real app, this would query a soil API or database.
    Returns a mock pH value or a small GeoJSON feature collection.
    """
    # For demonstration, let's return a simple point with a pH value
    mock_ph = 6.5 + (latitude % 1) - 0.5 # Some variation based on lat
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [longitude, latitude]
                },
                "properties": {
                    "ph": round(mock_ph, 1),
                    "description": f"Approx. Soil pH: {round(mock_ph, 1)}"
                }
            }
        ]
    }

def add_soil_ph_layer(folium_map, latitude, longitude):
    """
    Adds a mock soil pH data layer to the map.
    This is a placeholder. Real implementation would need actual soil data.
    """
    if folium_map is None: return None

    soil_ph_geojson = get_mock_soil_ph_data(latitude, longitude)

    if soil_ph_geojson and soil_ph_geojson['features']:
        # Style function for the GeoJSON layer
        def style_function(feature):
            ph = feature['properties'].get('ph', 7.0)
            color = 'green' # Neutral
            if ph < 6.0: color = 'orange' # Acidic
            elif ph > 7.5: color = 'blue'   # Alkaline
            return {
                'fillColor': color,
                'color': color,
                'weight': 1,
                'fillOpacity': 0.3,
                'radius': 8 # If it's point data, for circle markers
            }

        # Tooltip for the GeoJSON layer
        tooltip = folium.features.GeoJsonTooltip(
            fields=['description'],
            aliases=['Soil Info:'],
            sticky=False
        )

        # Add GeoJSON layer
        # If points, use folium.features.GeoJson with point_to_layer for CircleMarkers
        # If polygons, GeoJson will render them directly.
        # For this mock point data, we'll use a simple CircleMarker for each feature.

        # Create a FeatureGroup for soil data
        soil_fg = folium.FeatureGroup(name="Approx. Soil pH", show=False) # Initially hidden

        for feature in soil_ph_geojson['features']:
            coords = feature['geometry']['coordinates'] # [lon, lat]
            ph_val = feature['properties'].get('ph', 'N/A')
            desc = feature['properties'].get('description', f'Soil pH: {ph_val}')

            ph_num = 7.0
            try:
                ph_num = float(ph_val)
            except ValueError:
                pass

            color = 'gray' # Neutral default
            if ph_num < 6.0: color = 'orange' # Acidic
            elif ph_num < 7.0: color = 'lightgreen'
            elif ph_num <= 7.5: color = 'green'
            else: color = 'blue'   # Alkaline

            folium.CircleMarker(
                location=[coords[1], coords[0]], # Folium expects [lat, lon]
                radius=10,
                popup=folium.Popup(f"pH: {ph_val}", max_width=150),
                tooltip=desc,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.6
            ).add_to(soil_fg)

        soil_fg.add_to(folium_map)
    return folium_map

# --- Main Map Display Function ---
def display_interactive_map(user_location):
    """
    Creates and displays the main interactive map in Streamlit.
    Includes location pin, satellite/standard views, and mock soil pH overlay.
    """
    if not user_location or user_location.get("latitude") is None or user_location.get("longitude") is None:
        st.warning("Location data is missing. Cannot display map.")
        return

    lat = user_location["latitude"]
    lon = user_location["longitude"]
    loc_name = user_location.get("village", "Current Location")

    st.subheader("🗺️ Local Analysis Map")

    m = create_base_map(lat, lon)
    if m:
        m = add_tile_layers(m) # Add OSM and Satellite
        m = add_location_marker(m, lat, lon, popup_text=f"{loc_name}<br>Lat: {lat:.4f}, Lon: {lon:.4f}")

        # Add Soil pH Layer (Mock)
        m = add_soil_ph_layer(m, lat, lon) # This adds a FeatureGroup

        # Add Layer Control to toggle layers (like satellite, soil pH)
        folium.LayerControl().add_to(m)

        # Display map in Streamlit
        # The st_folium function returns data on map interactions (like last clicked point)
        # which can be useful for more advanced features.
        map_data = st_folium(m, width=700, height=500, returned_objects=[])
        # st.write(map_data) # For debugging map interaction data

    else:
        st.error("Failed to create the map.")


if __name__ == '__main__':
    # Example Usage (for testing module standalone with Streamlit)
    # To run this test: streamlit run AgriGuru/modules/maps.py
    # (Assuming your terminal is in the AgriGuru project root or you adjust path)

    st.set_page_config(layout="centered")
    st.title("Test: AgriGuru Maps Module")

    # Mock user location (e.g., New Delhi)
    mock_user_loc = {
        "latitude": 28.6139,
        "longitude": 77.2090,
        "village": "Central Delhi",
        "district": "New Delhi",
        "state": "Delhi",
        "country": "India"
    }

    st.sidebar.info(f"Displaying map for: {mock_user_loc['village']}")
    st.sidebar.write(f"Lat: {mock_user_loc['latitude']}, Lon: {mock_user_loc['longitude']}")

    display_interactive_map(mock_user_loc)

    st.markdown("---")
    st.subheader("Test: Map without location")
    display_interactive_map(None)

    st.subheader("Test: Map with only lat/lon")
    display_interactive_map({"latitude": 20.5937, "longitude": 78.9629}) # Central India
```
