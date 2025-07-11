import streamlit as st
import requests
from geopy.geocoders import Nominatim
import os

# Ensure you have GOOGLE_MAPS_API_KEY in your .env file if using Google
# and load_dotenv() is called in app.py

def get_browser_location_javascript():
    """
    Returns JavaScript code to get geolocation from the browser.
    This needs to be executed in Streamlit using a component like streamlit-js-eval.
    """
    return """
    async function getGeoLocation() {
        return new Promise((resolve, reject) => {
            if (!navigator.geolocation) {
                reject("Geolocation is not supported by your browser.");
            } else {
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        resolve({
                            latitude: position.coords.latitude,
                            longitude: position.coords.longitude,
                            accuracy: position.coords.accuracy,
                            error: null
                        });
                    },
                    (error) => {
                        let errorMessage;
                        switch(error.code) {
                            case error.PERMISSION_DENIED:
                                errorMessage = "User denied the request for Geolocation.";
                                break;
                            case error.POSITION_UNAVAILABLE:
                                errorMessage = "Location information is unavailable.";
                                break;
                            case error.TIMEOUT:
                                errorMessage = "The request to get user location timed out.";
                                break;
                            case error.UNKNOWN_ERROR:
                                errorMessage = "An unknown error occurred.";
                                break;
                            default:
                                errorMessage = "An unspecified error occurred.";
                        }
                        resolve({ // Resolve with error details, don't reject outer promise
                            latitude: null,
                            longitude: null,
                            accuracy: null,
                            error: errorMessage
                        });
                    }
                );
            }
        });
    }
    // The getGeoLocation function is defined, now call it and return the promise
    return getGeoLocation();
    """

def reverse_geocode_osm(latitude, longitude):
    """
    Reverse geocodes coordinates to a human-readable address using OpenStreetMap Nominatim.
    Returns a dictionary with address components (village, district, state, country) or None.
    """
    if latitude is None or longitude is None:
        return None

    try:
        geolocator = Nominatim(user_agent="agriguru_app") # Replace with your app's name
        location = geolocator.reverse((latitude, longitude), exactly_one=True, language="en", timeout=10)

        if location and location.address:
            address = location.raw.get('address', {})
            # OSM address hierarchy can vary. Prioritize specific terms, then fall back.
            village = address.get('village', address.get('hamlet', address.get('suburb', 'N/A')))
            # District can be 'county', 'state_district', etc.
            district = address.get('county', address.get('state_district', address.get('city_district', 'N/A')))
            state = address.get('state', 'N/A')
            country = address.get('country', 'N/A')

            return {
                "village": village,
                "district": district,
                "state": state,
                "country": country,
                "full_address": location.address
            }
        else:
            return None
    except Exception as e:
        st.error(f"OSM Reverse geocoding error: {e}")
        return None

