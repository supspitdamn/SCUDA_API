import pydantic
import uuid 
from datetime import datetime
from enum import Enum

class AccessGroupCreate(pydantic.BaseModel):
    group_name: str

class AccessGroup(AccessGroupCreate):
    id: int

class EmployeeAccessGroupCreate(pydantic.BaseModel):
    employee_id: int
    group_id : int

class EmployeeAccessGroup(EmployeeAccessGroupCreate):
    id : int

class RoomGroupCreate(pydantic.BaseModel):
    group_id: int
    room_id: int

class RoomGroup(RoomGroupCreate):
    id: int

class DirectionsEnum(str, Enum):
    IN = "IN"
    OUT = "OUT"
    BOTH = "BOTH"

class RoleCreate(pydantic.BaseModel):
    role_name: str
    access_level: int

class Role(RoleCreate):
    id: int

class EmployeeCreate(pydantic.BaseModel):
    card_id: str
    full_name: str
    department: str
    role_id: int
    is_active: bool = True

class Employee(EmployeeCreate):
    id: int

class RoomCreate(pydantic.BaseModel):
    room_number: int
    description: str = None
    entry_level: int

class Room(RoomCreate):
    id: int

class AccessPointCreate(pydantic.BaseModel):
    room_id: int
    entrance_name: str
    direction: DirectionsEnum

class AccessPoint(AccessPointCreate):
    id: int

class AccessPointResponse(pydantic.BaseModel):
    id: int
    employee_id: int
    access_point_id: int
    event_time: datetime
    is_granted: bool

class StatusResponse(pydantic.BaseModel):
    status: str = "Неизвестно"
    message: str = "..."

class LogEntry(pydantic.BaseModel):
    id: int
    employee_name: str
    room_number: int
    entrance: str
    time: str
    is_granted: bool

class FromMKtoServerAccessLog(pydantic.BaseModel):
    event_id: int
    ts: datetime
    device: str
    card_id: str
    access: str
    whitelist_version: int = None
    rssi: int = None

class ViewLogsResponse(pydantic.BaseModel):
    status: str
    data: list[LogEntry]

class WhiteListResponse(pydantic.BaseModel):
    status: str
    device: str
    cards: list[str]