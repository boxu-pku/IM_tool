#!/usr/bin/env python
"""
IM Tool Launcher Script
Sets up PYTHONPATH and launches the application.
"""
import sys
import os

# Add the project root to PYTHONPATH
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Launch the application
from im_app.main import main
if __name__ == "__main__":
    main()