def reverse_geocode_google(latitude, longitude):
    """
    Reverse geocodes coordinates using Google Maps Geocoding API.
    Requires GOOGLE_MAPS_API_KEY to be set in the environment.
    Returns a dictionary with address components or None.
    """
    if latitude is None or longitude is None:
        return None

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key or api_key == "YOUR_GOOGLE_MAPS_API_KEY" or api_key.strip() == "":
        # st.warning("Google Maps API key not configured or is a placeholder. Google Geocoding disabled.")
        # Optionally, you could fall back to OSM here directly:
        # st.info("Falling back to OSM Nominatim for reverse geocoding due to Google API key issue.")
        # return reverse_geocode_osm(latitude, longitude)
        return {"error": "Google Maps API key not configured."}


    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "latlng": f"{latitude},{longitude}",
        "key": api_key,
        # More specific result types can help narrow down, but also might miss if not perfectly matching
        # "result_type": "political|locality|sublocality|administrative_area_level_1|administrative_area_level_2|administrative_area_level_3|postal_code",
        "language": "en"
    }

    address_data = {
        "village": "N/A", "district": "N/A", "state": "N/A",
        "country": "N/A", "full_address": "N/A", "error": None
    }

    try:
        response = requests.get(base_url, params=params, timeout=10) # Added timeout
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        data = response.json()

        if data['status'] == 'OK' and data['results']:
            # Use the first result, often the most specific
            top_result = data['results'][0]
            address_components = top_result['address_components']
            address_data["full_address"] = top_result.get('formatted_address', 'N/A')

            # Component extraction logic
            # Prioritize more specific types, then fall back to broader ones.
            # This mapping might need adjustment based on observed API responses for target regions (e.g., rural India)
            component_map = {
                'village': ['sublocality_level_1', 'locality', 'administrative_area_level_3', 'political'],
                'district': ['administrative_area_level_2', 'locality'], # Locality can sometimes be district in certain structures
                'state': ['administrative_area_level_1'],
                'country': ['country']
            }

            found_components = {key: None for key in component_map.keys()}

            for component in address_components:
                types = component.get('types', [])
                for key, google_types in component_map.items():
                    if not found_components[key]: # If not already found
                        for g_type in google_types:
                            if g_type in types:
                                found_components[key] = component.get('long_name')
                                break # Found for this key, move to next key

            address_data.update({k: v if v else "N/A" for k, v in found_components.items()})

            # Refinement for village: if specific village types are N/A, check if 'locality' or 'political'
            # is not already assigned to district/state/country, implying it might be the village/town.
            if address_data['village'] == 'N/A':
                locality_val = found_components.get('locality')
                political_val = found_components.get('political')
                if locality_val and locality_val not in [address_data['district'], address_data['state'], address_data['country']]:
                    address_data['village'] = locality_val
                elif political_val and political_val not in [address_data['district'], address_data['state'], address_data['country']]:
                     address_data['village'] = political_val


        elif data['status'] == 'ZERO_RESULTS':
            address_data["error"] = "Google Geocoding: No results found for the given coordinates."
            # st.warning(address_data["error"]) # UI feedback in main app
        else:
            # Handle other statuses like 'REQUEST_DENIED', 'INVALID_REQUEST', 'OVER_QUERY_LIMIT'
            error_message = data.get('error_message', 'Unknown Google API error.')
            address_data["error"] = f"Google Geocoding API error: {data['status']} - {error_message}"
            # st.error(address_data["error"]) # UI feedback in main app

        return address_data

    except requests.exceptions.Timeout:
        address_data["error"] = "Google Geocoding request timed out."
        # st.error(address_data["error"])
        return address_data
    except requests.exceptions.RequestException as e:
        address_data["error"] = f"Network error during Google Geocoding: {e}"
        # st.error(address_data["error"])
        return address_data
    except Exception as e: # Catch any other unexpected errors
        address_data["error"] = f"Unexpected error processing Google Geocoding response: {e}"
        # st.error(address_data["error"])
        return address_data


def get_detailed_location(latitude, longitude, provider="osm"):
    """
    Gets detailed location (village, district, state, country) using the specified provider.
    Provider can be 'osm' (OpenStreetMap) or 'google'.
    Returns a dictionary containing location details and any error messages.
    """
    if latitude is None or longitude is None:
        return {"error": "Latitude or Longitude not provided."}

    api_key_google = os.getenv("GOOGLE_MAPS_API_KEY")
    google_key_valid = api_key_google and api_key_google != "YOUR_GOOGLE_MAPS_API_KEY" and api_key_google.strip() != ""

    location_data = {
        "latitude": latitude, "longitude": longitude,
        "village": "N/A", "district": "N/A", "state": "N/A", "country": "N/A",
        "full_address": "N/A", "provider_used": provider, "error": None
    }

    if provider == "google":
        if not google_key_valid:
            location_data["error"] = "Google Maps API key not configured. Cannot use Google provider."
            # st.warning(location_data["error"] + " Attempting OSM fallback.") # UI feedback in main app
            # Fallback to OSM if Google key is bad from the start
            provider = "osm"
            location_data["provider_used"] = "osm_fallback_due_to_key"
        else:
            google_addr_details = reverse_geocode_google(latitude, longitude)
            if google_addr_details.get("error"):
                location_data["error"] = google_addr_details["error"]
                # st.warning(f"Google Geocoding failed: {google_addr_details['error']}. Attempting OSM fallback.") # UI feedback
                # Fallback to OSM if Google API call fails
                provider = "osm"
                location_data["provider_used"] = "osm_fallback_due_to_api_error"
            else:
                location_data.update(google_addr_details)
                return location_data # Successfully got from Google

    if provider == "osm": # This block will also execute on fallbacks
        osm_addr_details = reverse_geocode_osm(latitude, longitude)
        if osm_addr_details: # OSM success
            # If it was a fallback, we only update address parts, keep original error if any from Google attempt
            if "fallback" in location_data["provider_used"]:
                # Preserve original error from Google attempt, but update address with OSM data
                original_google_error = location_data["error"]
                location_data.update(osm_addr_details) # Update village, district etc.
                location_data["error"] = original_google_error # Restore original error
                location_data["error"] += " | OSM data shown as fallback." # Append info
            else: # Direct OSM call success
                location_data.update(osm_addr_details)
                location_data["error"] = None # Clear any previous error if it was direct OSM
        else: # OSM failed
            osm_error_msg = "OSM Nominatim reverse geocoding failed."
            if "fallback" in location_data["provider_used"]:
                location_data["error"] += f" | {osm_error_msg}" # Append to existing Google error
            else:
                location_data["error"] = osm_error_msg
            # st.error(osm_error_msg) # UI feedback in main app

    # Final check for N/A values if no provider succeeded fully
    if location_data["full_address"] == "N/A" and not location_data["error"]:
        location_data["error"] = "Could not determine address from any provider."

    return location_data


