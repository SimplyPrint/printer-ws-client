# Printer WS Client

A package for easy implementations of SimplyPrint printers.

## Usage

```python
from printer_ws_client import *

class MyClient(Client):
    def __init__(self):
        self.info.ui = "My Ui"
        self.info.ui_version = "0.0.1"

        self.info.api = "My Api"
        self.info.api_version = "4.2.0"

        self.local_path = "path_to_local_files"

    # define a callback
    async def on_connect(self, event: ConnectEvent):
        print(f"Connected, got name: {event.name}")

    # define another callback
    async def on_start_print(self, _: StartPrintEvent):
        # start the print somehow
        start_print(self.selected_file)

my_client = MyClient()

# start the client
# this runs the background thread and starts even processing
my_client.start()

# run some loop
while True:
    sleep(1)
    # get data from printer
    my_client.tool_temperatures = poll_tool_temperatures()
    my_client.bed_temperature = poll_bed_temperature()
```
