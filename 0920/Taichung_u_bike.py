import requests
import pandas as pd

def get_taichung_ubike_data():
    """
    Fetches real-time station data for YouBike 2.0 from the Taichung City Government's open data API.

    Returns:
        pandas.DataFrame: A DataFrame containing the YouBike station data, or None if it fails.
    """
    api_url = "https://datacenter.taichung.gov.tw/swagger/OpenData/bc27c2f7-6ed7-4f1a-b3cc-1a3cc9cda34e"
    print(f"Fetching data from the following URL...\n{api_url}")

    try:
        response = requests.get(api_url)
        response.raise_for_status()
        
        # Parse JSON
        data = response.json()
        print("Data fetched successfully!")
        
        # Convert into DataFrame
        df = pd.DataFrame(data)
        return df

    except requests.exceptions.RequestException as e:
        print(f"Error: API request failed - {e}")
        return None
    except ValueError as e:
        print(f"Error: Could not parse the returned data - {e}")
        return None

# --- Main program execution ---
if __name__ == "__main__":
    ubike_dataframe = get_taichung_ubike_data()
    
    if ubike_dataframe is not None:
        print("\nSuccessfully converted data to DataFrame.")
        print("-----------------------------------")
        print("Here is a preview of the first 5 rows:")
        
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 200)
        print(ubike_dataframe.head())

        # --- Save to CSV instead of Excel ---
        try:
            output_filename = 'taichung_ubike_data.csv'
            ubike_dataframe.to_csv(output_filename, index=False, encoding="utf-8-sig")
            print("\n-----------------------------------")
            print(f"Data has been successfully saved to '{output_filename}'")
            print("-----------------------------------")
        except Exception as e:
            print(f"\nError: A problem occurred while saving the file - {e}")
