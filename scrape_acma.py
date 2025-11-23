import requests
from bs4 import BeautifulSoup
import json
import datetime
from urllib.parse import urljoin
import time

# Configuration
START_URL = "https://www.acma.gov.au/register-licensed-carriers"
OUTPUT_FILE = "package_show.json"

def parse_acma_date(date_str):
    """Parses dates like '15-Sep-04' into 'YYYY-MM-DD'."""
    if not date_str or not date_str.strip():
        return ""
    try:
        dt = datetime.datetime.strptime(date_str.strip(), "%d-%b-%y")
        # Fix for 2-digit years (ACMA data starts ~1997)
        if dt.year > datetime.datetime.now().year:
            dt = dt.replace(year=dt.year - 100)
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return date_str

def scrape_all_pages():
    current_url = START_URL
    all_resources = []
    page_count = 1

    print(f"Starting scrape of {START_URL}...")

    while current_url:
        print(f"Scraping Page {page_count}...", end="\r")
        
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(current_url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 1. Find the table
            table = soup.find('table')
            if not table:
                print(f"\nWarning: No table found on page {page_count}. Ending scrape.")
                break

            # 2. Extract rows
            rows = table.find_all('tr')[1:] # Skip header
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 5:
                    continue

                # Extract data fields
                licence_number = cols[0].get_text(strip=True)
                carrier_name = cols[1].get_text(strip=True)
                status = cols[3].get_text(strip=True)
                date_granted = cols[4].get_text(strip=True)
                
                # Find PDF link
                pdf_link = "#"
                if len(cols) > 6:
                    link_tag = cols[6].find('a')
                    if link_tag and link_tag.get('href'):
                        pdf_link = urljoin(current_url, link_tag.get('href'))

                resource = {
                    "name": f"Licence {licence_number} - {carrier_name}",
                    "url": pdf_link,
                    "created": parse_acma_date(date_granted),
                    "format": "PDF",
                    "size": "Unknown",
                    "status": status
                }
                all_resources.append(resource)

            # 3. Find the "Next" button to continue loop
            next_link = soup.find('a', rel='next') # Standard HTML pagination attribute
            
            # Fallback for ACMA specific classes if rel='next' is missing
            if not next_link:
                next_link = soup.find('a', class_='pager__link--next')

            if next_link and next_link.get('href'):
                current_url = urljoin(current_url, next_link.get('href'))
                page_count += 1
                time.sleep(0.5) # Be polite to the server
            else:
                current_url = None # No more pages, exit loop

        except Exception as e:
            print(f"\nError on page {page_count}: {e}")
            break

    # Save result
    output_data = {
        "success": True,
        "result": {
            "title": "Carrier Licences (Live Scrape)",
            "metadata_modified": datetime.datetime.now().isoformat(),
            "resources": all_resources
        }
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=4)

    print(f"\n\nSuccess! Scraped {page_count} pages.")
    print(f"Found {len(all_resources)} licenses (including Telstra).")
    print(f"Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    scrape_all_pages()