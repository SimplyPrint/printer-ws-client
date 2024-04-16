from dataclasses import dataclass, fields, field, Field, is_dataclass
from typing import Optional, List

"""The general idea here is we can define a schema, and then define partial schemas we can extract updates to
for better clarity, fx.

We get a huge bundle called "print", we are interested in changes to the temperature, so we define a partial schema
on top of our complete definition:

@partial(of=PrintData)
class Temperature:
    bed_temperature: float = link(to=PrintData.field)
    nozzle_temp: float = link(to=PrintData.field.field)
    

We can then create an event listener on temperature, which will get triggered whenever we receive any updates
to the partial object.

def on_temperature(event: Temperature):
    if event.has_changes(Temperature.bed_temperature):
        do_something(event.bed_temperature)

To automatically resolve these beyond just running some code on every attribute change
we need to somewhere have a pool of "top level states" then we simplify and let all states link
then create a graph between all links which we traverse when we perform an update.

{
    "bed_temp": "0","bed_temp_type": "0","cali_idx": -1,"cols": ["FFFFFFFF"],
    "ctype": 0,"drying_temp": "0","drying_time": "0","id": "0","nozzle_temp_max": "240",
    "nozzle_temp_min": "190","remain": 0,"tag_uid": "0000000000000000","tray_color": "FFFFFFFF",
    "tray_diameter": "0.00","tray_id_name": "","tray_info_idx": "GFL99","tray_sub_brands": "","tray_type": "PLA",
    "tray_uuid": "00000000000000000000000000000000","tray_weight": "0","xcam_info": "000000000000000000000000"
}

@state
class AMSTray:
    id: int
    
    # Everything is optional
    bed_temp: float
    bed_temp_type: float
    cali_idx: int
    cols: List[str]
    ctype: int
    drying_temp: float
    drying_time: int
    nozzle_temp_max: float
    tray_diameter: float
    tray_id_name: str
    tray_info_idx: str
    tray_sub_brands: str
    tray_type: str
    tray_uuid: str
    tray_weight: int
    xcam_info: str

@state
class AMSInstance:
     humidity: int
     id: int
     temp: float
     trays: List[AMSTray]

"ams_exist_bits": "1",
"insert_flag": false,"power_on_flag": false,"tray_exist_bits": "c7",
"tray_is_bbl_bits": "b7","tray_now": "255","tray_pre": "255","tray_read_done_bits": "7",
"tray_reading_bits": "0","tray_tar": "255","version": 6190

@state
class AMS:
    ams: List[AMSInstance]
    ams_exists_bits: hex?
    insert_flag: bool
    power_on_flag: bool
    tray_exists_bits: hex?
    tray_is_bbl_bits: hex?
    tray_now: int
    tray_pre: int
    tray_read_done_bits: hex?
    tray_reading_bits: hex?
    tray_tar: int
    version: int
    
The way we would update this assuming we get one payload for the top level state called "BambuState" 

print -> ams [] -> ams [] -> trays [] fx.

Is that we invoke update on AMS which propagates the updates down to AMSInstance
which goes down to AMSTray.

For lists the most easy thing to do is do have some kind of "key" function that would fx. extract its ID
but for nested lists like AMS Instances -> AMS Trays it would have to collect keys down and return them as a tuple?

And we could default to the index as the key, then we could correctly generate "Updates" based on links on arrays.

For simple fields like AMS version any partial state that links to it would generate those events once.

Maybe keep track of subevents so the event that is produces that is linked to AMS comes before AMSInstance which comes 
before AMSTray, allowing some control of what events that need to be triggered.

"""


class TypeProxyField:
    """Not to be confused with dataclass Field
    This class is a reference to the underlying fields, and is used to
    perform object linking.
    """

    _field: Field
    _parent: Optional["TypeProxyField"] = None

    """
    def __new__(cls, *args, **kwargs):
        if "f" not in kwargs:
            raise ValueError("field is required")

        # kwargs["f"]
        # TODO Add slots based on fields.

        return super().__new__(cls)
    """

    def __init__(self, *, f: Field, parent: Optional["TypeProxyField"] = None, state_cls=None):
        self._field = f
        self._parent = parent
        self._state_cls = state_cls

    @staticmethod
    def invert_tree(tf: "TypeProxyField") -> List[Field]:
        """Invert the tree of fields, this can be cached for speed."""
        field_list = []

        while tf:
            field_list.append(tf._field)
            tf = tf._parent

        return field_list

    @staticmethod
    def resolve(tf: "TypeProxyField", state: object = None):
        """Resolve a field from its state.

        We have a tree of fields in TypeProxyField

        """

        field_list = TypeProxyField.invert_tree(tf)

        for f in field_list:
            state = getattr(state, f.name)

        return state


def extract_partial(partial_cls: dataclass, st: object) -> object:
    """Extract a partial object from a state object."""
    if not is_dataclass(partial_cls) or not is_dataclass(st):
        raise ValueError("Must be a dataclass")

    partial_values = {}

    for f in fields(partial_cls):
        try:
            metadata = f.metadata

            if LINK_METADATA_FIELD_NAME in metadata and isinstance(metadata[LINK_METADATA_FIELD_NAME],
                                                                   TypeProxyField):
                tf = metadata[LINK_METADATA_FIELD_NAME]
                partial_values[f.name] = TypeProxyField.resolve(tf, st)

            elif is_dataclass(f.type):
                partial_values[f.name] = extract_partial(f.type, st)

        except AttributeError:
            pass

    return partial_cls(**partial_values)


def apply_fields(dst, src=None, parent=None, state_cls=None):
    if not src:
        src = dst

    for f in fields(src):
        # Ignore default values.
        try:
            if isinstance(getattr(dst, f.name), TypeProxyField):
                continue
        except AttributeError:
            pass

        tf = TypeProxyField(f=f, parent=parent)

        if is_dataclass(f.type):
            apply_fields(tf, f.type, tf)

        setattr(dst, f.name, tf)


def fullstate(cls):
    dcls = dataclass(cls)
    apply_fields(dcls, state_cls=dcls)
    return dcls


def partial(cls):
    dcls = dataclass(cls)
    apply_fields(dcls, state_cls=dcls)
    return dcls


LINK_METADATA_FIELD_NAME = "of"


def link(*args, to=None, **kwargs):
    if "metadata" not in kwargs:
        kwargs["metadata"] = {}

    kwargs["metadata"].update({LINK_METADATA_FIELD_NAME: to})

    return field(*args, **kwargs)


@fullstate
class FullState:
    first_int: int = field(default=10)
    second_int: int = field(default=20)


@partial
class Test2:
    field2: int = link(to=FullState.first_int)


@partial
class Test:
    field: int = link(to=FullState.second_int)
    field0: Test2


s = FullState()

print(Test.field0.field2, Test2.field2)

print(TypeProxyField.resolve(FullState.second_int, s))

print(extract_partial(Test, s))
