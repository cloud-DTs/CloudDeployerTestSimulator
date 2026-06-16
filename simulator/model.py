import datetime
import random
from enum import Enum
import json
import time
class DataType(Enum):
    INTEGER = "INTEGER"
    DOUBLE = "DOUBLE"
    STRING = "STRING"
    VECTOR_DOUBLE = "VECTOR_DOUBLE"
    VECTOR_STRING = "VECTOR_STRING"
    VECTOR_INTEGER = "VECTOR_INTEGER"


class IotPayload:
    id:str
    dataType:DataType
    dataName:str
    run:bool

    def __str__(self):
        return f"{self.dataType} {self.dataName}"

    def returnAsPayloadWithRandValue(self)->dict:
        return {"iotDeviceId":self.id,"time":datetime.datetime.now().timestamp(),self.dataName:generateRandValue()}

    import random

    def generateRandValue(self):
        match self.dataType:
            case DataType.INTEGER:
                return random.randint(0, 100)
            case DataType.DOUBLE:
                return round(random.uniform(0.0, 100.0), 2)
            case DataType.STRING:
                return random.choice(["low", "medium", "high"])
            case DataType.VECTOR_INTEGER:
                return [random.randint(0, 100) for _ in range(3)]
            case DataType.VECTOR_DOUBLE:
                return [round(random.uniform(0.0, 100.0), 2) for _ in range(3)]
            case DataType.VECTOR_STRING:
                return [random.choice(["low", "medium", "high"]) for _ in range(3)]
            case _:
                raise ValueError(f"Unknown dataType: {self.dataType}")


class Payloads:

    payloads:list[IotPayload] = []
    payloadsDict:dict[str,IotPayload] = {}
    def read_from_json(self,path):
        with open(path) as json_file:
            data = json.load(json_file)
            for item in data:
                for prop in item["properties"]:
                    payload = IotPayload()
                    payload.id = item["id"]
                    payload.dataType = prop["dataType"]
                    payload.dataName = prop["name"]
                    payload.run = False
                    self.payloads.append(payload)
                    unique_key = f"{payload.id}_{payload.dataName}"
                    self.payloadsDict[unique_key] = payload


