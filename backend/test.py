import requests
import csv

# API endpoint
url = "https://tracktheweb.online/admin_api/v1/report/build"

# API Key
api_key = "c1da605a864e6c74beb71d3a713e019c"

# Headers
headers = {
    "Api-Key": api_key,
    "Content-Type": "application/json"
}

# JSON body
body = {
    "range": {
        "from": "2024-07-22",
        "to": "2025-07-23",
        "timezone": "Europe/Amsterdam"
    },
    "columns": [
        "campaign", "campaign_id", "cost", "revenue", "profit",
        "clicks", "campaign_unique_clicks", "conversions", "roi_confirmed",
        "datetime", "lp_clicks", "cr", "lp_ctr"
    ],
    "metrics": [
        "clicks",
        "cost",
        "campaign_unique_clicks",
        "conversions",
        "roi_confirmed"
    ],
    "grouping": [
        "campaign_id"
    ],
    "filters": [],
    "summary": False,
    "limit": 100000,
    "offset": 0,
    "extended": True
}

# Send POST request
response = requests.post(url, headers=headers, json=body)

# Check response status
if response.status_code == 200:
    data = response.json()
    print(data)
    # Extract rows
    rows = data.get("rows", [])

    # Count unique campaign_id
    unique_campaign_ids = set(row.get("campaign_id") for row in rows if "campaign_id" in row)
    print(f"Number of unique campaign_id: {len(unique_campaign_ids)}")
    print(f"Unique campaign_id values: {unique_campaign_ids}")

    if not rows:
        print("No data returned.")
    else:
        # Get headers from the first row keys
        fieldnames = rows[0].keys()

        # Write to CSV
        with open("campaign_report.csv", "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print("Data written to campaign_report.csv")
else:
    print("Failed to fetch data:", response.status_code)
    print("Response:", response.text)
