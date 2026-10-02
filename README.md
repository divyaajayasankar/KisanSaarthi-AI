# KisanSaarthi AI — Starter

This starter gets the first research-safe vertical slice running:

Browser frontend -> FastAPI -> PostgreSQL registry lookup -> deterministic constraint engine -> response.

## Important
The included registry seed is TEST-ONLY synthetic software data. It is not agricultural advice and must never be used in experiments, reports, or farmer-facing deployment.

## Start
1. Copy `.env.example` to `.env`
2. `docker compose up -d postgres redis chromadb minio`
3. Create Python 3.11 virtual environment
4. `pip install -r requirements.txt`
5. `python scripts/init_db.py`
6. `python scripts/seed_test_only.py`
7. `uvicorn app.main:app --reload`
8. Open `http://127.0.0.1:8000`

## Demo values
- crop: `demo_crop`
- pest: `demo_pest`
- area: `0.5 hectare`
- harvest: `20 days`

Expected: recommendation with 50 ml TEST dose.
Change harvest to 6 days. Expected: abstention because PHI=10 days.
