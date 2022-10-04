import time
import logging

from printer_ws_client import Client, ConnectEvent

def on_connect(event: ConnectEvent):
    print("Connected")
    print(f"is set up: {event.in_set_up}")
    print(f"intervals.job {event.intervals.job}")
    print(f"intervals.temperatures {event.intervals.temperatures}")
    print(f"intervals.target_temperatures {event.intervals.target_temperatures}")

logging.basicConfig(level=logging.DEBUG)
client = Client()

client.on_connect(on_connect)
client.on_pause(lambda event: print(event))

client.start()

temp = 20.0

while True:
    # sleep for 1 second
    time.sleep(1)

    client.send_json({
        "type": "temps",
        "data": {
            "tool0": [temp],
        }
    });

    temp += 5.0
