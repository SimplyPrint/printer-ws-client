import time
import logging

from printer_ws_client import Client, Temperature

class VirtualPrinter:
    def __init__(self):
        logging.basicConfig(level=logging.DEBUG)

        self.client: Client = Client()
        self.client.set_id("0")
        self.client.set_token("0")
        self.client.start()
    
    def run(self):
        self.client.start()

        while True:
            self.client.set_temperatures([Temperature(20.0)]);
            time.sleep(1)

if __name__ == "__main__":
    printer = VirtualPrinter()
    printer.run()
