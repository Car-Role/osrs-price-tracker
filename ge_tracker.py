import requests
import time
from datetime import datetime

class GETracker:
    def __init__(self):
        self.base_url = "https://prices.runescape.wiki/api/v1/osrs"
        self.headers = {
            "User-Agent": "OSRS GE Tracker - Python Script"
        }
        self.items = {}

    def add_item(self, item_name):
        item_id = self.get_item_id(item_name)
        if item_id:
            self.items[item_name] = item_id
            print(f"Added {item_name} to tracking list.")
        else:
            print(f"Could not find item: {item_name}")

    def get_item_id(self, item_name):
        mapping_url = f"{self.base_url}/mapping"
        response = requests.get(mapping_url, headers=self.headers)
        if response.status_code == 200:
            items = response.json()
            for item in items:
                if item["name"].lower() == item_name.lower():
                    return item["id"]
        return None

    def fetch_prices(self):
        if not self.items:
            print("No items to track. Add items using add_item() method.")
            return {}

        latest_url = f"{self.base_url}/latest"
        response = requests.get(latest_url, headers=self.headers)
        if response.status_code == 200:
            data = response.json()["data"]
            results = {}
            for item_name, item_id in self.items.items():
                if str(item_id) in data:
                    item_data = data[str(item_id)]
                    results[item_name] = {
                        "high": item_data['high'],
                        "low": item_data['low'],
                        "last_updated": datetime.fromtimestamp(item_data['highTime'])
                    }
                else:
                    print(f"No data available for {item_name}")
            return results
        else:
            print("Failed to fetch prices. Please try again later.")
            return {}

    def start_tracking(self, interval=5):
        print(f"Starting price tracker. Updating every {interval} seconds.")
        while True:
            self.fetch_prices()
            time.sleep(interval)

if __name__ == "__main__":
    tracker = GETracker()
    
    # Add items to track
    tracker.add_item("Abyssal whip")
    tracker.add_item("Dragon bones")
    tracker.add_item("Bandos chestplate")
    
    # Start tracking prices
    tracker.start_tracking()