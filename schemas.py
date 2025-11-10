"""
Database Schemas for COVA Restaurant

Define MongoDB collection schemas using Pydantic models.
Each model maps to a collection with the lowercase class name.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime

# Users (authentication)
class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    password_hash: str = Field(..., description="Hashed password")
    phone: Optional[str] = Field(None, description="Phone number")
    is_active: bool = Field(True, description="Account active")
    role: str = Field("customer", description="Role in system: customer/admin")

# Menu items
class MenuItem(BaseModel):
    name: str = Field(..., description="Dish name")
    description: Optional[str] = Field(None, description="Short description")
    price: float = Field(..., ge=0, description="Price")
    category: str = Field(..., description="Category like Starters, Mains, Desserts")
    image: Optional[str] = Field(None, description="Image URL")
    is_bestseller: bool = Field(False, description="Flag for bestselling dishes")

# Orders
class OrderItem(BaseModel):
    item_id: str = Field(..., description="Menu item ID")
    quantity: int = Field(1, ge=1)

class Order(BaseModel):
    user_id: Optional[str] = Field(None, description="User ID if logged in")
    items: List[OrderItem]
    total: float = Field(..., ge=0)
    status: str = Field("pending", description="pending/confirmed/preparing/out-for-delivery/completed/cancelled")
    address: Optional[str] = Field(None, description="Delivery address")
    notes: Optional[str] = None

# Table bookings
class Booking(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None
    date: str = Field(..., description="YYYY-MM-DD")
    time: str = Field(..., description="HH:MM")
    guests: int = Field(..., ge=1, le=20)
    notes: Optional[str] = None

# Location/contact info (single document collection)
class Location(BaseModel):
    address: str
    lat: float
    lng: float
    phone: str
    opening_hours: str
