# Sanaap API Challenge

A Django REST API-only project for document management with MinIO object storage, built with the Cookiecutter Django template.

## 🚀 Features

- **RESTful API** for document upload, download, and management
- **MinIO Object Storage** for scalable file storage
- **Role-Based Access Control (RBAC)** with django-guardian
- **Real-time WebSocket** support for upload status tracking
- **Asynchronous file processing** with Celery
- **Token-based authentication** for API access
- **Docker containerization** for easy deployment
- **nginx reverse proxy** in production
- **Comprehensive test suite** with pytest

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Local Development Setup](#local-development-setup)
- [Production Deployment](#production-deployment)
- [API Usage](#api-usage)
- [Architecture](#architecture)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## 🔧 Prerequisites

### For Local Development
- **Docker** and **Docker Compose** installed
- **Git** for version control
- **Python 3.13+** (if running outside Docker)
- **uv** package manager (for dependency management)

### For Production
- **Docker** and **Docker Compose** installed
- **Domain name** (optional but recommended)
- **SSL certificates** (for HTTPS)
- **Environment variables** configured

## 🏠 Local Development Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd sanaap_api_challenge
```

### 2. Environment Configuration

Create environment files for local development:

```bash
# Create environment directories
mkdir -p .envs/.local

# Create Django environment file
cat > .envs/.local/.django << 'EOF'
# General
USE_DOCKER=yes
IPYTHONDIR=/app/.ipython
DJANGO_DEBUG=True
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# Database
DATABASE_URL=postgres://debug:debug@postgres:5432/sanaap_api_challenge

# Redis
REDIS_URL=redis://redis:6379/0

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=password123
MINIO_BUCKET_NAME=sanaap-api-local
MINIO_USE_HTTPS=false
EOF

# Create PostgreSQL environment file
cat > .envs/.local/.postgres << 'EOF'
# PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=sanaap_api_challenge
POSTGRES_USER=debug
POSTGRES_PASSWORD=debug
EOF

# Create MinIO environment file
cat > .envs/.local/.minio << 'EOF'
# MinIO
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=password123
EOF
```

### 3. Start Development Environment

```bash
# Start all services
docker compose -f docker-compose.local.yml up

# Or start in background
docker compose -f docker-compose.local.yml up -d

# View logs
docker compose -f docker-compose.local.yml logs -f
```

### 4. Initialize Database

```bash
# Create and apply migrations
docker compose -f docker-compose.local.yml exec django python manage.py migrate

# Create superuser
docker compose -f docker-compose.local.yml exec django python manage.py createsuperuser

# Load sample data (optional)
docker compose -f docker-compose.local.yml exec django python manage.py loaddata fixtures/sample_data.json
```

### 5. Access Services

- **API Documentation**: http://localhost:8000/api/docs/
- **Django Admin**: http://localhost:8000/admin/
- **MinIO Console**: http://localhost:9001/
- **API Base URL**: http://localhost:8000/api/

## 🚀 Production Deployment

### 1. Environment Configuration

Create production environment files:

```bash
# Create environment directories
mkdir -p .envs/.production

# Create Django environment file
cat > .envs/.production/.django << 'EOF'
# General
USE_DOCKER=yes
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=your-super-secure-secret-key-here
DJANGO_ALLOWED_HOSTS=your-domain.com,www.your-domain.com
DJANGO_ADMIN_URL=secure-admin-path/

# Security settings
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=True
DJANGO_SECURE_HSTS_PRELOAD=True
DJANGO_SECURE_CONTENT_TYPE_NOSNIFF=True

# Database
DATABASE_URL=postgres://prod_user:secure_password@postgres:5432/sanaap_api_challenge_prod
CONN_MAX_AGE=60

# Redis
REDIS_URL=redis://redis:6379/0
EOF

# Create PostgreSQL environment file
cat > .envs/.production/.postgres << 'EOF'
# PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=sanaap_api_challenge_prod
POSTGRES_USER=prod_user
POSTGRES_PASSWORD=secure_password_here
EOF

# Create MinIO environment file
cat > .envs/.production/.minio << 'EOF'
# MinIO
MINIO_ROOT_USER=admin_prod
MINIO_ROOT_PASSWORD=SecureProductionPassword123!
EOF
```

### 2. Deploy Production Stack

```bash
# Build and start production services
docker compose -f docker-compose.production.yml up --build -d

# Apply migrations
docker compose -f docker-compose.production.yml exec django python manage.py migrate

# Collect static files
docker compose -f docker-compose.production.yml exec django python manage.py collectstatic --noinput

# Create superuser
docker compose -f docker-compose.production.yml exec django python manage.py createsuperuser
```

### 3. nginx Configuration

The production setup uses nginx as a reverse proxy with the following endpoints:

- **Port 80**: Main entry point
- **`/api/`**: Django API requests
- **`/admin/`**: Django admin interface
- **`/static/`**: Static files served by nginx
- **`/media/`**: Media files served by nginx
- **`/minio/`**: Direct MinIO API access
- **`/minio-console/`**: MinIO web console

### 4. SSL/HTTPS Setup (Recommended)

For production, set up SSL certificates:

```bash
# Using Let's Encrypt with certbot
sudo apt update
sudo apt install certbot python3-certbot-nginx

# Obtain certificates
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# Auto-renewal (add to crontab)
echo "0 12 * * * /usr/bin/certbot renew --quiet" | sudo crontab -
```

Update nginx configuration to use SSL:

```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Your existing configuration...
}
```

## 📚 API Usage

### Authentication

The API uses token-based authentication. First, obtain a token:

```bash
# Get authentication token
curl -X POST http://localhost:8000/api/auth-token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "your_username", "password": "your_password"}'

# Response
{
  "token": "your-auth-token-here"
}
```

Use the token in subsequent requests:

```bash
curl -H "Authorization: Token your-auth-token-here" \
  http://localhost:8000/api/endpoint/
```

### Document Management

#### Upload a Document

```bash
# Upload a small file (synchronous)
curl -X POST http://localhost:8000/api/documents/items/ \
  -H "Authorization: Token your-auth-token" \
  -F "file=@/path/to/document.pdf" \
  -F "title=My Document" \
  -F "description=Document description"

# Upload a large file (asynchronous)
curl -X POST http://localhost:8000/api/documents/items/ \
  -H "Authorization: Token your-auth-token" \
  -F "file=@/path/to/large-file.pdf" \
  -F "title=Large Document" \
  -F "description=Large document description"

# Response for async upload
{
  "document_id": 123,
  "upload_task_id": "task-uuid-here",
  "upload_status": "pending",
  "upload_status_url": "http://localhost:8000/api/documents/items/123/upload-status/",
  "is_async": true
}
```

#### Check Upload Status

```bash
# Check upload status
curl -H "Authorization: Token your-auth-token" \
  http://localhost:8000/api/documents/items/123/upload-status/

# Response
{
  "upload_status": "completed",
  "upload_progress": 100,
  "upload_task_id": "task-uuid-here",
  "upload_error_message": null,
  "file_info": {
    "size": 1048576,
    "content_type": "application/pdf"
  }
}
```

#### List Documents

```bash
# List all accessible documents
curl -H "Authorization: Token your-auth-token" \
  "http://localhost:8000/api/documents/items/"

# Filter documents
curl -H "Authorization: Token your-auth-token" \
  "http://localhost:8000/api/documents/items/?status=active&search=report"

# My documents
curl -H "Authorization: Token your-auth-token" \
  "http://localhost:8000/api/documents/my-documents/"
```

#### Download a Document

```bash
# Download document
curl -H "Authorization: Token your-auth-token" \
  -o downloaded-file.pdf \
  "http://localhost:8000/api/documents/items/123/download/"
```

#### Share a Document

```bash
# Share with a user
curl -X POST http://localhost:8000/api/documents/items/123/share/ \
  -H "Authorization: Token your-auth-token" \
  -H "Content-Type: application/json" \
  -d '{
    "shared_with_id": 456,
    "permission_level": "download",
    "expires_at": "2024-12-31T23:59:59Z"
  }'

# Bulk share with multiple users
curl -X POST http://localhost:8000/api/documents/items/123/bulk-share/ \
  -H "Authorization: Token your-auth-token" \
  -H "Content-Type: application/json" \
  -d '{
    "user_ids": [456, 789, 101],
    "permission_level": "view"
  }'
```

### WebSocket Support

For real-time upload status updates:

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/documents/123/upload-status/');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Upload progress:', data.progress);
    console.log('Status:', data.status);
};

ws.onopen = function(event) {
    console.log('Connected to upload status updates');
};
```

## 🏗️ Architecture

### System Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     nginx       │    │     Django      │    │     MinIO       │
│  (Reverse Proxy)│────│   (API Server)  │────│ (Object Storage)│
│     Port 80     │    │    Port 8000    │    │    Port 9000    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         │              │   PostgreSQL    │              │
         │              │   (Database)    │              │
         │              │    Port 5432    │              │
         │              └─────────────────┘              │
         │                       │                       │
         │              ┌─────────────────┐              │
         └──────────────│      Redis      │──────────────┘
                        │  (Cache/Queue)  │
                        │    Port 6379    │
                        └─────────────────┘
```

### Technology Stack

- **Backend**: Django 5.2.6 + Django REST Framework
- **Database**: PostgreSQL with psycopg
- **Cache/Queue**: Redis
- **File Storage**: MinIO object storage
- **Task Queue**: Celery
- **WebSockets**: Django Channels
- **Reverse Proxy**: nginx (production)
- **Authentication**: Token-based with django-guardian
- **Testing**: pytest
- **Code Quality**: ruff, mypy

### Directory Structure

```
sanaap_api_challenge/
├── config/                 # Django configuration
│   ├── settings/          # Environment-specific settings
│   ├── urls.py           # Main URL configuration
│   ├── api_router.py     # DRF API routing
│   └── celery_app.py     # Celery configuration
├── sanaap_api_challenge/  # Main application
│   ├── documents/        # Document management app
│   ├── utils/           # Utility modules
│   └── middleware.py    # Custom middleware
├── compose/              # Docker configurations
│   ├── production/      # Production containers
│   └── local/          # Local development containers
├── .envs/               # Environment variables
├── requirements/        # Python dependencies
└── tests/              # Test files
```

## 🧪 Testing

### Running Tests

```bash
# Run all tests
docker compose -f docker-compose.local.yml exec django pytest

# Run specific test file
docker compose -f docker-compose.local.yml exec django pytest sanaap_api_challenge/documents/tests/test_views.py

# Run with coverage
docker compose -f docker-compose.local.yml exec django coverage run -m pytest
docker compose -f docker-compose.local.yml exec django coverage html
docker compose -f docker-compose.local.yml exec django coverage report

# Run specific test class or method
docker compose -f docker-compose.local.yml exec django pytest sanaap_api_challenge/documents/tests/test_views.py::DocumentViewSetTest::test_upload_document
```

### Code Quality

```bash
# Type checking
docker compose -f docker-compose.local.yml exec django mypy sanaap_api_challenge

# Linting and formatting
docker compose -f docker-compose.local.yml exec django ruff check .
docker compose -f docker-compose.local.yml exec django ruff format .
```

### Load Testing

```bash
# Install locust for load testing
pip install locust

# Run load tests
locust -f tests/load_tests.py --host=http://localhost:8000
```

## 🔧 Troubleshooting

### Common Issues

#### 1. Port Already in Use

```bash
# Check what's using port 8000
sudo lsof -i :8000

# Kill the process
sudo kill -9 <PID>

# Or use different ports in docker-compose
```

#### 2. Database Connection Issues

```bash
# Check PostgreSQL container
docker compose -f docker-compose.local.yml logs postgres

# Reset database
docker compose -f docker-compose.local.yml down -v
docker compose -f docker-compose.local.yml up
```

#### 3. MinIO Connection Issues

```bash
# Check MinIO container
docker compose -f docker-compose.local.yml logs minio

# Verify MinIO credentials in environment files
cat .envs/.local/.minio
```

#### 4. File Upload Failures

```bash
# Check file permissions
ls -la uploads/

# Check MinIO bucket exists
docker compose -f docker-compose.local.yml exec minio mc ls local/

# Check Django logs
docker compose -f docker-compose.local.yml logs django
```

#### 5. nginx Issues (Production)

```bash
# Test nginx configuration
docker compose -f docker-compose.production.yml exec nginx nginx -t

# Check nginx logs
docker compose -f docker-compose.production.yml logs nginx

# Reload nginx configuration
docker compose -f docker-compose.production.yml exec nginx nginx -s reload
```

### Performance Optimization

#### Database Optimization

```sql
-- Add indexes for common queries
CREATE INDEX CONCURRENTLY idx_documents_owner ON documents_document(owner_id);
CREATE INDEX CONCURRENTLY idx_documents_status ON documents_document(status);
CREATE INDEX CONCURRENTLY idx_documents_created ON documents_document(created);
```

#### MinIO Optimization

```bash
# Configure MinIO for better performance
export MINIO_CACHE_DRIVES="/mnt/cache1,/mnt/cache2"
export MINIO_CACHE_EXCLUDE="*.tmp,*.temp"
```

#### Django Optimization

```python
# Add to production settings
DATABASES = {
    'default': {
        # ... existing config
        'CONN_MAX_AGE': 600,
        'OPTIONS': {
            'MAX_CONNS': 20,
            'MIN_CONNS': 5,
        }
    }
}

# Enable connection pooling
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            }
        }
    }
}
```

### Monitoring

#### Health Checks

```bash
# API health check
curl http://localhost:8000/api/health/

# MinIO health check
curl http://localhost:9000/minio/health/live

# Database health check
docker compose -f docker-compose.local.yml exec postgres pg_isready
```

#### Logs

```bash
# Application logs
docker compose -f docker-compose.local.yml logs -f django

# All services logs
docker compose -f docker-compose.local.yml logs -f

# Specific service logs
docker compose -f docker-compose.local.yml logs -f postgres redis minio
```

### Pre-commit Hooks

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Made with ❤️ using Django, MinIO, and Docker**