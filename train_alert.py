import requests
import datetime
import pytz
import time
import os
from dotenv import load_dotenv
from google.transit import gtfs_realtime_pb2

# Load secrets from Render's secret file mount
load_dotenv("/etc/secrets/env")

# CONFIG
STOP_ID = "A28S"  # 34th St–Penn Station (southbound)
TARGET_ROUTE = "A"
TARGET_ARRIVAL_TIME = datetime.time(hour=9, minute=30)  # 9:30 AM
WALK_BUFFER_MINUTES = 5
MAX_OFFSET_MINUTES = 10  # Only consider trains within +/- 20 minutes of target time

# Pushover config
PUSHOVER_USER_KEY = os.getenv("PUSHOVER_USER_KEY")
PUSHOVER_API_TOKEN = os.getenv("PUSHOVER_API_TOKEN")

def fetch_gtfs_feed():
    url = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace"
    response = requests.get(url)
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)
    return feed

def get_arrival_times(feed):
    eastern = pytz.timezone("America/New_York")
    arrivals = []

    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue

        route_id = entity.trip_update.trip.route_id
        if route_id != TARGET_ROUTE:
            continue

        for stop_time_update in entity.trip_update.stop_time_update:
            if stop_time_update.stop_id == STOP_ID:
                arrival_unix = stop_time_update.arrival.time
                arrival_dt = datetime.datetime.fromtimestamp(arrival_unix, tz=eastern)
                arrivals.append(arrival_dt)

    return sorted(arrivals)

def find_best_train_within_range(arrivals, target_time, max_offset_minutes):
    eastern = pytz.timezone("America/New_York")
    today = datetime.datetime.now(eastern).date()
    target_dt = datetime.datetime.combine(today, target_time, tzinfo=eastern)

    filtered = [dt for dt in arrivals if abs((dt - target_dt).total_seconds()) <= max_offset_minutes * 60]
    return min(filtered, key=lambda dt: abs(dt - target_dt)) if filtered else None

def send_pushover_notification(title, message):
    if not PUSHOVER_USER_KEY or not PUSHOVER_API_TOKEN:
        print("Missing Pushover credentials.")
        return

    payload = {
        "token": PUSHOVER_API_TOKEN,
        "user": PUSHOVER_USER_KEY,
        "title": title,
        "message": message
    }
    response = requests.post("https://api.pushover.net/1/messages.json", data=payload)
    if response.status_code == 200:
        print("✅ Notification sent successfully.")
    else:
        print("❌ Failed to send notification:", response.text)

if __name__ == "__main__":
    feed = fetch_gtfs_feed()
    arrival_times = get_arrival_times(feed)

    print("Upcoming A train arrivals at 34th St–Penn Station (southbound):")
    for t in arrival_times:
        print("\u2022", t.strftime("%I:%M:%S %p"))

    closest_train = find_best_train_within_range(arrival_times, TARGET_ARRIVAL_TIME, MAX_OFFSET_MINUTES)

    if closest_train:
        leave_by = closest_train - datetime.timedelta(minutes=WALK_BUFFER_MINUTES)
        print("\n🎯 Best train near 9:30 AM arrives at:", closest_train.strftime("%I:%M:%S %p"))
        print("🚶\u200d♂️ You should leave your apartment by:", leave_by.strftime("%I:%M:%S %p"))

        # First notification with leave-by time
        message = f"Leave your apartment by {leave_by.strftime('%I:%M %p')} to catch the A train."
        send_pushover_notification("🕒 Commute Planning", message)

        # Wait until leave-by time and send reminder
        now = datetime.datetime.now(pytz.timezone("America/New_York"))
        seconds_until_leave = (leave_by - now).total_seconds()

        if seconds_until_leave > 0:
            print(f"\n⏳ Waiting {int(seconds_until_leave)} seconds until reminder notification...")
            time.sleep(seconds_until_leave)
            send_pushover_notification("🚶 Time to Leave!", "Head out now to catch your A train.")
        else:
            print("\n⚠️ Leave time has already passed. Skipping reminder.")
    else:
        print("\n⚠️ No A train arrivals found within 20 minutes of 9:30 AM.")
