# CivicConnect — Backend API

CivicConnect is an AI-powered civic issue reporting and management platform designed for Andhra Pradesh.

Citizens can report public infrastructure issues such as street-light failures, transformer problems, water-pump issues, drainage problems, road issues, and garbage-related issues. Complaints are connected to structured geographic areas and Asset IDs so that issues can be routed, classified, tracked, and resolved.

## Live Services

- **Live API:** https://civicconnect-p3mq.onrender.com
- **Dashboard:** https://civicconnect-dashboard.vercel.app

## Features

- **Role-based access control** — Citizen, Officer, Department Admin, Mandal Head, and Super Admin roles
- **AI-powered triage** — complaints can be classified using Google's Gemini API
- **Duplicate detection** — identifies possible duplicate complaints associated with the same asset
- **Asset clustering** — detects nearby faulty assets reported around similar times
- **Geographic hierarchy** — District → Mandal/Municipality → Village/Area → Ward → Asset
- **Real/reference geographic data** — Andhra Pradesh districts, mandal names, and village/area information from government/reference datasets
- **5 assumed wards per village/area** — application-generated structure for CivicConnect
- **Asset management** — structured Asset IDs for civic infrastructure
- **Email notifications** — complaint updates, officer assignments, and escalations
- **Photo & video evidence** — citizens and officers can attach supporting evidence

## Geographic Data

CivicConnect uses a structured geographic hierarchy:

```text
District
   ↓
Mandal / Municipality
   ↓
Village / Area
   ↓
Ward
   ↓
Asset
```

The production database currently contains:

- **28 districts**
- **90,665 wards**
- **7 configured asset types**
- **634,655 asset records**

### Important Note About Wards

CivicConnect creates **5 assumed wards per village/area** for application purposes.

These five wards are **project-generated assumptions** and should not be interpreted as official government ward boundaries.

## Data Sources & Attribution

Village/area information used by CivicConnect is based on a dataset compiled from the **Local Government Directory (LGD), Ministry of Panchayati Raj, Government of India**, through the referenced `india-village-finder` dataset.

The government/reference data and project-generated data are treated separately.

Project-generated data includes:

- Five assumed wards per village/area
- Generated asset records for ward coverage

These generated asset records are **application data** and should not be interpreted as an official government asset inventory.

## Asset Management

CivicConnect currently supports the following asset types:

| Asset Type | Prefix |
|---|---|
| Street Light | `SL` |
| Transformer | `TR` |
| Water Pump | `WP` |
| Water Tank | `WT` |
| Road | `RD` |
| Drainage Line | `DL` |
| Garbage Bin | `GB` |

## Author

**Sodima Naga Prasanth Kumar**

B.Tech Electronics & Communication Engineering  
Pace Institute of Technology and Sciences, Ongole

**Role:** Developer / Creator of CivicConnect

The author attribution refers to the development of the CivicConnect software. It does not claim authorship of government/reference datasets used by the project.
