import sys
import os
import time
import random
import atexit
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from django.db import transaction

# ---------------- CONFIG ---------------- #
API_BASE = "http://app.wijte.me/api/adset/status/"
MAX_RETRIES = 5
BASE_DELAY = 2
THROTTLE_DELAY = 0.5  # seconds between API calls
INTERVAL_SECONDS = 600  # scheduler interval (10 minutes)
LOG_FILE = "/tmp/apscheduler_output.txt"
# --------------------------------------- #

# ---------------- Logging Helper ---------------- #
def log(msg):
    """Write timestamped log to /tmp/apscheduler_output.txt"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {msg}\n")


# ---------------- Job Functions ---------------- #
def fetch_status(adset_id):
    """Fetch adset status from API with retries & exponential backoff."""
    url = f"{API_BASE}{adset_id}"
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 429:
                delay = BASE_DELAY * (2 ** attempt) + random.uniform(0, 1)
                log(f"WARNING: 429 received for {adset_id}, retrying in {delay:.2f}s")
                time.sleep(delay)
                continue

            response.raise_for_status()
            data = response.json()
            return data.get("status")  # "ACTIVE" or "PAUSED"

        except requests.RequestException as e:
            delay = BASE_DELAY * (2 ** attempt) + random.uniform(0, 1)
            log(f"WARNING: Error fetching {adset_id}: {e}. Retrying in {delay:.2f}s")
            time.sleep(delay)

    log(f"ERROR: Failed to fetch status for {adset_id} after {MAX_RETRIES} attempts")
    return None


def my_job():
    """Scheduler job: checks all adsets and updates DB only if needed"""
    log("INFO: Adset status check job started")

    # Import Django model here to avoid issues with autoreload
    from api.models import AdsetStatus

    adsets = AdsetStatus.objects.all()

    for adset in adsets:
        db_status = "ACTIVE" if adset.is_active else "PAUSED"

        if db_status == "PAUSED":
            log(f"INFO: Adset {adset.adset_id} is Paused in DB (skipping API)")
            continue

        api_status = fetch_status(adset.adset_id)
        if api_status is None:
            continue  # fetch_status already logged failure

        if api_status != db_status:
            with transaction.atomic():
                adset.is_active = api_status == "ACTIVE"
                adset.save(update_fields=["is_active"])
            log(f"INFO: Adset {adset.adset_id} updated DB -> {api_status}")
        else:
            log(f"INFO: Adset {adset.adset_id} already {db_status} (no change)")

        time.sleep(THROTTLE_DELAY)

    log("INFO: Adset status check job finished")


# ---------------- Scheduler Setup ---------------- #
RUN_MAIN = os.environ.get("RUN_MAIN") == "true"
if "runserver" in sys.argv and RUN_MAIN:
    scheduler = BackgroundScheduler()
    scheduler.add_job(my_job, "interval", seconds=INTERVAL_SECONDS)
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())
    log("INFO: Adset scheduler started successfully")

    # Run the job once immediately on server start
    my_job()
