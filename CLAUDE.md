# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a commercial-grade AI hair style generation web application for beauty salons in Japan. It allows beauty salon professionals to upload client photos or fetch images from HotPepper Beauty URLs and transform hairstyles using FLUX.1 Kontext Pro AI. The application includes real-time progress tracking, session management, and supports multiple concurrent users.

## Development Commands

### Environment Setup
```bash
# Copy environment variables and configure API keys
cp env.example .env
# Edit .env file with your API keys: GEMINI_API_KEY, BFL_API_KEY, SECRET_KEY

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start Redis server (required for session management and task queue)
redis-server
```

### Development Server
```bash
# Recommended: Start with SocketIO server for real-time features
python dev-start.py

# Alternative: Standard Flask startup
python run.py

# Start Celery worker for async tasks (separate terminal)
celery -A run.celery_app worker --loglevel=info
```

### Production Deployment
```bash
# Docker Compose (recommended)
docker-compose up -d

# Manual deployment
gunicorn --worker-class eventlet -w 4 --bind 0.0.0.0:5000 run:app
celery -A run.celery_app worker --loglevel=info --concurrency=4
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test module
pytest tests/test_services/

# Run single test file
pytest tests/test_services/test_flux_service.py

# Run specific test function
pytest tests/test_services/test_flux_service.py::test_generate_hair_style

# Load testing
locust -f tests/test_load/locustfile.py
```

## Architecture Overview

### Core Components

**Flask Application Factory Pattern** (`app/__init__.py`):
- Main Flask app creation with SocketIO, CSRF protection, rate limiting
- Redis integration for session storage and message queue
- Celery integration for async image generation tasks
- Automatic directory creation for uploads/generated images

**Service Layer** (`app/services/`):
- `flux_service.py`: FLUX.1 Kontext Pro API integration for image generation
- `gemini_service.py`: Google Gemini 2.5 Flash for Japanese prompt optimization
- `file_service.py`: Image file handling, validation, and processing
- `scraping_service.py`: HotPepper Beauty URL image extraction
- `session_service.py`: User session management with Redis
- `task_service.py`: Celery async task coordination

**Route Handlers** (`app/routes/`):
- `main.py`: Home, gallery, help pages with session management
- `upload.py`: File upload and URL-based image fetching
- `generate.py`: Image generation workflow with real-time progress via SocketIO
- `api.py`: RESTful API endpoints for health checks, stats, session management

**Configuration System** (`app/config.py`):
- Environment-based configuration classes (Development, Testing, Production)
- API rate limits, file size limits, security settings
- Redis and Celery configuration management

### Key Features

**Session Management**: 
- Redis-based sessions with automatic cleanup
- Daily usage limits per user
- Uploaded/generated image tracking

**Real-time Progress**: 
- SocketIO integration for generation status updates
- Progress stages: prompt_optimization → image_generation → saving → finished

**Rate Limiting**: 
- Per-minute, hourly, and daily request limits
- User-specific generation quotas
- Production-ready scaling limits

**Image Processing Modes**:
- Simple mode: Full image regeneration using FLUX.1 Kontext
- Advanced mode: Masked editing using FLUX.1 Fill for hair-only changes
- Manual masking UI with brush tools

## Critical Dependencies

**Required API Keys** (configure in `.env`):
- `GEMINI_API_KEY`: Google AI Studio API key for prompt optimization
- `BFL_API_KEY`: Black Forest Labs API key for FLUX.1 image generation
- `SECRET_KEY`: Strong secret key for Flask session security

**External Services**:
- Redis: Session storage, task queue, rate limiting storage
- FLUX.1 Kontext Pro API: Primary image generation (60-180 second processing)
- Google Gemini 2.5 Flash: Japanese prompt optimization with thinking_budget=0

## File Structure Patterns

**Static File Organization**:
- `app/static/uploads/`: User uploaded images (temporary, session-based cleanup)
- `app/static/generated/`: AI generated images (permanent storage)
- `app/static/js/`: Frontend JavaScript (upload.js, generate.js, masking.js)

**Template System**:
- `app/templates/base.html`: Base template with Tailwind CSS 4.1
- Session-aware navigation and statistics display
- Real-time progress UI components

## Development Guidelines

**Session Management**:
- Always use `@session_required` decorator for user-facing routes
- Session data includes upload history, generation counts, and daily limits
- Automatic session cleanup handles orphaned files

**Error Handling**:
- Service layer returns typed results with success/error states
- Frontend uses Toastify for user notifications
- Comprehensive logging with different levels per environment

**Async Task Patterns**:
- Long-running operations (image generation) use Celery tasks
- SocketIO events provide real-time progress updates
- Task cleanup handles failed or interrupted generations

**Rate Limiting Strategy**:
- Different limits for development vs production environments
- Per-endpoint limits defined in route decorators
- Redis-backed storage for distributed rate limiting

**Code Quality Requirements**:
- Follow PEP 8 style guidelines  
- Add Japanese docstrings for user-facing functions
- Include type hints where applicable
- Always run `pytest` before completing tasks
- Test both with and without Redis connectivity

## Security Considerations

**CSRF Protection**: Enabled for form submissions, exempted for API endpoints
**Input Validation**: File type, size validation, prompt length limits
**Session Security**: Redis-based sessions with configurable timeout
**Production Settings**: HTTPS enforcement, secure cookies, restricted CORS origins

## Performance Notes

**Concurrent Limits**: Max 5 simultaneous image generations (configurable)
**File Size Limits**: 10MB max upload, support for JPG/PNG/WebP
**Caching Strategy**: Redis for session data, no application-level image caching
**Resource Management**: Celery worker concurrency tuned for memory usage

## Important Configuration

**Environment Variables**: All critical settings configurable via `.env`
**Docker Support**: Full docker-compose setup for production deployment
**Health Checks**: `/api/health` endpoint for monitoring
**Logging**: Configurable log levels, file + console output

## Debugging and Troubleshooting

**Service Dependencies**:
- Redis must be running before starting the application
- Celery worker required for image generation functionality
- API keys must be valid and configured in `.env`

**Common Issues**:
- Redis connection failures: Check `redis-server` is running
- SocketIO not working: Use `python dev-start.py` instead of `python run.py`
- Image generation stuck: Verify Celery worker is active with `celery -A run.celery_app inspect ping`
- API errors: Check API key validity and rate limits

**Development Workflow**:
1. Start Redis: `redis-server`
2. Start Celery worker: `celery -A run.celery_app worker --loglevel=info`
3. Start application: `python dev-start.py`
4. Run tests after changes: `pytest`