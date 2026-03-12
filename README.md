# CompetencyHub API

FastAPI backend for a web app designed to:
- building competency models for professions using expert evaluation and OPA method;
- candidate selection based on the created competency model with VIKOR.

The knowledge base is built on top of the ESCO taxonomy and scraped job descriptions.

This service uses the ESCO classification of the European Commission.

## What The System Does

The backend supports three main flows.

1. Knowledge base
- stores professions, profession groups, competencies, competency groups;
- stores ESCO labels, collections, hierarchy memberships, profession-competency links;
- stores scraped jobs and extracted job competencies.

2. Competency models
- a user creates a competency model for a profession;
- the system suggests competencies from ESCO profession-skill relations;
- the user adds experts, criteria, alternatives;
- experts rank criteria and alternatives;
- OPA calculates final weights of competencies.

3. Candidate selection
- a user creates a selection based on a completed competency model;
- the user adds candidates and uploads CV files;
- CV files are stored in Supabase Storage and parsed into competencies;
- experts score candidates against final competencies from the model;
- VIKOR ranks candidates.

## Tech Stack

- FastAPI
- SQLAlchemy 2.0 async
- PostgreSQL / Supabase
- Supabase Storage
- spaCy
- PuLP / SciPy

## Project Layout

```text
app/
  api/v1/
    endpoints/
      auth.py
      knowledge_base.py
      competency_models.py
      candidate_selection.py
    dependencies.py
    router.py
  core/
    config.py
    enums.py
    security.py
  db/
    session.py
  models/
    models.py
  schemas/
    auth.py
    knowledge_base.py
    competency_model.py
    candidate_selection.py
  services/
    auth_service.py
    knowledge_base_service.py
    competency_model_service.py
    candidate_selection_service.py
    document_processing_service.py
    storage_service.py
    opa_service.py
    vikor_service.py
  main.py

migrations/
  schema.sql
  004_candidate_selection_storage_and_invites.sql

scripts/
  seed_knowledge_base.py
  scrape_jobs.py

tests/
  knowledge_base/test_api.py
  competency_models/test_api.py
  candidate_selection/test_api.py
  smoke_common.py
```

## Architectural Rules

The codebase follows a simple layered structure.

- `endpoints`:
  HTTP layer only.
  Parses request data, injects dependencies, calls services.

- `schemas`:
  Pydantic request/response models.
  They define the API contract.

- `services`:
  Business logic.
  They enforce workflow rules, permissions, validation, and calculations.

- `models`:
  SQLAlchemy ORM models.
  They mirror the database structure.

- `db/session.py`:
  creates the async engine, session factory, and `get_db` dependency.

This is a good structure for a first API because responsibilities are separated:
- routers do not contain heavy logic;
- services do not care about HTTP details;
- schemas do not contain database logic.

## Database Structure

There are three logical schemas in PostgreSQL.

### `job`
- professions
- profession groups
- competencies
- competency groups
- labels
- collections
- profession-competency links
- jobs
- job competencies

### `competency_model`
- models
- experts
- expert invites
- criteria
- alternatives
- expert rankings for OPA

### `candidate_evaluation`
- selections
- candidates
- candidate competencies
- experts
- expert invites
- candidate scores for VIKOR

## Setup

### 1. Install dependencies

```powershell
pip install -r requirements.txt
```

### 2. Install spaCy model

```powershell
python -m spacy download en_core_web_sm
```

### 3. Configure environment

Create `.env` based on `.env.example`.

Required variables:
- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SECRET_KEY`

Optional variables:
- `SUPABASE_ANON_KEY`
- `SUPABASE_CV_BUCKET`
- `CV_SIGNED_URL_EXPIRE_SECONDS`
- `BACKEND_CORS_ORIGINS`
- `BACKGROUND_JOBS_ENABLED`
- `BACKGROUND_JOBS_POLL_SECONDS`
- `JOB_DERIVED_MIN_COUNT`
- `JOB_DERIVED_MIN_FREQUENCY`
- `EMAILS_ENABLED`
- `EMAIL_FROM`
- `EMAIL_REPLY_TO`
- `FRONTEND_BASE_URL`
- `RESEND_API_KEY`
- `EMAIL_DEADLINE_REMINDER_DAYS`

`BACKEND_CORS_ORIGINS` is a comma-separated list of frontend origins allowed to call the API from a browser.

Example:

```text
BACKEND_CORS_ORIGINS=http://localhost:3000,http://localhost:5173,https://your-frontend-domain.app
```

Notes:
- in local development, if `BACKEND_CORS_ORIGINS` is empty and `ENVIRONMENT=development`, the API allows all origins;
- in production, set explicit frontend origins instead of relying on `*`.
- background jobs are disabled by default; enable them explicitly only on the instance that should process deadlines.
- transactional emails are disabled by default; set `EMAILS_ENABLED=true`, `EMAIL_FROM`, and `RESEND_API_KEY` to enable Resend delivery;
- `FRONTEND_BASE_URL` is used in email templates to point users back to the app;
- deadline reminders are sent by the background runner and deduplicated through the `emails` log table.

### 4. Apply database schema

For a fresh database:
- run `migrations/schema.sql`

For an existing database that already has `public.emails`:
- run `migrations/versions/20260312_email_subsystem.sql`

### 5. Seed the knowledge base

The knowledge base uses two external data sources:
- ESCO EN CSV zip;
- scraped job descriptions stored in `scraped_jobs.json`.

#### 5.1 Scrape jobs

Use `scripts/scrape_jobs.py` to collect vacancies from public APIs and save them to JSON.

Sources used by the script:
- Arbeitnow
- RemoteOK
- Arbeitnow API page: `https://www.arbeitnow.com/blog/job-board-api`
- Arbeitnow terms: `https://www.arbeitnow.com/terms`
- RemoteOK API: `https://remoteok.io/api`

