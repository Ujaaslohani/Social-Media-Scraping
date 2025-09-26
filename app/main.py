"""
Social Media Scraping FastAPI Application

A robust, scalable backend API for managing social media data scraping operations.
Integrates with existing Instagram and YouTube scraping scripts while providing
secure authentication, rate limiting, and comprehensive error handling.

Features:
- JWT-based authentication with secure password hashing
- RESTful API endpoints for scraping management
- Integration with existing Instagram (insta_final.py) and YouTube (youtube_id_finder.py) scripts
- Background job processing for long-running scraping operations
- Rate limiting and security middleware
- Comprehensive logging and error handling
- MySQL database integration with SQLAlchemy ORM

Author: Social Media Scraping Project
Version: 1.0.0
Python: 3.10+
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import application modules
from app.database import create_tables, test_connection
from app.routers import auth_router, metrics_router
from app.utils.helpers import setup_logging, rate_limit_exceeded_handler, check_service_health
from app.schemas import HealthResponse, ErrorResponse

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events.
    
    Handles:
    - Database connection testing and table creation
    - Application initialization logging
    - Resource cleanup on shutdown
    """
    logger.info("🚀 Starting Social Media Scraping API...")
    
    # Test database connection
    if test_connection():
        logger.info("✅ Database connection successful")
        try:
            create_tables()
            logger.info("✅ Database tables initialized")
        except Exception as e:
            logger.error(f"❌ Failed to create database tables: {e}")
    else:
        logger.error("❌ Database connection failed - API may not function properly")
    
    logger.info("🎯 API startup complete - Ready to accept requests")
    yield
    
    logger.info("🔄 Shutting down Social Media Scraping API...")
    logger.info("✅ API shutdown complete")


