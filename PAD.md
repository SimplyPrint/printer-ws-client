### connection(s)

- Associate client(s) & connection.
    - Should a connection be given a `ClientView` and derive stuff from that?

- A connection runs one loop that:
    - connects
        - How to tell clients to do shit, or should connection deal with that from view?
    - polls
    - repeats
    - on disconnect -> inc ver -> reconnect
    - on close -> exit function

- A connection needs a heartbeat loop / connectivity check.
    - Could be implemented as a "watchdog" type timer in the main loop that gets refreshed somehow.
    - If it triggers it should happen inside the main loop.

Now we can send and receive messages over a connection, yay!

Scheduling:
  - When we receive a message, should it immediately be run? (discord.py does this)
  - How many separate tasks should the scheduler be.
  - When we schedule a client we:
    - Check if its connection version is up to date
    - Consume changes and send messages
    - Tick client

- Stay disconnected when no pending clients.

### whatever scheduling

time
progress

v1:

-> change/update => mark JobInfo as pending

-> tick
- Construct JobInfo event and send
- Clear JobInfo as pending

-> send (Could be done whenever)

-> tick
- Still changed but no event is pending so no event is sent

-> sent
- Clear changed

v2:

-> change/update => field marked as changed

-> tick/schedule
- Compute events to send (based on changed keys)
- clear changes now
- send events

-> tick/schedule
- Nothing

-> sent
- Nothing