# AgriGuru

AgriGuru is a Streamlit web application designed to provide farmers with valuable insights and decision-making tools. It leverages various APIs and data sources to offer location-specific information on weather, soil, market prices, and crop suitability. An integrated AI chatbot allows users to ask questions in text or voice in their regional languages.

## Features

- **Location-Aware Insights:** Automatically detects user location (with permission) to provide tailored information.
- **Weather Forecast:** 7-day weather forecast including temperature, precipitation, soil moisture, etc., powered by Tomorrow.io.
- **Local Analysis with Maps:** Interactive maps (Google Maps or Leaflet) displaying location pins, satellite overlays, soil data, pH levels, and crop suitability suggestions.
- **Market Price Analysis:** Fetches and displays the latest mandi (market) prices for key crops in the user's region by scraping Agmarknet.gov.in or other public sources.
- **AI Chatbot:**
    - Supports text and voice input (multilingual speech-to-text using IndicConformer/Whisper).
    - Classifies user queries (weather, crop, soil, market, general).
    - Provides text and voice responses (TTS using Coqui TTS or gTTS).

## Project Structure

```
AgriGuru/
 ├── app.py                 # Main Streamlit application
 ├── modules/               # Core logic modules
 │   ├── location.py        # Location detection and geocoding
 │   ├── weather.py         # Weather data fetching and display
 │   ├── maps.py            # Map generation and overlays
 │   ├── market.py          # Market price scraping and analysis
 │   ├── chatbot.py         # AI chatbot functionalities
 ├── static/                # Static assets
 │   ├── icons/             # Icons for UI elements
 │   ├── images/            # Images used in the app
 ├── .env                   # Environment variables (API keys, etc.)
 ├── requirements.txt       # Python dependencies
 └── README.md              # Project overview and setup instructions
```

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd AgriGuru
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables:**
    -   Rename `.env.example` to `.env` (if an example is provided) or create a new `.env` file.
    -   Add your API keys and other necessary configurations:
        ```env
        GOOGLE_MAPS_API_KEY="YOUR_GOOGLE_MAPS_API_KEY"
        TOMORROW_IO_API_KEY="YOUR_TOMORROW_IO_API_KEY"
        # Add other keys as needed
        ```

5.  **Run the Streamlit application:**
    ```bash
    streamlit run app.py
    ```

## Key Technologies

-   **Frontend:** Streamlit
-   **Location:** Browser Geolocation, Google Maps Geocoding API / OpenStreetMap Nominatim
-   **Weather:** Tomorrow.io API
-   **Maps:** Google Maps Embed / Leaflet (Folium)
-   **Soil Data:** ICAR, SoilGrids, or other public/static sources
-   **Market Prices:** Web scraping (e.g., Agmarknet.gov.in) with BeautifulSoup
-   **Speech-to-Text (ASR):** IndicConformer, OpenAI Whisper
-   **Text Processing/Correction:** Indic T5, mBART
-   **Text-to-Speech (TTS):** Coqui TTS, gTTS
-   **Data Visualization:** Plotly

## Contributing

[Details on how to contribute to the project, if applicable]

## License

[Specify the project license, e.g., MIT License]
```
