import asyncio
import functools
import inspect
from functools import partial
from typing import Type, get_origin, Hashable, Dict, Optional, get_args, \
    Literal, Tuple, List, TYPE_CHECKING

from pydantic import BaseModel

from .state import PrinterState
from .ws_protocol.messages import ClientMsg, DemandMsgType, DispatchMode, ServerMsgType, ServerMsgKind, DemandMsgKind
from ..events.event_bus_listeners import EventBusListenerOptions

if TYPE_CHECKING:
    from .client import Client

try:
    from typing import Unpack
except ImportError:
    from typing_extensions import Unpack

_client_msg_map: Dict[str, Type[ClientMsg]] = {}


def configure(event: Optional[Hashable] = None, **kwargs: Unpack[EventBusListenerOptions]):
    """Map a function as a callback for an event."""

    def decorator(func):
        if not hasattr(func, '_event_bus_event'):
            func._event_bus_event = None

        if not hasattr(func, '_event_bus_wrap'):
            func._event_bus_wrap = False

        if not hasattr(func, '_event_bus_listeners_args'):
            func._event_bus_listeners_args = {}

        func._event_bus_listeners_args.update(kwargs)
        func._event_bus_event = event or func._event_bus_event

        return func

    return decorator


def autoconfigure(attr: callable):
    """Automatically configure a function based on its signature."""
    if isinstance(attr, partial) or isinstance(attr, functools.partialmethod):
        attr = attr.func

    if not inspect.isfunction(attr):
        raise ValueError("Expected a function.")

    signature = inspect.signature(attr)
    parameters = dict(signature.parameters.copy())
    parameters.pop('self', None)

    if len(parameters) == 0:
        attr._event_bus_wrap = True

    name = attr.__name__

    msg_lookup, msg_data_lookup, demand_lookup = build_autoconfiguration_state()

    # Initially, determine event type based on function name.
    if name.startswith('on_'):
        event_name: str = name[3:]

        if event_name.upper() in ServerMsgType.__members__:
            event_guess = ServerMsgType(event_name)
            attr._event_bus_event = event_guess
            return

        elif event_name.upper() in DemandMsgType.__members__:
            event_guess = DemandMsgType(event_name)
            attr._event_bus_event = event_guess
            return

    # We extract event information given one argument.
    if len(parameters) != 1:
        return

    param_type = next(iter(parameters.values())).annotation

    # Only consider first argument type.
    if not isinstance(param_type, type):
        return

    if msg_cls := msg_lookup.get(param_type):
        attr._event_bus_event = msg_cls
        return

    if demand_cls := demand_lookup.get(param_type):
        attr._event_bus_event = demand_cls
        return

    if data_cls := msg_data_lookup.get(param_type):
        attr._event_bus_event = data_cls
        return


@functools.lru_cache()
def build_autoconfiguration_state():
    demand_lookup: Dict[Type[BaseModel], DemandMsgType] = {}
    msg_lookup: Dict[Type[BaseModel], ServerMsgType] = {}
    msg_data_lookup: Dict[Type[BaseModel], ServerMsgType] = {}

    for m in set(get_args(ServerMsgKind)):
        type_annotation = m.model_fields['type'].annotation

        if get_origin(type_annotation) is not Literal:
            continue

        msg_type = get_args(type_annotation)[0]

        if not isinstance(msg_type, ServerMsgType):
            continue

        msg_lookup[m] = msg_type

        data_annotation = m.model_fields['data'].annotation

        if isinstance(data_annotation, type) and issubclass(data_annotation, BaseModel):
            msg_data_lookup[data_annotation] = msg_type

    for m in set(get_args(DemandMsgKind)):
        demand_annotation = m.model_fields['demand'].annotation

        if get_origin(demand_annotation) is not Literal:
            continue

        demand_type = get_args(demand_annotation)[0]

        if not isinstance(demand_type, DemandMsgType):
            continue

        demand_lookup[m] = demand_type

    return msg_lookup, msg_data_lookup, demand_lookup


def autoconfigure_class_dict(class_dict: dict):
    """
    # autofill opts based on:
    # function name
    # function arguments
    """
    for name in class_dict:
        attr = class_dict[name]

        # Only consider functions.
        if not inspect.isfunction(attr) and not isinstance(attr, partial):
            continue

        autoconfigure(attr)


def debug(cls: Type['Client']):
    # Show all configured functions
    for name in dir(cls):
        attr = getattr(cls, name)

        if not inspect.isfunction(attr):
            continue

        if hasattr(attr, '_event_bus_event'):
            print(f"{name} => {getattr(attr, '_event_bus_event')}")


def instrument(client: 'Client'):
    """Instrument and instance of a client based on its methods."""
    for name in dir(client.__class__):
        attr = getattr(client.__class__, name)

        if not hasattr(attr, '_event_bus_event'):
            continue

        e = getattr(attr, '_event_bus_event')
        kwargs = {}

        if hasattr(attr, '_event_bus_listeners_args'):
            kwargs = getattr(attr, '_event_bus_listeners_args')

        func = getattr(client, name)

        if hasattr(attr, '_event_bus_wrap') and getattr(attr, '_event_bus_wrap') is True:
            if asyncio.iscoroutinefunction(func):
                async def func(*args, inner_func=func, **_):
                    return await inner_func()
            else:
                def func(*args, inner_func=func, **_):
                    return inner_func()

        client.event_bus.on(e, func, **kwargs)


def produce(msg_cls, *when_key_changes: str):
    """Map a message to a key"""
    for key in when_key_changes:
        _client_msg_map[key] = msg_cls


def consume(state: PrinterState) -> Tuple[List[ClientMsg], int]:
    """Consume state from mappings"""
    changes = state.model_recursive_changeset

    msg_kinds = {}

    # Build unique map of message kinds together with their highest version.
    for k, v in changes.items():
        if k not in _client_msg_map:
            continue

        msg_kind = _client_msg_map.get(k)
        current = msg_kinds.get(msg_kind)

        if current is None:
            msg_kinds[msg_kind] = v
            continue

        msg_kinds[msg_kind] = v if v > current else current

    is_pending = state.config.is_pending()

    msgs = []

    for msg_kind, v in msg_kinds.items():
        # Skip over messages that are not allowed to be sent when pending.
        if is_pending and not msg_kind.msg_type().when_pending():
            continue

        data = dict(msg_kind.build(state))

        if not data:
            continue

        msg = msg_kind(data)

        # Skip over messages that are not supposed to be sent.
        if msg.dispatch_mode(state) != DispatchMode.DISPATCH:
            continue

        msgs.append(msg)
        msg.reset_changes(state, v=v)

    return msgs, -1  # max(v for _, v in msg_kinds)