# Initialize FastAPI application
app = FastAPI(
    title="Social Media Scraping API",
    description="""
    A robust and scalable backend API for managing social media data scraping operations.
    
    ## Features
    
    🔐 **Authentication & Security**
    - JWT-based authentication with secure password hashing
    - Rate limiting to prevent abuse
    - CORS support for web applications
    
    📊 **Social Media Integration**
    - Instagram profile and post scraping
    - YouTube channel and video data collection
    - Background job processing for long-running operations
    
    📈 **Analytics & Metrics**
    - Comprehensive analytics dashboards
    - Profile performance metrics
    - Engagement rate calculations
    
    🔧 **Developer-Friendly**
    - Comprehensive API documentation
    - Type hints and validation with Pydantic
    - Structured error responses
    - Extensive logging for debugging
    
    ## Authentication
    
    Most endpoints require authentication. To access protected routes:
    
    1. Register a new account: `POST /auth/register`
    2. Login to get access token: `POST /auth/login`
    3. Use token in Authorization header: `Bearer <your_token>`
    
    ## Rate Limits
    
    - Authentication endpoints: 5-10 requests/minute
    - Metrics endpoints: 30 requests/minute  
    - Scraping jobs: 5-10 jobs/hour
    
    ## Support
    
    For issues, feature requests, or questions about integrating with existing
    scraping scripts, please refer to the project documentation.
    """,
    version="1.0.0",
    contact={
        "name": "Social Media Scraping Project",
        "email": "support@socialmediascraping.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Add security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if os.getenv("ENVIRONMENT") == "development" else ["yourdomain.com", "*.yourdomain.com"]
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React development
        "http://localhost:8080",  # Vue development
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
    ] if os.getenv("ENVIRONMENT") == "development" else [
        "https://yourdomain.com",
        "https://app.yourdomain.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)


# Global exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with structured error responses."""
    logger.warning(f"HTTP {exc.status_code} error on {request.url}: {exc.detail}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": "HTTPException",
            "message": exc.detail,
            "status_code": exc.status_code,
            "path": str(request.url),
            "method": request.method,
            "timestamp": __import__("datetime").datetime.utcnow().isoformat()
        },
    )


@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    """Handle internal server errors with proper logging."""
    logger.error(f"Internal server error on {request.url}: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "InternalServerError",
            "message": "An internal server error occurred. Please try again later.",
            "status_code": 500,
            "path": str(request.url),
            "method": request.method,
            "timestamp": __import__("datetime").datetime.utcnow().isoformat()
        },
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    """Handle 404 errors with helpful messages."""
    logger.info(f"404 error on {request.url}")
    
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "error": "NotFound",
            "message": f"The requested endpoint {request.url.path} was not found.",
            "status_code": 404,
            "available_endpoints": [
                "/docs - API Documentation",
                "/api/v1/auth/register - User Registration",
                "/api/v1/auth/login - User Login",
                "/api/v1/metrics/youtube - YouTube Analytics",
                "/api/v1/metrics/instagram - Instagram Analytics",
                "/api/v1/metrics/twitter - Twitter Analytics",
                "/health - Health Check"
            ],
            "timestamp": __import__("datetime").datetime.utcnow().isoformat()
        },
    )


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests for monitoring and debugging."""
    import time
    
    start_time = time.time()
    
    # Log request details
    logger.info(
        f"📥 {request.method} {request.url.path} - "
        f"IP: {request.client.host} - "
        f"User-Agent: {request.headers.get('user-agent', 'Unknown')}"
    )
    
    response = await call_next(request)
    
    # Log response details
    process_time = round((time.time() - start_time) * 1000, 2)
    logger.info(
        f"📤 {request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time}ms"
    )
    
    # Add response time header
    response.headers["X-Process-Time"] = str(process_time)
    
    return response


# Include routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(metrics_router, prefix="/api/v1")


# Root endpoint
@app.get("/", tags=["Root"])
@limiter.limit("100/minute")
async def root(request: Request):
    """
    API root endpoint with welcome message and basic information.
    
    Returns:
        dict: Welcome message with API information and available endpoints
    """
    return {
        "message": "🚀 Welcome to Social Media Scraping API",
        "version": "1.0.0",
        "description": "A robust backend for managing Instagram and YouTube scraping operations",
        "features": [
            "JWT Authentication",
            "Instagram Profile Scraping",
            "YouTube Channel Analytics", 
            "Background Job Processing",
            "Rate Limiting & Security",
            "Comprehensive Error Handling"
        ],
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_json": "/openapi.json"
        },
        "endpoints": {
            "authentication": "/api/v1/auth",
            "metrics_analytics": "/api/v1/metrics",
            "health_check": "/health"
        },
        "quick_start": {
            "1_register": "POST /api/v1/auth/register",
            "2_login": "POST /api/v1/auth/login", 
            "3_get_metrics": "GET /api/v1/metrics/youtube (with Authorization header)",
            "4_twitter_scraping": "POST /api/v1/metrics/twitter (with Authorization header)"
        },
        "status": "✅ Operational",
        "environment": os.getenv("ENVIRONMENT", "development")
    }


# Health check endpoint
@app.get("/health", response_model=HealthResponse, tags=["Health"])
@limiter.limit("100/minute")
async def health_check(request: Request):
    """
    Health check endpoint for monitoring and load balancers.
    
    Returns:
        HealthResponse: Service health status and system information
    """
    health_info = check_service_health()
    
    return HealthResponse(
        status=health_info["status"],
        timestamp=health_info["timestamp"],
        version="1.0.0",
        database=health_info["checks"]["database"],
        environment=os.getenv("ENVIRONMENT", "development")
    )


# Custom OpenAPI schema
def custom_openapi():
    """Generate custom OpenAPI schema with additional metadata."""
    if app.openapi_schema:
        return app.openapi_schema
        
    openapi_schema = get_openapi(
        title="Social Media Scraping API",
        version="1.0.0",
        description=app.description,
        routes=app.routes,
    )
    
    # Add custom security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token obtained from /auth/login endpoint"
        }
    }
    
    # Add rate limiting information to schema
    openapi_schema["info"]["x-rate-limits"] = {
        "authentication": "5-10 requests per minute",
        "metrics": "30 requests per minute",
        "scraping": "5-10 jobs per hour"
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


if __name__ == "__main__":
    """
    Development server entry point.
    
    For production deployment, use a WSGI/ASGI server like Gunicorn with Uvicorn workers:
    gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
    """
    logger.info("🔧 Starting development server...")
    
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,  # Auto-reload on code changes
        reload_dirs=["app"],  # Watch specific directories
        log_level="info",
        access_log=True,
        use_colors=True,
        server_header=False,  # Security: hide server version
        date_header=False,    # Security: hide date header
    )