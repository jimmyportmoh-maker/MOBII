# Mobi Hub — Global Service Marketplace (Admin Core)
FastAPI + SQLAlchemy (PostgreSQL in production, SQLite local/offline mode), bcrypt, JWT, role-based access.

## Run
    python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    cp .env.example .env   # then export its values (or set them in your shell)
    uvicorn app.main:app --reload
Open http://localhost:8000 and sign in with ADMIN_EMAIL / ADMIN_PASSWORD. API docs: /docs.
For PostgreSQL: `docker compose up -d`, then set DATABASE_URL (see .env.example).

## Included
- Auth: bcrypt hashing, JWT (8h), customer/provider registration, 7 admin roles (super, verification, operations, finance, support, catalogue, analytics)
- Admin dashboard: overview, users, providers, verification docs, industries/categories, services, bookings, payments + refunds, reviews, disputes, audit log, settings
- Global catalogue: 26 industries with subcategories seeded; unlimited depth, add/disable anything from the UI (no code change)
- Provider verification: document upload to private storage, status workflow, every document view is audit-logged
- Audit trail on every admin write

## Not yet built (next steps)
M-Pesa Daraja integration (payments table is ready), notification sending (SMS/email/push), offline sync engine
(SQLite local mode + `synced` flag on bookings are the groundwork), analytics charts, customer/provider web portals,
file encryption at rest, refresh tokens, migrations (Alembic), rate limiting. Set a strong SECRET_KEY and change the seeded admin password before any real use.

## v2: portals + manual escrow
- Customer & provider portal: `/`  |  Staff admin dashboard: `/admin`
- Providers register, fill profile (services, payout details), upload ID/licences (private storage, JPG/PNG/PDF, 8 MB). Admin cannot approve a provider without an ID document and payout details.
- Manual escrow flow: customer books -> pays platform by M-Pesa/bank (instructions editable in Admin > Settings: `escrow_instructions`) and enters the code ->
  Finance admin checks the platform account and clicks **confirm** -> provider delivers -> customer approves (or disputes) ->
  Finance admin pays the provider by hand and records the payout reference (**release**), or pays the customer back (**refund**). Every step is logged (Escrow > history).
- Payment codes can't be reused across bookings. If you used v1 before, delete `mobihub_local.db` once (new tables/columns).
