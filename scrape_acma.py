import requests
from bs4 import BeautifulSoup
import json
import datetime
import re
from urllib.parse import urljoin

# Configuration
SOURCE_URL = "https://www.acma.gov.au/register-licensed-carriers"
OUTPUT_FILE = "package_show.json"

def parse_acma_date(date_str):
    """Parses dates like '15-Sep-04' into 'YYYY-MM-DD'."""
    if not date_str or not date_str.strip():
        return ""
    try:
        # Parse format like 15-Sep-04
        dt = datetime.datetime.strptime(date_str.strip(), "%d-%b-%y")
        # Handle 2-digit year pivot (Python defaults to 1969-2068 split)
        # ACMA data starts from 1997, so standard pivot is generally fine.
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return date_str

def scrape_acma_register():
    print(f"Fetching live data from: {SOURCE_URL}")
    
    try:
        # Add a User-Agent to look like a real browser (good practice for scraping)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(SOURCE_URL, headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching website: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find the main table
    table = soup.find('table')
    if not table:
        print("Error: Could not find the register table on the page.")
        return

    resources = []
    rows = table.find_all('tr')[1:] # Skip header row

    print(f"Found {len(rows)} rows. Processing...")

    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 5:
            continue

        # Extract relevant columns based on standard ACMA table layout
        # 0: Number, 1: Name, 2: ACN, 3: Status, 4: Date Granted, 5: Surrendered Date, 6: PDF Link
        
        licence_number = cols[0].get_text(strip=True)
        carrier_name = cols[1].get_text(strip=True)
        status = cols[3].get_text(strip=True)
        date_granted = cols[4].get_text(strip=True)
        
        # Find the PDF link in the 'Carrier licence' column (usually index 6)
        pdf_link = "#"
        if len(cols) > 6:
            link_tag = cols[6].find('a')
            if link_tag and link_tag.get('href'):
                # Convert relative URL (/file/...) to absolute URL (https://acma...)
                pdf_link = urljoin(SOURCE_URL, link_tag.get('href'))

        # Filter: You can uncomment the next lines if you ONLY want 'Current' licenses
        # if "surrendered" in status.lower() or "cancelled" in status.lower():
        #     continue

        # Construct the resource object
        resource = {
            "name": f"Licence {licence_number} - {carrier_name}",
            "url": pdf_link,
            "created": parse_acma_date(date_granted),
            "format": "PDF",
            "size": "Unknown", # We don't know the file size without downloading it
            "status": status   # Extra field, won't hurt
        }
        resources.append(resource)

    # Create the final JSON structure expected by your site generator
    output_data = {
        "success": True,
        "result": {
            "title": "Carrier Licences (Live Scrape)",
            "metadata_modified": datetime.datetime.now().isoformat(),
            "resources": resources
        }
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=4)

    print(f"Successfully scraped {len(resources)} licenses.")
    print(f"Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    scrape_acma_register()