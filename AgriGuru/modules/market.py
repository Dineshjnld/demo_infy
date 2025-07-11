import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import plotly.express as px
import re

# --- Agmarknet Scraper ---
# Attempting a more direct approach if possible, but Agmarknet is notoriously difficult.
# This version tries to mimic the form submission for the Datewise Commodity Report.

AGMARKNET_URL = "https://agmarknet.gov.in/PriceAndArrivals/DatewiseCommodityReport.aspx"
# Headers to mimic a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive',
    'Referer': 'https://agmarknet.gov.in/PriceAndArrivals/DatewiseCommodityReport.aspx', # Important for some sites
    'DNT': '1', # Do Not Track
    'Upgrade-Insecure-Requests': '1'
}

# These lists would ideally be dynamically scraped from Agmarknet dropdowns.
# For now, providing a limited static list. Users might need to input exact names.
# The actual values for dropdowns on Agmarknet are often numerical IDs, not text names.
# This scraper will be simplified and assume text names can be somehow mapped or used.

STATIC_STATES_MAP = {
    # This map would need to be populated with exact "value" attributes from Agmarknet's State dropdown
    # Example: "Andhra Pradesh": "AP", "Uttar Pradesh": "UP" (These are illustrative, not actual values)
    # For a robust solution, scraping these values is essential.
    "DELHI": "DL", # This is a guess, actual value needed
    "UTTAR PRADESH": "UP",
    "MAHARASHTRA": "MH",
    "PUNJAB": "PB",
    "RAJASTHAN": "RJ",
    "HARYANA": "HR",
    # Add more as needed, or implement dynamic scraping for these
}

STATIC_COMMODITIES_MAP = {
    # Similar to states, these are illustrative. Actual values might be IDs.
    "WHEAT": "2", # Guess
    "RICE": "1",  # Guess
    "POTATO": "43",
    "ONION": "44",
    "TOMATO": "45",
    "COTTON": "10",
    "MAIZE": "4",
    # Add more or implement dynamic scraping
}


def get_hidden_form_fields(session, url):
    """Fetches hidden ASP.NET form fields like __VIEWSTATE."""
    try:
        response = session.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        viewstate = soup.find('input', {'name': '__VIEWSTATE'})
        viewstategenerator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
        eventvalidation = soup.find('input', {'name': '__EVENTVALIDATION'})

        fields = {}
        if viewstate: fields['__VIEWSTATE'] = viewstate['value']
        if viewstategenerator: fields['__VIEWSTATEGENERATOR'] = viewstategenerator['value']
        if eventvalidation: fields['__EVENTVALIDATION'] = eventvalidation['value']
        return fields
    except requests.exceptions.RequestException as e:
        # st.error(f"Error fetching initial page from Agmarknet: {e}")
        return {"error": f"Error fetching initial page: {e}"}
    except Exception as e:
        # st.error(f"Error parsing initial page: {e}")
        return {"error": f"Error parsing initial page: {e}"}


