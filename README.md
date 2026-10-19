# Simple Stationery Shop

A local full-stack shop management project using React, FastAPI, SQLAlchemy and PostgreSQL.

## Demo login
- Username: `shopkeeper`
- Password: `Shop@123`

## Requirements
- Python 3.10 or newer
- Node.js 18 or newer (Node 20 LTS recommended)
- PostgreSQL installed and running locally

## 1. Create the PostgreSQL database

Open **SQL Shell (psql)** or pgAdmin and run this SQL command (connect as a PostgreSQL administrator):

```sql
CREATE DATABASE stationery_shop;
```

If the database already exists, do not create it again. The PostgreSQL username in the example below is `postgres`; use the username and password you configured during PostgreSQL installation.

## 2. Configure the backend

Open PowerShell in the project folder and run:

```powershell
cd backend
Copy-Item .env.example .env
notepad .env
```

In `.env`, replace `YOUR_POSTGRES_PASSWORD` with your actual PostgreSQL password. For example, if your password is `myPassword123`, the URL becomes:

```text
DATABASE_URL=postgresql+psycopg://postgres:myPassword123@localhost:5432/stationery_shop
```

If your password contains special URL characters such as `@`, `:`, `/`, or `#`, URL-encode those characters. Keep `.env` private and do not share your database password.

## 3. Install Python dependencies and start the backend

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

If you already created `.venv`, just activate it and install the updated requirements. If PowerShell blocks activation, run this for the current terminal first:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

The app creates its tables and seeds the demo shopkeeper and starter products in PostgreSQL automatically at first startup. For Neon, create the database in your Neon project and set `DATABASE_URL` to its connection string; a local PostgreSQL server is not required.

Backend API: http://127.0.0.1:8000
Interactive API docs: http://127.0.0.1:8000/docs

## 4. Start the frontend (open a SECOND terminal)

```powershell
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite, usually http://localhost:5173.

## Database and deployment notes

The backend reads `DATABASE_URL` and `SECRET_KEY` from `backend/.env` locally, or from environment variables supplied by your deployment host. The example file is a template: set `DATABASE_URL` to the connection string from Neon and set `SECRET_KEY` to a long random value. Keep both values private. Standard Neon `postgresql://` URLs are supported using the Psycopg 3 driver.

For deployment, add `DATABASE_URL` and `SECRET_KEY` to the backend service's environment settings; do not rely on a local `.env` file or SQLite storage. The Neon database remains persistent across deployments. Existing data in `backend/stationery.db` is **not automatically copied** to PostgreSQL; the PostgreSQL database will be seeded with the demo shopkeeper and starter products on first startup.

## Database Tools & Utilities

You can manage and inspect your PostgreSQL database using `backend/db_admin.py`:

```powershell
cd backend

# 1. Test your database connection:
python db_admin.py test

# 2. View current record counts in the database:
python db_admin.py status

# 3. Initialize tables and seed demo shopkeeper and products:
python db_admin.py init

# 4. Migrate existing data from SQLite (stationery.db) to PostgreSQL:
python db_admin.py migrate

# 5. Run automated test suite:
python -m pytest tests/ -v
```

## Main API routes
- `GET /api/health` - Check API and PostgreSQL database health status
- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/products`, `POST /api/products`, `PUT /api/products/{id}`, `DELETE /api/products/{id}`
- `POST /api/sales`, `GET /api/sales`
- `GET /api/dashboard`


## Important security notes
This is a learning/demo project. The initial shopkeeper account is seeded with a known demo password. Change it before any real use. Set a strong random `SECRET_KEY` in `.env` before deployment. Do not expose this development server publicly. For production, add account creation/password-change workflows, stronger operational controls, tests, backups, and a more complete audit trail.
