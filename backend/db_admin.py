"""Database Administration and Migration Tool for Simple Stationery Shop.

Usage:
  python db_admin.py test          - Test connection to the configured DATABASE_URL
  python db_admin.py init          - Create tables and seed initial data
  python db_admin.py migrate       - Copy existing data from SQLite stationery.db to PostgreSQL
  python db_admin.py status        - Display summary of records in the database
"""

import os
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")

from sqlalchemy import create_engine, make_url, text, select
from sqlalchemy.orm import Session
from app.database import engine, Base, SessionLocal, database_url
from app import models
from app.main import seed_database, init_db


def test_connection():
    print(f"[+] Testing database connection...")
    print(f"    Target URL: {make_url(database_url).render_as_string(hide_password=True)}")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            version = ""
            if engine.dialect.name == "postgresql":
                version = conn.execute(text("SELECT version();")).scalar()
            print(f"[OK] Connection successful!")
            if version:
                print(f"    Server version: {version}")
        return True
    except Exception as exc:
        print(f"[FAIL] Connection failed: {exc}")
        print("\nTroubleshooting tips:")
        print("  1. If using local PostgreSQL: Ensure PostgreSQL service is running and credentials in backend/.env are correct.")
        print("     Example: DATABASE_URL=postgresql+psycopg://postgres:yourPassword@localhost:5432/stationery_shop")
        print("  2. If using Neon / Cloud PostgreSQL: Verify the connection URL is active and your network allows DNS resolution.")
        print("  3. To create the database locally, run:")
        print("     CREATE DATABASE stationery_shop; in psql or pgAdmin.")
        return False


def show_status():
    if not test_connection():
        return
    with SessionLocal() as db:
        users_count = db.query(models.User).count()
        products_count = db.query(models.Product).count()
        orders_count = db.query(models.Order).count()
        order_items_count = db.query(models.OrderItem).count()
        print("\nDatabase Status:")
        print(f"  - Users:        {users_count}")
        print(f"  - Products:     {products_count}")
        print(f"  - Orders:       {orders_count}")
        print(f"  - Order Items:  {order_items_count}")


def migrate_from_sqlite():
    sqlite_path = backend_dir / "stationery.db"
    if not sqlite_path.exists():
        print(f"[!] SQLite database not found at {sqlite_path}. Nothing to migrate.")
        return

    print(f"[+] Found SQLite database at {sqlite_path}")
    print(f"[+] Preparing target database...")
    init_db()

    import sqlite3
    con = sqlite3.connect(sqlite_path)
    cur = con.cursor()

    with SessionLocal() as db:
        # Migrate users
        sqlite_users = cur.execute("SELECT id, username, password_hash FROM users").fetchall()
        users_added = 0
        for uid, username, pw_hash in sqlite_users:
            if not db.query(models.User).filter_by(username=username).first():
                db.add(models.User(username=username, password_hash=pw_hash))
                users_added += 1

        # Migrate products
        sqlite_products = cur.execute("SELECT id, name, category, price, stock FROM products").fetchall()
        products_added = 0
        for pid, name, category, price, stock in sqlite_products:
            if not db.query(models.Product).filter_by(name=name, category=category).first():
                db.add(models.Product(name=name, category=category, price=price, stock=stock))
                products_added += 1

        # Migrate orders
        sqlite_orders = cur.execute("SELECT id, created_at, total FROM orders").fetchall()
        orders_added = 0
        for oid, created_at, total in sqlite_orders:
            if not db.query(models.Order).filter_by(id=oid).first():
                # Parse date if string
                from datetime import datetime
                dt = datetime.fromisoformat(created_at) if isinstance(created_at, str) else created_at
                db.add(models.Order(id=oid, created_at=dt, total=total))
                orders_added += 1

        # Migrate order items
        sqlite_items = cur.execute("SELECT id, order_id, product_id, product_name, quantity, unit_price, line_total FROM order_items").fetchall()
        items_added = 0
        for iid, order_id, product_id, product_name, quantity, unit_price, line_total in sqlite_items:
            if not db.query(models.OrderItem).filter_by(id=iid).first():
                db.add(models.OrderItem(
                    id=iid,
                    order_id=order_id,
                    product_id=product_id,
                    product_name=product_name,
                    quantity=quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                ))
                items_added += 1

        db.commit()
        print(f"[OK] Migration complete:")
        print(f"    Users copied:       {users_added}")
        print(f"    Products copied:    {products_added}")
        print(f"    Orders copied:      {orders_added}")
        print(f"    Order items copied: {items_added}")


if __name__ == "__main__":
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "status"
    if action == "test":
        test_connection()
    elif action == "init":
        print("[+] Initializing database tables and seeding defaults...")
        init_db()
        print("[OK] Initialization complete.")
        show_status()
    elif action == "migrate":
        migrate_from_sqlite()
    elif action == "status":
        show_status()
    else:
        print(f"Unknown action: {action}")
        print("Available actions: test, init, migrate, status")
