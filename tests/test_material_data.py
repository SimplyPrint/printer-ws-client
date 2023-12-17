from typing import List, Optional
import unittest

from traitlets import Instance, Integer, List as TraitletsList
from simplyprint_ws_client.events.client_events import MaterialDataEvent, ToolEvent
from simplyprint_ws_client.models import MaterialModel
from simplyprint_ws_client.state import to_event
from simplyprint_ws_client.state.root_state import RootState

@to_event(MaterialDataEvent, "material_data")
@to_event(ToolEvent, "active_tool")
class TestState(RootState):
    active_tool: Optional[int] = Integer(None, allow_none=True)
    material_data: List[MaterialModel] = TraitletsList(Instance(MaterialModel))

    def __init__(self, **kwargs):
        super().__init__(
            active_tool=None,
            material_data=[],
        )

    def get_events(self):
        events = list(self._build_events())
        return list(map(lambda x: x.__class__, events)), events

class TestJobInfoState(unittest.TestCase):
    def test_basic_state(self):
        state = TestState()

        self.assertEqual(state.active_tool, None)
        self.assertEqual(state.material_data, [])

        state.active_tool = 0
        state.material_data.append(MaterialModel(type="PLA", color="red", hex="#FF0000", ext=0))

        event_types, events = state.get_events()
        self.assertEqual(event_types, [MaterialDataEvent, ToolEvent])
        event: MaterialDataEvent = events[0]
        self.assertDictEqual(dict(event.generate_data()), {'materials': [{'color': 'red', 'ext': 0, 'hex': '#FF0000', 'type': 'PLA'}]})

        event_types, events = state.get_events()
        self.assertEqual(event_types, [])
        self.assertEqual(events, [])

        state.active_tool = 1

        event_types, events = state.get_events()
        self.assertEqual(event_types, [ToolEvent])
        event: ToolEvent = events[0]

        self.assertDictEqual(dict(event.generate_data()), {'new': 1})

        # Add 3 more materials
        state.material_data = [
            MaterialModel(type="PLA", color="red", hex="#FF0000", ext=0),
            MaterialModel(type="PLA", color="green", hex="#00FF00", ext=1),
            MaterialModel(type="PLA", color="blue", hex="#0000FF", ext=2),
            MaterialModel(type="PLA", color="white", hex="#FFFFFF", ext=3)
        ]

        event_types, events = state.get_events()
        self.assertEqual(event_types, [MaterialDataEvent])
        event: MaterialDataEvent = events[0]

        self.assertDictEqual(dict(event.generate_data()), {'materials': [{'color': 'red', 'ext': 0, 'hex': '#FF0000', 'type': 'PLA'}, {'color': 'green', 'ext': 1, 'hex': '#00FF00', 'type': 'PLA'}, {'color': 'blue', 'ext': 2, 'hex': '#0000FF', 'type': 'PLA'}, {'color': 'white', 'ext': 3, 'hex': '#FFFFFF', 'type': 'PLA'}]})

        # Change both
        state.material_data = [
            MaterialModel(type="PLA", color="red", hex="#FF0000", ext=0),
            MaterialModel(type="PLA", color="green", hex="#00FF00", ext=1),
            MaterialModel(type="PLA", color="blue", hex="#0000FF", ext=2),
            MaterialModel(type="PLA", color="white", hex="#FFFFFF", ext=3)
        ]
        state.active_tool = 0

        event_types, events = state.get_events()
        self.assertEqual(event_types, [MaterialDataEvent, ToolEvent])
        event_material: MaterialDataEvent = events[0]
        event_tool: ToolEvent = events[1]

        self.assertDictEqual(dict(event_material.generate_data()), {'materials': [{'color': 'red', 'ext': 0, 'hex': '#FF0000', 'type': 'PLA'}, {'color': 'green', 'ext': 1, 'hex': '#00FF00', 'type': 'PLA'}, {'color': 'blue', 'ext': 2, 'hex': '#0000FF', 'type': 'PLA'}, {'color': 'white', 'ext': 3, 'hex': '#FFFFFF', 'type': 'PLA'}]})
        self.assertDictEqual(dict(event_tool.generate_data()), {'new': 0})