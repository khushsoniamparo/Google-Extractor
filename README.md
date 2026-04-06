# 🌐 Google Extractor Platform
### *Enterprise-Grade Lead Generation & Protocol Automation*

[![Version](https://img.shields.io/badge/Version-1.2.0-blue.svg)](https://github.com/khushsoniamparo/Google-Extractor)
[![Backend](https://img.shields.io/badge/Backend-Django-092e20.svg)](https://www.djangoproject.com/)
[![Scraper](https://img.shields.io/badge/Engine-Scrapling-orange.svg)](https://github.com/D4Vinci/Scrapling)

## 📖 Executive Summary
The **Google Extractor Platform** is a high-fidelity, full-stack SaaS solution designed for precise lead generation from Google Maps. Built with a "Protocol-First" philosophy, it empowers users to transform geographic search vectors into actionable business intelligence through a sleek, premium dashboard.

---

## ⚡ Core Features

### 🔍 Precision Extraction Engine
*   **Dual-Search Strategy**: Choose between **Fast** (144 cells) for quick results or **Ultra** (625 cells) for deep-core data mining.
*   **Bulk Identifier Processing**: Input multiple keywords and locations simultaneously to scale your lead generation exponentially.
*   **Real-Time Live Monitor**: Pulse-based status updates let you watch the extraction "yield" as it happens with live progress indicators.

### 💳 Premium Transaction Architecture
*   **Multi-Gateway Integration**: Seamlessly syncs with **Razorpay, PayPal,**, and **Paytm** for secure licensing.
*   **Dynamic Subscription Tiers**: Starter, Premium Pro, and Professional Pro tiers with varying lead limits and extraction intensities.

### 👤 Identity & Analytics Dashboard
*   **High-Fidelity Profile**: A data-dense user dashboard with real-time counters for Total Leads, Units Used, and Protocol Success rates.
*   **Extraction Protocol Log**: A sophisticated history view for auditing past runs, checking timestamps, and reviewing lead "yields".

---

## 🛠️ Technical Infrastructure

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Backend** | Django & REST Framework | Core logic, secure routing, and API orchestration. |
| **Engine** | Scrapling + StealthFetcher | High-performance, undetectable web scraping. |
| **Frontend** | Vanilla JS & CSS3 | Ultra-performance UI with "I/O" inspired aesthetics. |
| **Asynchronous** | Celery & Redis | Managing long-running extraction tasks in the background. |
| **Authentication** | Firebase & JWT | Robust multi-method login (Google, Phone, Email/Pass). |
| **Persistence** | PostgreSQL (or SQLite) | Relational database for user profiles, jobs, and billing. |

---

## 🚀 Installation & Deployment

### 1. Repository Setup
```bash
git clone https://github.com/khushsoniamparo/Google-Extractor.git
cd google-extractor
```

### 2. Environment Configuration
Create a `.env` file in the root directory:
```env
DEBUG=True
SECRET_KEY=your_secret_key
DATABASE_URL=your_db_connection
RAZORPAY_KEY_ID=your_key
RAZORPAY_KEY_SECRET=your_secret
FIREBASE_SERVICE_ACCOUNT_PATH=firebase-adminsdk.json
```

### 3. Dependency Injection
```bash
python -m venv venv
source venv/bin/activate  # venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 4. Database Sync & Protocol Start
```bash
python manage.py migrate
python manage.py runserver
```
*Note: Ensure **Redis** is running for Celery task processing.*

---

## 🎨 Aesthetic Design Principles
The platform follows the **"I/O Protocol"** design language:
*   **Palette**: Deep slate, vibrant orange accents (`#f97316`), and clean white surfaces.
*   **Typography**: High-weight sans-serif for headers (800+) to convey authority and precision.
*   **Animations**: Subtle CSS transitions and hover-scale effects on interactive cards and buttons.

---

## ⚖️ Disclaimer
This tool is intended for ethical data gathering and research purposes only. Please respect the Terms of Service of target platforms and local data privacy laws.

---
*Built with ❤️ for High-Performance Extraction.*
