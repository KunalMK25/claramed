# ClaraMed Deployment Guide

## Prerequisites

- Docker and Docker Compose
- PostgreSQL 15+ (for production)
- Redis 7+
- Python 3.11+
- Tesseract OCR
- Groq API Key

## Local Development with Docker Compose

### 1. Environment Setup

Create `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and set:
```
GROQ_API_KEY=your_actual_groq_api_key
```

### 2. Start All Services

```bash
docker-compose up -d
```

This starts:
- PostgreSQL database (port 5432)
- Redis (port 6379)
- FastAPI backend (port 8000)
- Celery worker
- Streamlit frontend (port 8501)

### 3. Verify Deployment

**Backend Health:**
```bash
curl http://localhost:8000/api/v1/health
```

**Frontend:**
Open http://localhost:8501

**API Documentation:**
Open http://localhost:8000/api/docs

### 4. View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f worker
```

### 5. Stop Services

```bash
docker-compose down
```

## Production Deployment

### Database Setup

Use managed PostgreSQL (AWS RDS, Google Cloud SQL, Azure Database):

```sql
CREATE DATABASE claramed;
CREATE USER claramed WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE claramed TO claramed;
```

### Environment Variables (Production)

```env
APP_ENV=production
DEBUG=False

DATABASE_URL=postgresql://claramed:password@db.example.com:5432/claramed
REDIS_URL=redis://redis.example.com:6379/0

GROQ_API_KEY=sk_prod_...

STORAGE_PROVIDER=s3
STORAGE_BUCKET=claramed-prod
STORAGE_ACCESS_KEY=...
STORAGE_SECRET_KEY=...

API_KEY_HASH_SECRET=random_secure_string_here
SECRET_KEY=random_secure_jwt_secret_here
```

### Run Database Migrations

```bash
alembic upgrade head
```

### Start Backend

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Start Celery Worker

```bash
celery -A backend.workers.celery_app worker --loglevel=info --concurrency=2
```

### Start Frontend

```bash
streamlit run app_new.py --server.port=8501 --server.address=0.0.0.0
```

## Platform-Specific Deployments

### Render.com

**Backend (Web Service):**
- Build Command: `pip install -r requirements.txt`
- Start Command: `alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- Add PostgreSQL database
- Add Redis instance
- Set environment variables

**Worker (Background Worker):**
- Build Command: `pip install -r requirements.txt`
- Start Command: `celery -A backend.workers.celery_app worker --loglevel=info`
- Use same database and Redis

**Frontend (Web Service):**
- Build Command: `pip install -r requirements.txt`
- Start Command: `streamlit run app_new.py --server.port=$PORT --server.address=0.0.0.0`

### Railway

Deploy using docker-compose or separate services similar to Render.

### AWS ECS/Fargate

Use provided Dockerfile and docker-compose.yml as reference for task definitions.

## Health Checks

Configure health check endpoints:

- Backend: `GET /api/v1/health`
- Frontend: `GET /_stcore/health`

## Monitoring

Recommended tools:
- Sentry (error tracking)
- Datadog/New Relic (APM)
- CloudWatch (AWS)

## Backup Strategy

**Database:**
- Automated daily backups
- Point-in-time recovery enabled
- 7-day retention minimum

**File Storage:**
- S3 versioning enabled
- Lifecycle policies for old files

## Scaling

**Backend:**
- Horizontal scaling: Add more API instances
- Load balancer required

**Workers:**
- Scale Celery workers based on queue depth
- Monitor Redis queue size

**Database:**
- Use read replicas for analytics
- Connection pooling (PgBouncer)

## Security Checklist

- [ ] HTTPS enabled (TLS 1.3)
- [ ] API keys rotated
- [ ] Database credentials secure
- [ ] S3 buckets private
- [ ] CORS configured properly
- [ ] Rate limiting enabled
- [ ] Logging configured (no PHI in logs)
- [ ] Regular security updates

## Troubleshooting

### Backend won't start

Check logs:
```bash
docker-compose logs backend
```

Common issues:
- Database connection failed → Check DATABASE_URL
- Groq API key missing → Set GROQ_API_KEY
- Port already in use → Change port in docker-compose.yml

### Worker not processing jobs

```bash
docker-compose logs worker
```

Check:
- Redis connection
- Queue has jobs: `redis-cli LLEN celery`

### Frontend can't connect to backend

Check BACKEND_URL environment variable in frontend service.

## Performance Optimization

**Model Caching:**
- TorchXRayVision model cached in `/app/models/cache`
- First inference downloads model (~200MB)
- Subsequent inferences use cached model

**Database:**
- Add indexes on frequently queried fields
- Use connection pooling

**File Storage:**
- Use CDN for file downloads
- Enable S3 transfer acceleration
