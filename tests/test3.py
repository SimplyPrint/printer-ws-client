import logging
import asyncio
import json
from simplyprint_ws.websocket import SimplyPrintWebSocket


async def main():
    ws = await SimplyPrintWebSocket.from_url("ws://localhost:8080/0.1/p/0/0", asyncio.get_event_loop())

    while ws.socket.closed:
        print("Not connected yet")
        await asyncio.sleep(1)

    await ws.send(json.dumps({ "type": "latency", "data": { "ms": 100 } }))

    while True:
        await ws.poll_event()

logging.basicConfig(level=logging.DEBUG)
asyncio.run(main())