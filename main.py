import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

from database import db, create_document, get_documents
from schemas import User, MenuItem, Order, Booking, Location

# App and CORS
app = FastAPI(title="COVA Restaurant API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth settings
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkeychange")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# Utilities

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    email: Optional[str] = None

# Database helpers

def find_one(collection: str, filter_dict: dict):
    if db is None:
        return None
    return db[collection].find_one(filter_dict)

# Auth dependencies

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    user_doc = find_one("user", {"email": token_data.email})
    if not user_doc:
        raise credentials_exception
    return user_doc

# Routes
@app.get("/")
def root():
    return {"name": "COVA", "status": "ok"}

@app.get("/schema")
def get_schema_info():
    # Helper endpoint for DB viewer
    return {
        "collections": [
            "user", "menuitem", "order", "booking", "location"
        ]
    }

# Auth
class SignUpBody(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None

@app.post("/auth/signup")
def signup(body: SignUpBody):
    existing = find_one("user", {"email": body.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        name=body.name,
        email=body.email,
        password_hash=get_password_hash(body.password),
        phone=body.phone,
        is_active=True,
        role="customer",
    )
    user_id = create_document("user", user)
    token = create_access_token({"sub": body.email})
    return {"user_id": user_id, "access_token": token, "token_type": "bearer"}

@app.post("/auth/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user_doc = find_one("user", {"email": form_data.username})
    if not user_doc:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    if not verify_password(form_data.password, user_doc.get("password_hash")):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    access_token = create_access_token(data={"sub": user_doc["email"]})
    return {"access_token": access_token, "token_type": "bearer"}

# Menu
@app.post("/menu")
def add_menu_item(item: MenuItem, user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    item_id = create_document("menuitem", item)
    return {"id": item_id}

@app.get("/menu")
def list_menu(category: Optional[str] = None, bestseller: Optional[bool] = None):
    filters = {}
    if category:
        filters["category"] = category
    if bestseller is not None:
        filters["is_bestseller"] = bestseller
    items = get_documents("menuitem", filters)
    for i in items:
        i["_id"] = str(i["_id"])  # serialize
    return items

# Bookings
@app.post("/bookings")
def create_booking(booking: Booking):
    booking_id = create_document("booking", booking)
    return {"id": booking_id, "message": "Booking received"}

@app.get("/bookings")
def list_bookings(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    bookings = get_documents("booking")
    for b in bookings:
        b["_id"] = str(b["_id"])  # serialize
    return bookings

# Orders
@app.post("/orders")
def create_order(order: Order, user=Depends(get_current_user)):
    order_dict = order.model_dump()
    if user:
        order_dict["user_id"] = str(user.get("_id"))
    order_id = create_document("order", order_dict)
    return {"id": order_id, "message": "Order placed"}

@app.get("/orders")
def list_orders(user=Depends(get_current_user)):
    filters = {"user_id": str(user.get("_id"))}
    orders = get_documents("order", filters)
    for o in orders:
        o["_id"] = str(o["_id"])  # serialize
    return orders

# Location info
@app.get("/location")
def get_location():
    docs = get_documents("location")
    if docs:
        d = docs[0]
        d["_id"] = str(d["_id"])  # serialize
        return d
    # Default fallback
    return {
        "address": "123 COVA Street, Food City",
        "lat": 40.7128,
        "lng": -74.0060,
        "phone": "+1 (555) 123-4567",
        "opening_hours": "Mon-Sun: 10:00 - 22:00",
    }

# Health
@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        from database import db
        if db is not None:
            response["database"] = "✅ Available"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
