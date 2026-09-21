"""
Startup script for Azure App Service
"""
import importlib.util
import os
import sys
from pathlib import Path

# Load app module dynamically
src_path = Path(__file__).parent.parent / 'src' / 'app.py'
spec = importlib.util.spec_from_file_location('app', src_path)
app_module = importlib.util.module_from_spec(spec)
sys.modules['app'] = app_module
spec.loader.exec_module(app_module)

if __name__ == '__main__':
    app_module.app.run(host='0.0.0.0', port=os.environ.get('PORT', '5000'))
