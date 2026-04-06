# 🐘 Extractor Platform: Development & Migration Log

This document tracks the critical technical transitions made to ensure the platform is production-ready and high-performance.

## 🛠️ Phase 1: PostgreSQL Migration
The platform has officially transitioned from a local SQLite engine to a production-grade **PostgreSQL** database.

*   **Database Name**: `scraper_prod_db`
*   **User/Schema**: `postgres` (Superuser)
*   **Driver**: `psycopg[binary]` (v3) — chosen for Python 3.13 stability.
*   **Host Logic**: Switched to `127.0.0.1` (with `localhost` fallback documented) to resolve Windows timeout issues.
*   **Schema Sync**: All Django migrations (Accounts, Jobs, Billing, Sessions) have been applied to the new environment.

## 🕊️ Phase 2: Professional SMTP Integration
The email notification system was hardened to ensure reliable delivery of Admin OTPs.

*   **Server**: `7shouters.com` (Direct IP resolution confirmed: `103.191.208.137`)
*   **Port**: `587` (STARTTLS) — selected over 465 for superior cPanel/Exim compatibility.
*   **Security Protocol**: `EMAIL_USE_TLS=True`
*   **Configuration**: The `.env` file was sanitized to remove conflicting quotes in the host password.

## 🔳 Phase 3: High-Fidelity UI Hardening
The "Omega" Dark Theme was refined to resolve visibility "messes" in the user profile dashboard.

*   **Variable Integration**: Replaced hardcoded `background: white` with theme-aware `var(--card-bg)`.
*   **Dynamic Borders**: Hardcoded colors in the "Settings" panel now adapt to the global `data-theme="dark"` attribute.
*   **Danger Zone**: Redesigned the "Terminate Protocol" section with a distinctive, safe accent soft-color background.

## 🔐 Phase 4: Administrative Security (Intel Hub)
The specialized Admin Login now features a dual-layer authentication check.

1.  **Email OTP**: Triggered via `7shouters.com` to the authorized master email (`sonikhush004@gmail.com`).
2.  **Security Mirror (Terminal)**: For developer convenience during setup, the **OTP and Master Clearance Secret** are mirrored to the `runserver` console.

## 💎 Phase 5: Resource Initialization (Seeding)
A clean database is a non-functional one. I have initialized the core subscription tiers:

*   **Starter**: 2,000 Leads
*   **Professional**: 10,000 Leads (Featured Tier)
*   **Enterprise**: 500,000 Leads (Custom Grid)

---

### 🚀 Developer Instructions for New Instances:
1.  **Install Postgres**: Ensure a server is listening on port `5432`.
2.  **Create DB**: Use `pgAdmin` to create `scraper_prod_db`.
3.  **Sync**: Run `python manage.py migrate`.
4.  **Seed**: Run `python seed_packages.py`.
5.  **Identify**: Type `sonikhush004@gmail.com` into the Intel Hub to begin the extraction.

**Current Deployment State**: `STABLE | PostgreSQL Active | Omega Dark UI Fixed` 🚀🔭🏆
