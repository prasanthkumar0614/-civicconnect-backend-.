# CivicConnect — Backend API

The backend for **CivicConnect**, an AI-powered civic issue reporting and management platform for Andhra Pradesh. Citizens report problems with public infrastructure (street lights, transformers, water pumps, etc.) tied to a structured Asset ID system, and the platform routes, classifies, and tracks each complaint through resolution.

🔗 **Live API:** https://civicconnect-p3mq.onrender.com
🔗 **Dashboard:** https://civicconnect-dashboard.vercel.app

## Features

- **Role-based access control** — Citizen, Officer, Department Admin, Mandal Head, and Super Admin roles, each scoped to exactly the data they should see
- **AI-powered triage** — every complaint is automatically classified by category, priority, and department using Google's Gemini API, with graceful fallback if the AI call fails
- **Duplicate detection** — flags likely-duplicate complaints on the same asset
- **Asset clustering** — detects nearby faulty assets reported around the same time, surfacing possible shared faults (e.g. a transformer issue knocking out several street lights)
- **Real government data** — all 28 official Andhra Pradesh districts and 683+ real mandal names, sourced from official reorganization notifications
- **Email notifications** — automatic status updates to citizens, officer assignment alerts, and high-priority escalations to department admins
- **Photo & video evidence** — citizens and officers can attach media to complaints

## Tech Stack

- **Framework:** Django + Django REST Framework
- **Database:** PostgreSQL
- **Auth:** JWT (djangorestframework-simplejwt)
- **AI:** Google Gemini API
- **Static files:** WhiteNoise
- **Deployment:** Render

## Local Setup

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py add_all_real_mandals
python manage.py fill_empty_mandals
python manage.py createsuperuser
python manage.py runserver
```

See `.env.example` for required environment variables.

## Project Structure

## Author

**Sodima Naga Prasanth Kumar**
B.Tech Electronics & Communication Engineering, Pace Institute of Technology and Sciences, Ongole