if __name__ == '__main__':
    # Example Usage (for testing module standalone)
    # Note: Streamlit components (st.error, st.warning) won't render here directly.
    # You would typically call these functions from your main Streamlit app.

    print("Testing location module...")

    # --- Test OSM (No API key needed) ---
    print("\n--- Testing with OSM Nominatim ---")
    # Coordinates for a location in India (e.g., a village in Haryana)
    test_lat_osm, test_lon_osm = 29.0470, 76.9902
    osm_location = get_detailed_location(test_lat_osm, test_lon_osm, provider="osm")
    if osm_location:
        print(f"OSM - Village: {osm_location['village']}")
        print(f"OSM - District: {osm_location['district']}")
        print(f"OSM - State: {osm_location['state']}")
        print(f"OSM - Country: {osm_location['country']}")
        print(f"OSM - Full Address: {osm_location['full_address']}")
    else:
        print("OSM - Could not retrieve location details.")

    # --- Test Google (Requires API Key in .env) ---
    # Make sure to load .env if running this standalone and it's not loaded by Streamlit
    from dotenv import load_dotenv
    load_dotenv(dotenv_path='../.env') # Assuming .env is in the parent AgriGuru directory

    print("\n--- Testing with Google Geocoding API ---")
    google_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not google_api_key or google_api_key == "YOUR_GOOGLE_MAPS_API_KEY":
        print("GOOGLE_MAPS_API_KEY not set in .env or is placeholder. Skipping Google API test.")
    else:
        # Coordinates for New Delhi as an example
        test_lat_google, test_lon_google = 28.6139, 77.2090
        google_location = get_detailed_location(test_lat_google, test_lon_google, provider="google")
        if google_location:
            print(f"Google - Village/Locality: {google_location['village']}") # Google's definition of 'village' can vary
            print(f"Google - District: {google_location['district']}")
            print(f"Google - State: {google_location['state']}")
            print(f"Google - Country: {google_location['country']}")
            print(f"Google - Full Address: {google_location['full_address']}")
            print(f"Google - Provider Used: {google_location['provider']}")
        else:
            print("Google - Could not retrieve location details (or fell back to OSM and failed).")

    # --- Test JavaScript snippet (just prints it) ---
    # print("\n--- Browser Geolocation JavaScript ---")
    # print(get_browser_location_javascript())
    # In a Streamlit app, you would use streamlit_js_eval:
    # from streamlit_js_eval import streamlit_js_eval, copy_to_clipboard
    # geo_location = streamlit_js_eval(js_expressions=get_browser_location_javascript(), key = 'GEO_LOCATION')
    # if geo_location and geo_location['error'] is None:
    #    lat = geo_location['latitude']
    #    lon = geo_location['longitude']
    #    # then call get_detailed_location(lat, lon)
    # elif geo_location and geo_location['error']:
    #    st.error(geo_location['error'])
    # else:
    #    st.warning("Waiting for location permission or location data...")
```
