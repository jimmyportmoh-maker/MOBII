# Mobi Hub — Global Service Marketplace (Admin Core)
FastAPI + SQLAlchemy (PostgreSQL in production, SQLite local/offline mode), bcrypt, JWT, role-based access.

## Run
    python -m venv .venv && source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
    pip install -r requirements.txt
    cp .env.example .env   # then set the values below
    uvicorn app.main:app --reload
Open http://localhost:8000 and sign in with ADMIN_EMAIL / ADMIN_PASSWORD. API docs: /docs.

## Production database and admin configuration
- Create a PostgreSQL database service for Mobi Hub and set the web service's DATABASE_URL to that database's connection URL.
- Set ADMIN_EMAIL to jimmyportmoh@gmail.com.
- Set ADMIN_PASSWORD to the administrator password in the hosting provider's private environment-variable settings. Do not commit real passwords to Git.
- Set SECRET_KEY to a long, random secret.
- The app accepts postgres:// and postgresql:// URLs and normalizes them for psycopg 3. SQLite remains available for local/offline development.
- On startup, the seed routine creates the Super Admin if none exists, or updates the existing Super Admin email and password from these environment variables.

For local PostgreSQL, run `docker compose up -d` and configure DATABASE_URL as shown in .env.example.

## Included
- Auth: bcrypt hashing, JWT (8h), customer/provider registration, 7 admin roles (super, verification, operations, finance, support, catalogue, analytics)
- Admin dashboard: overview, users, providers, verification docs, industries/categories, services, bookings, payments + refunds, reviews, disputes, audit log, settings
- Global catalogue: 26 industries with subcategories seeded; unlimited depth, add/disable anything from the UI (no code change)
- Provider verification: document upload to private storage, status workflow, every document view is audit-logged
- Audit trail on every admin write

## Not yet built (next steps)
M-Pesa Daraja integration (payments table is ready), notification sending (SMS/email/push), offline sync engine
(SQLite local mode + `synced` flag on bookings are the groundwork), analytics charts, customer/provider web portals,
file encryption at rest, refresh tokens, migrations (Alembic), rate limiting.

## v2: portals + manual escrow
- Customer & provider portal: `/` | Staff admin dashboard: `/admin`
- Providers register, fill profile (services, payout details), upload ID/licences (private storage, JPG/PNG/PDF, 8 MB). Admin cannot approve a provider without an ID document and payout details. 
- Manual escrow flow: customer books -> pays platform by M-Pesa/bank (instructions editable in Admin > Settings: `escrow_instructions`) and enters the code ->
  Finance admin checks the platform account and clicks **confirm** -> provider delivers -> customer approves (or disputes) ->
  Finance admin pays the provider by hand and records the payout reference (**release**), or pays the customer back (**refund**). Every step is logged (Escrow > history).
- Payment codes can't be reused across bookings. If you used v1 before, do not delete your production database; use a proper migration strategy for schema changes.
