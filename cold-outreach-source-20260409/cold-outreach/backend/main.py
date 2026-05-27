import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()

from database import engine, Base
import models  # register all ORM models

from routers import auth, leads, activities, gmail, ai, stats, scraper, scoring, bulk, sequences
from routers import templates, email_scheduler, tracking, reports
from routers import contacts, tags, attachments, ab_test, webhooks, notifications, analytics, keyword_tracker, weekly_report
from routers import cadence, call_log, enrich, icp, signals


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create tables on startup
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"[startup] create_all skipped: {e}")
    # Migration: add drive_url / drive_name columns and make file_data nullable
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE attachments ADD COLUMN IF NOT EXISTS drive_url VARCHAR(1000)"))
            conn.execute(text("ALTER TABLE attachments ADD COLUMN IF NOT EXISTS drive_name VARCHAR(500)"))
            conn.execute(text("ALTER TABLE attachments ALTER COLUMN file_data DROP NOT NULL"))
            conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS website VARCHAR(500)"))
            # Round 4: Cadence & Engagement
            conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS linkedin VARCHAR(500)"))
            conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS engagement_score INTEGER DEFAULT 0"))
            # Create cadences table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS cadences (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    steps JSON,
                    created_by UUID REFERENCES users(id),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            # Create cadence_enrollments table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS cadence_enrollments (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    cadence_id UUID REFERENCES cadences(id) ON DELETE CASCADE,
                    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
                    current_step INTEGER DEFAULT 0,
                    status VARCHAR(50) DEFAULT 'active',
                    enrolled_at TIMESTAMP DEFAULT NOW(),
                    next_action_at TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """))
            # Create cadence_step_logs table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS cadence_step_logs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    enrollment_id UUID REFERENCES cadence_enrollments(id) ON DELETE CASCADE,
                    step_index INTEGER,
                    step_type VARCHAR(50),
                    status VARCHAR(50) DEFAULT 'pending',
                    note TEXT,
                    executed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            # Create email_clicks table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS email_clicks (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    email_id VARCHAR(255),
                    lead_id UUID REFERENCES leads(id) ON DELETE SET NULL,
                    url VARCHAR(2000),
                    clicked_at TIMESTAMP DEFAULT NOW(),
                    ip VARCHAR(50)
                )
            """))
            # Create call_logs table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS call_logs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
                    caller_id UUID REFERENCES users(id),
                    duration_seconds INTEGER,
                    outcome VARCHAR(100),
                    note TEXT,
                    called_at TIMESTAMP DEFAULT NOW()
                )
            """))
            # Round 5: MQL/SQL statuses, ICP profiles
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS icp_profiles (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(255) NOT NULL,
                    industries TEXT[] DEFAULT '{}',
                    company_sizes TEXT[] DEFAULT '{}',
                    titles TEXT[] DEFAULT '{}',
                    locations TEXT[] DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            # Round 6: 含金量欄位
            conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS ad_signals JSONB"))
            conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS tech_signals JSONB"))
            conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS social_signals JSONB"))
            conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS ops_signals JSONB"))
            conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS market_signals JSONB"))
            conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS wallet_signals JSONB"))
            conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS enriched_score INTEGER"))
            # Company Basic Info
            conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS tax_id VARCHAR(20)"))
            conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS representative_name VARCHAR(255)"))
            conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS capital_amount VARCHAR(50)"))
            conn.commit()
    except Exception as e:
        print(f"Migration skip: {e}")
    yield


app = FastAPI(
    title="Cold Outreach Platform",
    version="1.0.0",
    lifespan=lifespan,
)

# ── API Routers ────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(leads.router)
app.include_router(activities.router)
app.include_router(gmail.router)
app.include_router(ai.router)
app.include_router(stats.router)
app.include_router(scraper.router)
app.include_router(scoring.router)
app.include_router(bulk.router)
app.include_router(sequences.router)
app.include_router(templates.router)
app.include_router(email_scheduler.router)
app.include_router(tracking.router)
app.include_router(reports.router)
app.include_router(contacts.router)
app.include_router(tags.router)
app.include_router(attachments.router)
app.include_router(ab_test.router)
app.include_router(webhooks.router)
app.include_router(notifications.router)
app.include_router(analytics.router)
app.include_router(keyword_tracker.router)
app.include_router(weekly_report.router)
app.include_router(cadence.router)
app.include_router(call_log.router)
app.include_router(enrich.router)
app.include_router(icp.router)
app.include_router(signals.router)

# ── Static files (frontend build) ─────────────────────────────────────────────
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

if os.path.isdir(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        index = os.path.join(STATIC_DIR, "index.html")
        return FileResponse(index)
