import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func, select, text
from .database import Base, engine, get_db, SessionLocal
from . import models, schemas
from .security import hash_password, verify_password, create_access_token, read_token

logger = logging.getLogger("stationery_shop")


def seed_database():
    db = SessionLocal()
    try:
        if not db.query(models.User).filter_by(username="shopkeeper").first():
            # Demo credentials; change them before real deployment.
            db.add(models.User(username="shopkeeper", password_hash=hash_password("Shop@123")))
        if db.query(models.Product).count() == 0:
            db.add_all([
                models.Product(name="Blue Pen", category="Pens", price=10.0, stock=100),
                models.Product(name="Pencil", category="Pencils", price=5.0, stock=120),
                models.Product(name="Notebook", category="Notebooks", price=50.0, stock=40),
                models.Product(name="Eraser", category="Accessories", price=5.0, stock=80),
                models.Product(name="Ruler", category="Accessories", price=15.0, stock=30),
            ])
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    seed_database()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables and seed data are initialized
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as exc:
        logger.error("Database initialization failed on startup: %s", exc)
        print(f"[WARNING] Database initialization failed on startup: {exc}")
    yield


app = FastAPI(title="Simple Stationery Shop API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

bearer = HTTPBearer(auto_error=False)


@app.exception_handler(OperationalError)
async def handle_db_operational_error(request, exc: OperationalError):
    logger.error("Database connection error: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database connection error. Please verify PostgreSQL is running and DATABASE_URL in backend/.env is configured correctly."}
    )



def current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Please log in.")
    username = read_token(credentials.credentials)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    user = db.query(models.User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    return user


@app.get("/")
def root():
    return {"message": "Stationery Shop API is running", "docs": "/docs"}


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        return {"status": "degraded", "database": "disconnected", "error": str(exc)}


@app.post("/api/auth/login", response_model=schemas.TokenOutput)
def login(payload: schemas.LoginInput, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(username=payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password.")
    return {"access_token": create_access_token(user.username), "username": user.username}


@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return {"username": user.username}


@app.get("/api/products", response_model=list[schemas.ProductOutput])
def list_products(user=Depends(current_user), db: Session = Depends(get_db)):
    return db.query(models.Product).order_by(models.Product.name).all()


@app.post("/api/products", response_model=schemas.ProductOutput, status_code=201)
def create_product(payload: schemas.ProductInput, user=Depends(current_user), db: Session = Depends(get_db)):
    product = models.Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@app.put("/api/products/{product_id}", response_model=schemas.ProductOutput)
def update_product(product_id: int, payload: schemas.ProductInput, user=Depends(current_user), db: Session = Depends(get_db)):
    product = db.query(models.Product).filter_by(id=product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    for key, value in payload.model_dump().items():
        setattr(product, key, value)
    db.commit()
    db.refresh(product)
    return product


@app.delete("/api/products/{product_id}")
def delete_product(product_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    product = db.query(models.Product).filter_by(id=product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    db.delete(product)
    db.commit()
    return {"message": "Product deleted.", "id": product_id}


@app.post("/api/sales", response_model=schemas.OrderOutput, status_code=201)
def create_sale(payload: schemas.SaleInput, user=Depends(current_user), db: Session = Depends(get_db)):
    # Merge repeated product IDs so a product is not charged twice inconsistently.
    quantities = {}
    for item in payload.items:
        quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity

    prepared = []
    total = 0.0
    for product_id, quantity in quantities.items():
        query = db.query(models.Product).filter_by(id=product_id)
        if engine.dialect.name == "postgresql":
            query = query.with_for_update()
        product = query.first()

        if not product:
            raise HTTPException(status_code=404, detail=f"Product {product_id} not found.")
        if product.stock < quantity:
            raise HTTPException(status_code=400, detail=f"Not enough stock for {product.name}. Available: {product.stock}.")
        line_total = round(product.price * quantity, 2)
        prepared.append((product, quantity, line_total))
        total += line_total

    order = models.Order(total=round(total, 2))
    db.add(order)
    db.flush()
    for product, quantity, line_total in prepared:
        product.stock -= quantity
        db.add(models.OrderItem(
            order_id=order.id,
            product_id=product.id,
            product_name=product.name,
            quantity=quantity,
            unit_price=product.price,
            line_total=line_total,
        ))
    db.commit()
    stmt = select(models.Order).options(selectinload(models.Order.items)).filter_by(id=order.id)
    return db.scalars(stmt).first()


@app.get("/api/sales", response_model=list[schemas.OrderOutput])
def list_sales(user=Depends(current_user), db: Session = Depends(get_db)):
    stmt = (
        select(models.Order)
        .options(selectinload(models.Order.items))
        .order_by(models.Order.created_at.desc())
        .limit(100)
    )
    return db.scalars(stmt).all()


@app.get("/api/dashboard")
def dashboard(user=Depends(current_user), db: Session = Depends(get_db)):
    product_count = db.query(func.count(models.Product.id)).scalar() or 0
    stock_count = db.query(func.coalesce(func.sum(models.Product.stock), 0)).scalar() or 0
    sales_total = db.query(func.coalesce(func.sum(models.Order.total), 0)).scalar() or 0
    bills_count = db.query(func.count(models.Order.id)).scalar() or 0
    return {
        "product_count": int(product_count),
        "units_in_stock": int(stock_count),
        "sales_total": round(float(sales_total), 2),
        "bills_count": int(bills_count),
    }
