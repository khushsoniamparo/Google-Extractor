# Project Review Checklist

- [ ] Check `.env` for production settings and presence.
- [ ] Review `settings.py` (DEBUG, SECRET_KEY, ALLOWED_HOSTS, etc.).
- [ ] Check `requirements.txt` for all necessary dependencies.
- [ ] Remove or convert `print()` calls to proper logging.
- [ ] Verify database migrations are up-to-date.
- [ ] Check for hardcoded credentials or API keys (besides what's in .env).
- [ ] Ensure static files are configured for production (COLLECTSTATIC).
- [ ] Verify core functionality (Scraper, Accounts, Billing).
- [ ] Review any remaining TODOs or commented-out code.
