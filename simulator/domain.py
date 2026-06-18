import json
import uuid
from enum import Enum


class DataType(Enum):
    INTEGER = "INTEGER"
    DOUBLE = "DOUBLE"
    STRING = "STRING"
    VECTOR_DOUBLE = "VECTOR_DOUBLE"
    VECTOR_STRING = "VECTOR_STRING"
    VECTOR_INTEGER = "VECTOR_INTEGER"


class Attribute:
    def __init__(self):
        self.name: str = ""
        self.dataType: DataType = DataType.STRING
        self.id: str = uuid.uuid4().hex
        self.run = False

    def read_from_json(self, attribute: dict):
        self.name = attribute["name"]
        self.dataType = DataType(attribute.get("dataType", ""))


class Component:
    def __init__(self):
        self.iotDeviceId: str = ""
        self.name: str = ""
        self.attributes: list[Attribute] = []

    def read_from_json(self, component: dict, components_by_id: dict):
        self.iotDeviceId = component["iotDeviceId"]
        self.name = component["name"]
        comp_data = components_by_id.get(self.iotDeviceId, {})
        for attribute in comp_data.get("properties", []):
            attr = Attribute()
            attr.read_from_json(attribute)
            self.attributes.append(attr)


class Entity:
    def __init__(self):
        self.id: str = ""
        self.name: str = ""
        self.entities: list["Entity"] = []
        self.components: list[Component] = []

    def read_from_json(self, entity: dict, components_by_id: dict):
        self.id = entity["id"]
        self.name = entity["name"]
        for child in entity.get("children", []):
            if child["type"] == "entity":
                ent = Entity()
                ent.read_from_json(child, components_by_id)
                self.entities.append(ent)
            else:
                component = Component()
                component.read_from_json(child, components_by_id)
                self.components.append(component)


class Twin:
    def __init__(self):
        self.name: str = ""
        self.entities: list[Entity] = []

    def read_from_json(self, config_json_path: str, config_iotdevices_path: str, config_hier_path: str):
        with open(config_json_path) as f:
            config_json = json.load(f)
        with open(config_iotdevices_path) as f:
            config_iotdevices = json.load(f)
        with open(config_hier_path) as f:
            config_hier = json.load(f)

        self.name = config_json["digital_twin_name"]
        components_by_id = {c["id"]: c for c in config_iotdevices}
        for entity in config_hier:
            ent = Entity()
            ent.read_from_json(entity, components_by_id)
            self.entities.append(ent)

    def flatten(self, entities: list = None):
        if entities is None:
            entities = self.entities

        rows = []
        for entity in entities:
            for component in entity.components:
                for attribute in component.attributes:
                    rows.append((entity, component, attribute))
            rows.extend(self.flatten(entity.entities))
        return rows