Important:
- ESCO data requires attribution. This repository and the API docs include the notice: `This service uses the ESCO classification of the European Commission.`
- Vacancy sources are subject to their own API and website terms. Before using scraped jobs outside local research, diploma work, or internal experiments, review the source-specific legal conditions and attribution requirements.

Default output:
- `scraped_jobs.json`

Default target:
- `200` jobs per position

Example:

```powershell
.\.venv\Scripts\python.exe scripts\scrape_jobs.py
```

Custom target and output file:

```powershell
.\.venv\Scripts\python.exe scripts\scrape_jobs.py --target 100 --output scraped_jobs.json
```

The script currently collects jobs for these positions:
- Data Analyst
- Software Engineer
- DevOps Engineer
- Product Manager
- Data Scientist
- Machine Learning Engineer
- Front End Developer
- Quality Assurance Engineer
- Cybersecurity Analyst
- Cloud Architect

#### 5.2 Seed ESCO and jobs into the database

The seeder imports ESCO data from the EN CSV zip and the scraped jobs JSON.

```powershell
.\.venv\Scripts\python.exe scripts\seed_knowledge_base.py
```

Optional flags:

```powershell
.\.venv\Scripts\python.exe scripts\seed_knowledge_base.py --jobs-only
.\.venv\Scripts\python.exe scripts\seed_knowledge_base.py --skip-jobs
.\.venv\Scripts\python.exe scripts\seed_knowledge_base.py --reset-job-data
```

The script expects the ESCO zip path in `scripts/seed_knowledge_base.py`.

### 6. Run the API

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Docs:
- `http://127.0.0.1:8000/api/v1/docs`

If you test a local frontend against a deployed API, add the local frontend origin to `BACKEND_CORS_ORIGINS`, for example:
- `http://localhost:3000`
- `http://localhost:5173`

## Background Jobs

The API can poll for overdue evaluations and process them automatically.

Environment variables:
- `BACKGROUND_JOBS_ENABLED=true|false`
- `BACKGROUND_JOBS_POLL_SECONDS=60`

Current automated actions:
- calculate OPA for competency models whose expert-evaluation deadline has passed;
- calculate VIKOR for selections whose expert-evaluation deadline has passed;
- cancel a selection automatically if its deadline has passed but the scoring matrix is incomplete.

Recommended deployment rule:
- enable background jobs only on one instance or one dedicated worker process to avoid duplicate processing.

## Storage

Candidate CV files are stored in Supabase Storage.

- bucket name defaults to `candidate-cvs`;
- the backend uses `SUPABASE_SERVICE_ROLE_KEY`;
- files are accessed through signed URLs;
- the bucket can be created automatically on first use, but it is still worth verifying in the Supabase dashboard.

## Deployment

The API is deployed on Railway.

Public URLs:
- API docs: `https://competency-hub-api-production.up.railway.app/api/v1/docs`
- OpenAPI schema: `https://competency-hub-api-production.up.railway.app/api/v1/openapi.json`
- Health check: `https://competency-hub-api-production.up.railway.app/health`

## Tests

Smoke tests are plain Python scripts that call the running API.

Run them with the server already started:

```powershell
.\.venv\Scripts\python.exe tests\knowledge_base\test_api.py
.\.venv\Scripts\python.exe tests\competency_models\test_api.py
.\.venv\Scripts\python.exe tests\candidate_selection\test_api.py
```

What they cover:
- CRUD and workflow endpoints;
- access rules;
- invite flows;
- negative validation cases;
- OPA and VIKOR happy paths.

## Main API Areas

### Auth
- `/api/v1/auth/*`

### Knowledge base
- `/api/v1/profession-groups`
- `/api/v1/professions`
- `/api/v1/competency-groups`
- `/api/v1/competencies`
- `/api/v1/jobs`

### Competency models
- `/api/v1/competency-models/*`
- `/api/v1/expert/competency-models/*`
- `/api/v1/expert/competency-model-invites/*`

### Candidate selection
- `/api/v1/selections/*`
- `/api/v1/candidates/*`
- `/api/v1/expert/selections/*`
- `/api/v1/expert/selection-invites/*`

## Notes

- ESCO raw datasets are not committed to git.
- `scraped_jobs.json` is also ignored.
- The backend currently focuses on English ESCO data.
