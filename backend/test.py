import json
import csv

# Load JSON from a file
with open('api_response.json', 'r', encoding='utf-8') as json_file:
    data = json.load(json_file)

# Extract the rows list
rows = data["rows"]

# Get CSV headers from the keys of the first item
headers = rows[0].keys()

# Write to CSV file
with open('campaign_data.csv', 'w', newline='', encoding='utf-8') as csv_file:
    writer = csv.DictWriter(csv_file, fieldnames=headers)
    writer.writeheader()       # write headers
    writer.writerows(rows)     # write all rows

print("✅ CSV file 'campaign_data.csv' created successfully.")