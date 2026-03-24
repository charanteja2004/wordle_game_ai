"""Vercel serverless entry point — exposes the Flask app as a handler."""
import sys
import os

# Ensure project root is on the path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import app
