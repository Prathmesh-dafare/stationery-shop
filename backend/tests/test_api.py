import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

# Add backend to sys.path
backend_path = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_path))

from app.database import Base, get_db
from app.main import app, seed_database
from app import models

# Use isolated SQLite for unit testing with StaticPool so all connections share the memory DB
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    # Seed default shopkeeper and products
    from app.security import hash_password
    if not db.query(models.User).filter_by(username="shopkeeper").first():
        db.add(models.User(username="shopkeeper", password_hash=hash_password("Shop@123")))
    if db.query(models.Product).count() == 0:
        db.add_all([
            models.Product(name="Blue Pen", category="Pens", price=10.0, stock=100),
            models.Product(name="Pencil", category="Pencils", price=5.0, stock=120),
            models.Product(name="Notebook", category="Notebooks", price=50.0, stock=40),
        ])
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def auth_headers(client):
    res = client.post("/api/auth/login", json={"username": "shopkeeper", "password": "Shop@123"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_login_invalid(client):
    res = client.post("/api/auth/login", json={"username": "shopkeeper", "password": "WrongPassword"})
    assert res.status_code == 401

def test_me(client, auth_headers):
    res = client.get("/api/auth/me", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["username"] == "shopkeeper"

def test_unauthorized(client):
    res = client.get("/api/products")
    assert res.status_code == 401

def test_list_products(client, auth_headers):
    res = client.get("/api/products", headers=auth_headers)
    assert res.status_code == 200
    products = res.json()
    assert len(products) == 3
    names = [p["name"] for p in products]
    assert "Blue Pen" in names

def test_create_and_delete_product(client, auth_headers):
    payload = {"name": "Eraser", "category": "Accessories", "price": 5.0, "stock": 50}
    res = client.post("/api/products", json=payload, headers=auth_headers)
    assert res.status_code == 201
    created = res.json()
    prod_id = created["id"]
    assert created["name"] == "Eraser"

    # Delete
    del_res = client.delete(f"/api/products/{prod_id}", headers=auth_headers)
    assert del_res.status_code == 200

    # Ensure deleted
    del_res2 = client.delete(f"/api/products/{prod_id}", headers=auth_headers)
    assert del_res2.status_code == 404

def test_product_validation(client, auth_headers):
    # Blank name
    res = client.post("/api/products", json={"name": "   ", "category": "Test", "price": 10.0, "stock": 5}, headers=auth_headers)
    assert res.status_code == 422

    # Negative price
    res = client.post("/api/products", json={"name": "Valid", "category": "Test", "price": -2.0, "stock": 5}, headers=auth_headers)
    assert res.status_code == 422

    # Negative stock
    res = client.post("/api/products", json={"name": "Valid", "category": "Test", "price": 10.0, "stock": -1}, headers=auth_headers)
    assert res.status_code == 422

def test_create_sale_and_list_sales(client, auth_headers):
    # Get products
    products = client.get("/api/products", headers=auth_headers).json()
    p1 = products[0]
    p2 = products[1]

    # Create sale
    sale_payload = {
        "items": [
            {"product_id": p1["id"], "quantity": 2},
            {"product_id": p2["id"], "quantity": 3},
        ]
    }
    sale_res = client.post("/api/sales", json=sale_payload, headers=auth_headers)
    assert sale_res.status_code == 201
    bill = sale_res.json()
    expected_total = round(p1["price"] * 2 + p2["price"] * 3, 2)
    assert bill["total"] == expected_total
    assert len(bill["items"]) == 2

    # Verify stock decreased
    updated_products = client.get("/api/products", headers=auth_headers).json()
    up1 = next(p for p in updated_products if p["id"] == p1["id"])
    assert up1["stock"] == p1["stock"] - 2

    # Verify list sales works without unique() crash
    sales_res = client.get("/api/sales", headers=auth_headers)
    assert sales_res.status_code == 200
    sales_list = sales_res.json()
    assert len(sales_list) == 1
    assert sales_list[0]["id"] == bill["id"]
    assert len(sales_list[0]["items"]) == 2

def test_sale_insufficient_stock(client, auth_headers):
    products = client.get("/api/products", headers=auth_headers).json()
    p1 = products[0]
    sale_payload = {"items": [{"product_id": p1["id"], "quantity": 99999}]}
    sale_res = client.post("/api/sales", json=sale_payload, headers=auth_headers)
    assert sale_res.status_code == 400
    assert "Not enough stock" in sale_res.json()["detail"]

def test_dashboard(client, auth_headers):
    res = client.get("/api/dashboard", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["product_count"] == 3
    assert data["units_in_stock"] == 100 + 120 + 40
    assert data["bills_count"] == 0
    assert data["sales_total"] == 0.0
