import json
import os
from django.conf import settings

# Load JSON mapping from file=
json_path = os.path.join(settings.MEDIA_ROOT, 'country.json')

with open(json_path, "r") as f:
    country_map = json.load(f)

# Define function using the loaded JSON
def extract_country_name(code):
    # print("country_code :", code)
    return country_map.get(code, "Unknown")  # handles lowercase too