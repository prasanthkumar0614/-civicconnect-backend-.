# CivicConnect Backend — Ready to Run

This is the complete, assembled backend: Django project scaffold + your
original app files (api.py, permissions.py, services) + models split into
each app + a working requirements.txt + SQLite-by-default settings.

## First-time setup

Open a terminal in this folder (the one with `manage.py` in it), then:

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations accounts core assets issues
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Visit http://127.0.0.1:8000/admin/ and log in with the superuser you just
created to confirm it's working.

## Notes

- **Database**: runs on SQLite by default (`USE_SQLITE=True` in `.env`) —
  no PostgreSQL install needed. To switch to PostgreSQL later: install
  PostgreSQL, uncomment `psycopg2-binary` in `requirements.txt`, run
  `pip install -r requirements.txt` again, set `USE_SQLITE=False` and fill in
  `DB_NAME`/`DB_USER`/`DB_PASSWORD` in `.env`.
- **AI classification**: works without any key — issues just save without
  AI fields filled in if `ANTHROPIC_API_KEY` is blank in `.env`. Add a real
  key there to turn on real classification via the Claude API.
- **Auth**: JWT-based (`djangorestframework-simplejwt`). Get a token at
  `POST /api/auth/token/` with `username`/`password`.
- **Frontend CORS**: `.env`'s `CORS_ALLOWED_ORIGINS` already allows
  `localhost:5173` and `localhost:5174` — the two React dev server ports.

## If `pip install` fails on a package

Your Python version matters here. If you're on a very new Python (3.14+),
some packages may not have prebuilt wheels yet. If a specific package fails
to build, tell me the exact error and I'll swap in a version that has a
compatible wheel.
