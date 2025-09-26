# App module exports - Entry point for the FastAPI application
from .main import app

__version__ = "1.0.0"
__author__ = "Social Media Scraping Project"
__email__ = "support@socialmediascraping.com"

# Make the app importable from the package root
__all__ = ["app"]