def scrape_agmarknet_prices(state_name, commodity_name, report_date_str):
    """
    Attempts to scrape market price data from Agmarknet.
    Args:
        state_name (str): Name of the state (must match a key in STATIC_STATES_MAP or be the exact form value).
        commodity_name (str): Name of the commodity (similarly, must map or be exact value).
        report_date_str (str): Date in 'DD/MM/YYYY' format (as Agmarknet form expects).
    Returns:
        dict: {"data": pd.DataFrame or None, "error": str or None}
    """
    # Use a session to persist cookies if Agmarknet uses them
    session = requests.Session()

    initial_fields = get_hidden_form_fields(session, AGMARKNET_URL)
    if initial_fields.get("error"):
        return {"data": None, "error": initial_fields["error"]}
    if not all(k in initial_fields for k in ['__VIEWSTATE', '__VIEWSTATEGENERATOR', '__EVENTVALIDATION']):
        return {"data": None, "error": "Could not retrieve all necessary hidden fields from Agmarknet. Site structure might have changed."}

    # Map state and commodity names to their form values (this is a simplification)
    # A real implementation would need to get these values from the website's dropdowns.
    # For this example, we'll assume the user provides names that are keys in our static maps,
    # or that these names are directly usable (less likely for Agmarknet).

    # Attempt to use mapped values, otherwise use the provided names directly (less reliable)
    # Agmarknet's dropdowns are complex; state might trigger district, then commodity, etc.
    # This simplified version assumes we can directly set state, commodity, and date.

    # These are example IDs for dropdowns. Actual IDs need to be inspected from Agmarknet.
    # ddlState, ddlCommodity, txtDate, btnSubmit
    form_data = {
        **initial_fields,
        'ctl00$ddlState': state_name, # This should be the 'value' from the dropdown
        'ctl00$ddlCommodity': commodity_name, # This should be the 'value'
        'ctl00$txtDate': report_date_str,
        'ctl00$btnSubmit': 'View', # Value of the submit button
        # Other fields might be required depending on the form's complexity and dependencies.
        # E.g., ddlDistrict, ddlMarket - these are often populated dynamically.
        # This scraper is simplified and omits dynamic field handling.
        'ctl00$ddlDistrict': '0', # Often '0' for all districts or requires specific ID
        'ctl00$ddlMarket': '0',   # Often '0' for all markets or requires specific ID
    }

    try:
        # st.info(f"Submitting form to Agmarknet with State: {state_name}, Comm: {commodity_name}, Date: {report_date_str}")
        response = session.post(AGMARKNET_URL, data=form_data, headers=HEADERS, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Look for the main data table. The ID 'ctl00_cphBody_gridRecords' is a common pattern in ASP.NET.
        # This ID needs to be verified by inspecting the Agmarknet page after a successful form submission.
        table = soup.find('table', {'id': 'ctl00_cphBody_gridRecords'})

        if not table:
            # Fallback: try to find any table that looks like a data table
            tables = soup.find_all('table', {'class': 'table'}) # Common class for tables
            if not tables:
                tables = soup.find_all('table') # Last resort

            # Heuristic: pick a table with a good number of rows and cells
            best_table = None
            max_cells = 0
            for t in tables:
                rows = t.find_all('tr')
                if len(rows) > 1: # At least a header and one data row
                    cells = len(rows[0].find_all(['th', 'td']))
                    if cells > 3 and len(rows) * cells > max_cells: # Arbitrary threshold for a "data-like" table
                        max_cells = len(rows) * cells
                        best_table = t
            table = best_table

        if table:
            df = pd.read_html(str(table), header=0)[0] # header=0 assumes first row is header

            # Data Cleaning
            df.dropna(how='all', inplace=True) # Drop rows that are all NaN
            df.dropna(axis=1, how='all', inplace=True) # Drop columns that are all NaN

            # Standardize column names (similar to previous mock)
            df.columns = [str(col).strip() for col in df.columns] # Ensure string type and strip spaces
            df.columns = [re.sub(r'[^A-Za-z0-9_]+', '_', col).strip('_').lower() for col in df.columns]

            # Rename common columns for consistency (add more mappings as identified)
            rename_map = {
                'sl_no': 's_no', 's_n': 's_no',
                'min_price_rs_quintal': 'min_price', 'min_price_quintal': 'min_price',
                'max_price_rs_quintal': 'max_price', 'max_price_quintal': 'max_price',
                'modal_price_rs_quintal': 'modal_price', 'modal_price_quintal': 'modal_price',
                'price_date': 'date', 'report_date': 'date',
                'commodity_name': 'commodity',
                'district_name': 'district',
                'market_name': 'market'
            }
            df.rename(columns=lambda c: rename_map.get(c, c), inplace=True)

            # Convert price columns to numeric, coercing errors
            price_cols = ['min_price', 'max_price', 'modal_price']
            for col in price_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            if df.empty:
                 return {"data": None, "error": "No data found in the table after parsing, or table was empty."}
            return {"data": df, "error": None}
        else:
            # Check for common "no records found" messages on Agmarknet
            no_records_msg = soup.find(text=re.compile(r"No Record Found|No Data Found", re.IGNORECASE))
            if no_records_msg:
                return {"data": None, "error": f"Agmarknet: {no_records_msg.strip()}"}

            # If no specific message, give a generic one
            # For debugging, one might save response.text to a file here.
            # with open("agmarknet_response.html", "w", encoding="utf-8") as f: f.write(response.text)
            return {"data": None, "error": "Could not find the data table in Agmarknet response. The site structure may have changed, or the query returned no results page without a clear message."}

    except requests.exceptions.Timeout:
        return {"data": None, "error": "Agmarknet request timed out."}
    except requests.exceptions.RequestException as e:
        return {"data": None, "error": f"Network error during Agmarknet scraping: {e}"}
    except pd.errors.EmptyDataError:
        return {"data": None, "error": "No tables found in the HTML response from Agmarknet."}
    except Exception as e:
        # Log the full error for debugging if possible
        # print(f"Unexpected Agmarknet scraping error: {e}", traceback.format_exc())
        return {"data": None, "error": f"An unexpected error occurred during Agmarknet scraping: {str(e)}"}


# --- Display Functions ---
def display_market_prices(user_location):
    """
    Allows user to select commodity and displays market prices.
    """
    if not user_location or not user_location.get("district") or not user_location.get("state"):
        # st.warning("District and State information needed to fetch market prices.") # UI feedback in main app
        return {"error": "District and State information missing from user_location."}


    # For this enhanced scraper, we need to map state/commodity names to values Agmarknet expects,
    # or the user must input them very precisely if we don't have mappings.
    # The STATIC_STATES_MAP and STATIC_COMMODITIES_MAP are placeholders for this.
    # A fully robust solution would involve dynamically scraping these mappings from Agmarknet's dropdowns.

    st.subheader(f"💹 Market Prices (Agmarknet)")
    st.caption("Note: Agmarknet scraping can be unreliable due to site changes. Data might be limited by available static mappings for state/commodity.")

    # User Inputs
    # For a better UX, these would be dynamic dropdowns based on Agmarknet.
    # Using text input for now for simplicity with static maps.

    # Use keys from static map as default suggestions, but allow free text
    state_input = st.selectbox("Select State:", options=list(STATIC_STATES_MAP.keys()), index=0)
    commodity_input = st.selectbox("Select Commodity:", options=list(STATIC_COMMODITIES_MAP.keys()), index=0)

    # Use user_location as a hint if state_input matches
    if user_location.get("state","").upper() in STATIC_STATES_MAP:
        try:
            state_idx = list(STATIC_STATES_MAP.keys()).index(user_location.get("state","").upper())
            state_input = st.selectbox("Select State:", options=list(STATIC_STATES_MAP.keys()), index=state_idx, key="state_sb")
        except ValueError:
            pass # Keep default if not found

    selected_date = st.date_input("Select Date for Prices:", datetime.date.today(), max_value=datetime.date.today())

    if st.button(f"Fetch Prices for {commodity_input} in {state_input}"):
        if not state_input or not commodity_input:
            st.error("Please select a state and commodity.")
            return

        # Get the mapped values if they exist, otherwise use the input directly (less reliable)
        state_form_value = STATIC_STATES_MAP.get(state_input.upper(), state_input)
        commodity_form_value = STATIC_COMMODITIES_MAP.get(commodity_input.upper(), commodity_input)

        # Agmarknet form expects date as DD/MM/YYYY
        date_for_agmarknet = selected_date.strftime("%d/%m/%Y")

        with st.spinner(f"Scraping Agmarknet for {commodity_input} in {state_input} for {date_for_agmarknet}..."):
            result = scrape_agmarknet_prices(state_form_value, commodity_form_value, date_for_agmarknet)

        price_df = result.get("data")
        error_msg = result.get("error")

        if error_msg:
            st.error(f"Scraper Error: {error_msg}")

        if price_df is not None and not price_df.empty:
            st.success(f"Data found for {commodity_input} in {state_input} on {date_for_agmarknet}")

            # Filter by user's district if district column exists and matches
            # This is an approximation as the form was simplified.
            # A more precise scrape would involve selecting the district in the form itself.
            district_col_options = ['district', 'district_name'] # Possible column names for district
            actual_district_col = next((col for col in district_col_options if col in price_df.columns), None)

            if actual_district_col and user_location.get("district"):
                user_district_name = user_location["district"]
                # Case-insensitive match for district
                filtered_df = price_df[price_df[actual_district_col].str.contains(user_district_name, case=False, na=False)]
                if not filtered_df.empty:
                    st.info(f"Showing data filtered for district: {user_district_name}")
                    display_df = filtered_df
                else:
                    st.info(f"No specific data for district '{user_district_name}' found in results for {state_input}. Showing all for state.")
                    display_df = price_df
            else:
                display_df = price_df

            # Select and order columns for display
            # Common columns expected: s_no, district, market, commodity, variety, grade, min_price, max_price, modal_price, date
            preferred_cols_order = [
                's_no', 'district', 'market', 'commodity', 'variety', 'grade',
                'min_price', 'max_price', 'modal_price', 'date'
            ]
            display_cols = [col for col in preferred_cols_order if col in display_df.columns]
            # Add any other columns that might have been scraped but are not in preferred_cols_order
            other_cols = [col for col in display_df.columns if col not in display_cols]
            final_display_cols = display_cols + other_cols

            st.dataframe(display_df[final_display_cols].reset_index(drop=True), use_container_width=True)

            # Plotting (if modal_price is available)
            plot_df = display_df.copy() # Use the (potentially district-filtered) df for plotting
            if 'modal_price' in plot_df.columns and plot_df['modal_price'].notna().any() and \
               ('market' in plot_df.columns or 'market_name' in plot_df.columns):

                market_col_name = 'market' if 'market' in plot_df.columns else 'market_name'
                plot_df.dropna(subset=['modal_price', market_col_name], inplace=True)

                if not plot_df.empty:
                    fig_market_prices = px.bar(
                        plot_df,
                        x=market_col_name,
                        y='modal_price',
                        color='variety' if 'variety' in plot_df.columns else None,
                        title=f"Modal Prices (Rs./Quintal) for {commodity_input} in {state_input} (District: {user_location.get('district', 'All')})",
                        labels={'modal_price': 'Modal Price (Rs./Quintal)', market_col_name: 'Market Name'},
                        hover_data=[col for col in ['min_price', 'max_price', 'date', 'commodity', 'grade'] if col in plot_df.columns]
                    )
                    fig_market_prices.update_layout(xaxis_tickangle=-45)
                    st.plotly_chart(fig_market_prices, use_container_width=True)
                else:
                    st.info(f"Not enough data to plot modal prices after filtering for {commodity_input}.")
            else:
                st.info("Modal price or market name column not found/sufficient in the scraped data for plotting.")

        elif not error_msg: # No error, but also no data
             st.info(f"No market data found by the scraper for {commodity_input} in {state_input} for the selected date.")


if __name__ == '__main__':
    # Example Usage (for testing module standalone with Streamlit)
    # To run this test: streamlit run AgriGuru/modules/market.py
    st.set_page_config(layout="wide")
    st.title("Test: AgriGuru Market Module")

    # Mock user location
    mock_user_loc = {
        "latitude": 28.6139, "longitude": 77.2090,
        "village": "Mock Village", "district": "North Delhi", "state": "Delhi", "country": "India"
    }

    st.sidebar.info(f"Location: {mock_user_loc['district']}, {mock_user_loc['state']}")

    display_market_prices(mock_user_loc)

    st.markdown("---")
    st.header("Test without location:")
    display_market_prices({})

    st.markdown("---")
    st.header("Test with different commodity (e.g., Rice):")
    # To test this, you'd manually change the input in the UI when running the Streamlit app.
    # This section is more of a reminder for manual testing.
    st.info("To test different commodities, please use the input field above when running this script with Streamlit.")

```
