#!/usr/bin/env python3
"""
WSGI Configuration for PythonAnywhere deployment
===============================================
"""

import sys
import os

# Add your project directory to the sys.path
sys.path.insert(0, "/home/edudracos/traza-1.0")

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from app import create_app

# Create the application instance
application = create_app('production')

if __name__ == "__main__":
    application.run()