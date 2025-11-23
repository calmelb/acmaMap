import pandas as pd
import json
import os
import time

def create_fixed_map():
    print("--- GENERATING FIXED MAP (Type-Safe Merge) ---")
    
    files = {
        'site': 'site.csv',
        'device': 'device_details.csv',
        'licence': 'licence.csv',
        'client': 'client.csv',
        'subservice': 'licence_subservice.csv'
    }

    # Verify Files
    for key, f in files.items():
        if not os.path.exists(f):
            print(f"CRITICAL ERROR: Missing {f}")
            return

    print("1. Loading Data...")
    
    # helper to force string types to prevent merge errors
    dtype_options = {
        'SITE_ID': str,
        'LICENCE_NO': str,
        'CLIENT_NO': str,
        'SS_ID': str
    }

    try:
        # Load SITE
        df_site = pd.read_csv(files['site'], dtype=str, usecols=['SITE_ID', 'LATITUDE', 'LONGITUDE', 'NAME'])
        df_site = df_site.rename(columns={'NAME': 'SITE_NAME'})
        
        # Load DEVICE
        df_device = pd.read_csv(files['device'], dtype=str, usecols=['SITE_ID', 'LICENCE_NO', 'FREQUENCY'])
        df_device = df_device.dropna(subset=['SITE_ID'])
        
        # Load LICENCE
        df_licence = pd.read_csv(files['licence'], dtype=str, usecols=['LICENCE_NO', 'CLIENT_NO', 'SS_ID'])
        
        # Load CLIENT
        df_client = pd.read_csv(files['client'], dtype=str, usecols=['CLIENT_NO', 'LICENCEE'])
        
        # Load SUBSERVICE
        df_subservice = pd.read_csv(files['subservice'], dtype=str, usecols=['SS_ID', 'SS_NAME'])

    except ValueError as e:
        print(f"Error reading CSVs: {e}")
        print("Try removing the 'dtype=str' argument if this persists, but type mismatch is likely the issue.")
        return

    print("2. Merging Tables...")
    
    # 1. Device -> Licence
    # We use LEFT join to keep devices even if licence info is missing
    merged = pd.merge(df_device, df_licence, on='LICENCE_NO', how='left')
    
    # 2. -> Client
    merged = pd.merge(merged, df_client, on='CLIENT_NO', how='left')
    
    # 3. -> Subservice
    merged = pd.merge(merged, df_subservice, on='SS_ID', how='left')

    # Fill Unknowns
    merged['LICENCEE'] = merged['LICENCEE'].fillna('Unknown Carrier')
    merged['SS_NAME'] = merged['SS_NAME'].fillna('Unknown Service')
    
    print(f"   Matched {len(merged)} records.")

    # --- CLASSIFICATION & SORTING ---
    def get_primary_carrier(carrier_text):
        ct = str(carrier_text).upper()
        if 'STARLINK' in ct or 'SPACEX' in ct: return 'Starlink'
        if 'TELSTRA' in ct: return 'Telstra'
        if 'OPTUS' in ct: return 'Optus'
        if 'VODAFONE' in ct or 'TPG' in ct: return 'Vodafone/TPG'
        if 'NBN' in ct: return 'NBN'
        if 'BROADCAST' in ct or 'ABC' in ct or 'SBS' in ct: return 'Broadcasters'
        return 'Other'

    def smart_sort_carriers(carrier_list):
        unique = sorted(list(set(carrier_list)))
        majors = ['STARLINK', 'SPACEX', 'TELSTRA', 'OPTUS', 'VODAFONE', 'TPG', 'NBN']
        priority = [c for c in unique if any(m in c.upper() for m in majors)]
        others = [c for c in unique if not any(m in c.upper() for m in majors)]
        return '; '.join((priority + others)[:50])

    # Format Frequency (e.g., 2600000000 -> 2.6G)
    def summarize_freqs(freq_list):
        try:
            # Convert back to float for sorting, then format
            floats = sorted([float(f) for f in freq_list if pd.notnull(f) and f != 'nan'])
            unique = sorted(list(set(floats)))[:12] # Top 12 freqs
            
            res = []
            for val in unique:
                if val >= 1_000_000_000: res.append(f"{val/1_000_000_000:.1f}G")
                elif val >= 1_000_000: res.append(f"{int(val/1_000_000)}M")
                else: res.append(str(int(val)))
            return ', '.join(res)
        except:
            return ""

    print("3. Aggregating by Site...")
    grouped = merged.groupby('SITE_ID').agg({
        'LICENCEE': [smart_sort_carriers, lambda x: ';'.join(set(get_primary_carrier(c) for c in x))], 
        'SS_NAME': lambda x: '; '.join(sorted(set(str(s) for s in x))[:20]),
        'FREQUENCY': summarize_freqs,
        'LICENCE_NO': 'count'
    }).reset_index()

    grouped.columns = ['SITE_ID', 'CARRIERS_TEXT', 'FILTER_TAGS', 'SERVICES_TEXT', 'FREQ_TEXT', 'LICENCE_COUNT']

    # Attach Location
    # Convert Coords to numeric for mapping, keep ID as string for joining
    df_site['LATITUDE'] = pd.to_numeric(df_site['LATITUDE'], errors='coerce')
    df_site['LONGITUDE'] = pd.to_numeric(df_site['LONGITUDE'], errors='coerce')
    
    final_df = pd.merge(df_site, grouped, on='SITE_ID', how='inner')
    final_df = final_df.dropna(subset=['LATITUDE', 'LONGITUDE'])

    print(f"4. Generating Map for {len(final_df)} sites...")

    features = []
    for _, row in final_df.iterrows():
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [round(row['LONGITUDE'], 5), round(row['LATITUDE'], 5)]
            },
            "properties": {
                "n": str(row['SITE_NAME']),
                "id": str(row['SITE_ID']),
                "c": row['CARRIERS_TEXT'],
                "tags": row['FILTER_TAGS'],
                "s": row['SERVICES_TEXT'],
                "f": row['FREQ_TEXT'],
                "qn": str(row['LICENCE_COUNT'])
            }
        })

    geojson = { "type": "FeatureCollection", "features": features }

    # Write Data
    js_filename = 'sites_final.js'
    with open(js_filename, 'w') as f:
        f.write("window.siteData = ")
        json.dump(geojson, f)
        f.write(";")

    # Write HTML
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Australian RF Site Map</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.Default.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet-search@3.0.0/dist/leaflet-search.src.css" />

    <style>
        body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
        #map {{ width: 100vw; height: 100vh; }}
        
        .filter-control {{
            background: white; padding: 12px; border-radius: 4px;
            box-shadow: 0 1px 5px rgba(0,0,0,0.4); font-size: 14px;
        }}
        .filter-control select {{ padding: 6px; font-size: 14px; margin-top: 5px; width: 100%; }}
        
        .leaflet-popup-content-wrapper {{ max-height: 450px; overflow-y: auto; }}
        .leaflet-popup-content {{ min-width: 280px; }}
        
        h3 {{ margin: 0 0 5px 0; font-size: 16px; color: #333; }}
        hr {{ border: 0; border-top: 1px solid #eee; margin: 8px 0; }}
        .carrier-list {{ padding-left: 20px; margin: 5px 0; }}
        .carrier-list li {{ margin-bottom: 3px; color: #444; }}
        .info-box {{ background:#f8f9fa; padding:8px; border-radius:4px; border:1px solid #e9ecef; margin:8px 0; font-size: 0.9em; color: #555; }}
        .freq-tag {{ display: inline-block; background: #e2e6ea; padding: 2px 5px; border-radius: 3px; font-size: 0.8em; margin: 2px; }}
    </style>
</head>
<body>
    <div id="map"></div>
    
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js"></script>
    <script src="https://unpkg.com/leaflet-search@3.0.0/dist/leaflet-search.src.js"></script>
    
    <script src="{js_filename}?t={int(time.time())}"></script>

    <script>
        var map = L.map('map', {{ preferCanvas: true }}).setView([-35.2809, 149.1300], 11);
        L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 19,
            attribution: '&copy; OpenStreetMap and the Australian Communications and Media Authority (ACMA)'
        }}).addTo(map);

        var markers = L.markerClusterGroup({{ chunkedLoading: true }});
        var allLayers = [];

        if (typeof window.siteData !== 'undefined') {{
            
            var geoJsonLayer = L.geoJSON(window.siteData, {{
                pointToLayer: function (feature, latlng) {{ return L.marker(latlng); }},
                onEachFeature: function (feature, layer) {{
                    var p = feature.properties;
                    var carriers = p.c.split('; ').map(c => `<li>${{c}}</li>`).join('');
                    var freqs = p.f ? p.f.split(', ').map(f => `<span class="freq-tag">${{f}}</span>`).join('') : 'None listed';

                    var content = `
                        <h3>${{p.n}}</h3>
                        <div style="font-size: 0.85em; color: #666; margin-bottom: 5px;">
                            Site ID: ${{p.id}} &bull; ${{p.qn}} Transmitters
                        </div>
                        <hr>
                        <div class="info-box">
                            <strong>Frequencies:</strong><br>${{freqs}}
                        </div>
                        <div class="info-box">
                            <strong>Services:</strong><br>${{p.s}}
                        </div>
                        <strong>Carriers:</strong>
                        <ul class="carrier-list">${{carriers}}</ul>
                    `;
                    layer.bindPopup(content);
                }}
            }});

            allLayers = geoJsonLayer.getLayers();
            markers.addLayers(allLayers);
            map.addLayer(markers);

            var searchControl = new L.Control.Search({{
                layer: markers, propertyName: 'n', initial: false, zoom: 15,
                marker: {{ icon: false, animate: true, circle: {{ radius: 25, weight: 3, color: '#007bff', stroke: true, fill: false }} }}
            }});
            map.addControl(searchControl);

            var filterControl = L.control({{position: 'topright'}});
            filterControl.onAdd = function (map) {{
                var div = L.DomUtil.create('div', 'filter-control leaflet-bar');
                div.innerHTML = `
                    <strong>Filter Network</strong><br>
                    <select id="carrier_filter">
                        <option value="ALL">Show All Sites</option>
                        <option value="Starlink">Starlink / SpaceX</option>
                        <option value="Telstra">Telstra Only</option>
                        <option value="Optus">Optus Only</option>
                        <option value="Vodafone/TPG">Vodafone/TPG Only</option>
                        <option value="NBN">NBN Only</option>
                        <option value="Broadcasters">TV & Radio</option>
                    </select>
                `;
                L.DomEvent.disableClickPropagation(div);
                return div;
            }};
            filterControl.addTo(map);

            document.getElementById('carrier_filter').addEventListener('change', function(e) {{
                var selected = e.target.value;
                markers.clearLayers();
                
                if (selected === 'ALL') {{
                    markers.addLayers(allLayers);
                }} else {{
                    var filtered = allLayers.filter(function(layer) {{
                        var tags = layer.feature.properties.tags; 
                        return tags && tags.includes(selected);
                    }});
                    markers.addLayers(filtered);
                }}
            }});

        }} else {{
            alert("Error: {js_filename} could not be loaded.");
        }}
    </script>
</body>
</html>
"""
    with open('index.html', 'w') as f:
        f.write(html_content)

    print("SUCCESS! Created 'index.html' and 'sites_final.js'.")

if __name__ == "__main__":
    create_fixed_map()