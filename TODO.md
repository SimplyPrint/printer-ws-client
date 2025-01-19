### stuff now:

- ClientApp
    * load (provider)
        * Creates internal provider reference.
    * unload (provider)
        * Two types of unload, remove (offline / keep state) and delete (fully deleted / remove state).

    - Provider
        * get_client (boolean, either active or not)
        * can receive external changes (new ip etc.) which potentially can lead to it being removed.

        - Instance (gets client)
            * lifetime/init/tick/stop (based on WebSocket connection)
            * can receive "pop" e.i. invalid client / deleted client that needs to change role / config and be
              reconfigured with remote (new add_connection etc.)

The above structure is controlled from the `PrinterConfig` lifetime

- All on boot
- Individually under load

This is obviously too complicated and bad. The idea is we have multiple sources and places of "invalid state / do not
pass", and we want to modify the state and its "rank" in the hierarchy from everywhere.


There is a user "need / want": I declare an existence of `PRINTER 1`.

There is a physical reality: `PRINTER 1` is online / offline / reachable / authenticated etc.

There is the SP state: `PRINTER 1` is a valid printer, is already connected, etc.


Each of these sources can change the rank of the client:

- User can remove / add (declare existence)
- Printer can go offline, change authentication or IP etc.
- Printer can be removed from SP, connect from somewhere else, SP can restart disconnecting it etc.

All of these factors need to be correctly factored in, this is before reaching the concept of consistency in the configuration
which we have abstracted away here. All while SP wants to poll the client, the user wants to edit/change it and the printer does
whatever it wants to do.

A redesign is necessary.

### new stuff

Layers / "regions" as some would call it.

- User layer (CRUD config)
- Config layer (store config / local state)
- Provider layer (connect to physical and update client / physical state)

- Instance layer (poll client / no state)
- WebSocket layer (add/remove/send/receive client / remote state)

