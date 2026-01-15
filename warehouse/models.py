from typing import Optional, List
from datetime import date, datetime
from enum import Enum
from sqlmodel import Field, SQLModel, Relationship

class MaterialType(str, Enum):
    CONSUMABLE = "consumable"
    ITEM = "item"

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # Custom ID: First[0] + Last[0] + Counter
    custom_id: str = Field(index=True, unique=True) 
    title: Optional[str] = None
    first_name: str
    last_name: str
    workplace: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    
    withdrawals: List["Withdrawal"] = Relationship(back_populates="user")

class Material(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    material_type: MaterialType
    denomination: str
    ndc: Optional[str] = None
    part_number: Optional[str] = None
    serial_number: Optional[str] = None
    code: Optional[str] = None
    image_path: Optional[str] = None
    
    batches: List["Batch"] = Relationship(back_populates="material")
    withdrawals: List["Withdrawal"] = Relationship(back_populates="material")

class Batch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    material_id: int = Field(foreign_key="material.id")
    expiration: date
    amount: int
    location: Optional[str] = None
    
    material: Material = Relationship(back_populates="batches")

class Withdrawal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    material_id: int = Field(foreign_key="material.id")
    amount: int
    withdrawal_date: datetime = Field(default_factory=datetime.now)
    notes: Optional[str] = None
    
    # Only for Items
    return_date: Optional[datetime] = None
    efficient_at_return: Optional[bool] = None
    
    user: User = Relationship(back_populates="withdrawals")
    material: Material = Relationship(back_populates="withdrawals")
