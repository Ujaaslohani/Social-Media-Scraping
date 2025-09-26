"""
Production-ready startup script for the Social Media Scraping API.

This script provides optimized configuration for running the FastAPI application
in production environments with proper logging, security, and performance settings.

Usage:
    python run.py                    # Development mode
    python run.py --production       # Production mode
    python run.py --workers 4        # Specify number of workers
    python run.py --port 8080        # Custom port
"""

import os
import sys
import argparse
import multiprocessing
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Social Media Scraping API Server",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to"
    )
    
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes"
    )
    
    parser.add_argument(
        "--production",
        action="store_true",
        help="Run in production mode with optimized settings"
    )
    
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (development only)"
    )
    
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="Logging level"
    )
    
    return parser.parse_args()


def configure_production_settings():
    """Configure optimized settings for production."""
    # Set environment to production
    os.environ["ENVIRONMENT"] = "production"
    
    # Optimize for production
    os.environ["PYTHONOPTIMIZE"] = "1"
    os.environ["PYTHONUNBUFFERED"] = "1"
    
    print("🔧 Production mode enabled with optimized settings")


def run_server():
    """Run the FastAPI server with appropriate configuration."""
    args = get_args()
    
    if args.production:
        configure_production_settings()
        args.host = "0.0.0.0"  # Bind to all interfaces in production
        if args.workers == 1:
            args.workers = min(4, multiprocessing.cpu_count())
    
    # Determine if reload should be enabled
    reload = args.reload and not args.production
    
    print(f"🚀 Starting Social Media Scraping API Server...")
    print(f"📍 Host: {args.host}")
    print(f"🔌 Port: {args.port}")
    print(f"👥 Workers: {args.workers}")
    print(f"📊 Log Level: {args.log_level}")
    print(f"🔄 Reload: {'Enabled' if reload else 'Disabled'}")
    print(f"🌍 Environment: {os.getenv('ENVIRONMENT', 'development')}")
    
    if args.production:
        print("🔒 Production mode: Security optimizations enabled")
    
    print("-" * 50)
    
    # Server configuration
    config = {
        "app": "app.main:app",
        "host": args.host,
        "port": args.port,
        "log_level": args.log_level,
        "access_log": True,
        "use_colors": not args.production,
        "server_header": False,  # Security: hide server info
        "date_header": False,    # Security: hide date
        "reload": reload,
        "workers": args.workers if not reload else 1,  # Reload doesn't work with multiple workers
    }
    
    # Production optimizations
    if args.production:
        config.update({
            "loop": "uvloop",  # Use uvloop for better performance
            "http": "httptools",  # Use httptools for HTTP parsing
            "backlog": 2048,  # Increase connection backlog
            "limit_concurrency": 1000,  # Limit concurrent connections
            "timeout_keep_alive": 5,  # Keep-alive timeout
        })
    
    # Start server
    try:
        uvicorn.run(**config)
    except KeyboardInterrupt:
        print("\n🛑 Server shutdown requested by user")
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_server()