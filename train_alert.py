import requests
import datetime
import pytz
from google.transit import gtfs_realtime_pb2

# CONFIG
STOP_ID = "A28S"  # 34th St–Penn Station (southbound)
TARGET_ROUTE = "A"

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

if __name__ == "__main__":
    feed = fetch_gtfs_feed()
    arrival_times = get_arrival_times(feed)

    print("Upcoming A train arrivals at 34th St–Penn Station (southbound):")
    for t in arrival_times:
        print("•", t.strftime("%I:%M:%S %p"))
