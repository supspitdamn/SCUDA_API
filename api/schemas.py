import pydantic
import uuid 
from datetime import datetime

class EmployeeCreate(pydantic.BaseModel):

    card_id: str
    full_name: str
    department: str
    entry_level: int

class Employee(pydantic.BaseModel):

    id: int

class RoomCreate(pydantic.BaseModel):

    room_number: int
    description: str = None
    entry_level: int

class CreateAccessPoint(pydantic.BaseModel):

    room_id: int
    entrance_name: str
    direction: str