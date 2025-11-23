import json
import math
import datetime

# Configuration
INPUT_FILE = 'package_show.json'
OUTPUT_FILE = 'carriers.html'

def convert_size(size_bytes):
    """Converts raw bytes to human readable format (KB, MB, etc)."""
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])

def format_date(date_str):
    """Formats ISO date strings to YYYY-MM-DD."""
    try:
        # Attempt to parse ISO format
        dt = datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d')
    except:
        return date_str

def generate_html():
    print(f"Reading {INPUT_FILE}...")
    
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find {INPUT_FILE}. Make sure it is in the same folder.")
        return

    # Extract the list of resources (licenses)
    try:
        resources = data['result']['resources']
        dataset_title = data['result'].get('title', 'Carrier Licences Register')
        last_updated = format_date(data['result'].get('metadata_modified', ''))
    except KeyError:
        print("Error: JSON structure does not match expected 'package_show' format.")
        return

    print(f"Found {len(resources)} records. Generating HTML...")

    # Start building the HTML content
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{dataset_title}</title>
        
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdn.datatables.net/1.13.4/css/dataTables.bootstrap5.min.css" rel="stylesheet">
        
        <style>
            body {{ background-color: #f8f9fa; padding-top: 20px; }}
            .container {{ background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .footer {{ margin-top: 40px; font-size: 0.9em; color: #6c757d; text-align: center; }}
            .btn-download {{ font-size: 0.85em; }}
        </style>
    </head>
    <body>

    <div class="container">
        <div class="row mb-4">
            <div class="col">
                <h1 class="display-6">{dataset_title}</h1>
                <p class="lead text-muted">Searchable register of Australian Carrier Licences.</p>
                <span class="badge bg-secondary">Last Updated: {last_updated}</span>
                <span class="badge bg-info text-dark">Total Records: {len(resources)}</span>
            </div>
        </div>

        <table id="licenseTable" class="table table-striped table-hover" style="width:100%">
            <thead>
                <tr>
                    <th>License Name</th>
                    <th>Date Created</th>
                    <th>File Size</th>
                    <th>Format</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
    """

    # Loop through JSON data and add rows
    for item in resources:
        name = item.get('name', 'Unknown')
        url = item.get('url', '#')
        date = format_date(item.get('created', ''))
        
        # Handle size (sometimes null or string)
        raw_size = item.get('size')
        if raw_size and str(raw_size).isdigit():
            fmt_size = convert_size(int(raw_size))
        else:
            fmt_size = "N/A"
            
        fmt_format = item.get('format', 'N/A').upper()

        html_content += f"""
                <tr>
                    <td>{name}</td>
                    <td>{date}</td>
                    <td data-order="{raw_size if raw_size else 0}">{fmt_size}</td>
                    <td><span class="badge bg-light text-dark border">{fmt_format}</span></td>
                    <td>
                        <a href="{url}" target="_blank" class="btn btn-primary btn-sm btn-download">
                            Download
                        </a>
                    </td>
                </tr>
        """

    # Finish HTML
    html_content += """
            </tbody>
        </table>

        <div class="footer">
            <p>Generated from open data sources.</p>
        </div>
    </div>

    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.4/js/dataTables.bootstrap5.min.js"></script>

    <script>
        $(document).ready(function () {
            $('#licenseTable').DataTable({
                "pageLength": 25,
                "order": [[ 0, "asc" ]], // Sort by Name by default
                "language": {
                    "search": "Filter records:"
                }
            });
        });
    </script>

    </body>
    </html>
    """

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html_content)
        
    print(f"Success! Generated {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_html()