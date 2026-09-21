#!/usr/bin/env python3
"""
Entry point for running the prayer times generator
"""
import importlib.util
import sys
from pathlib import Path

# Load generator module dynamically
src_path = Path(__file__).parent / 'src' / 'generator.py'
spec = importlib.util.spec_from_file_location('generator', src_path)
generator_module = importlib.util.module_from_spec(spec)
sys.modules['generator'] = generator_module
spec.loader.exec_module(generator_module)

if __name__ == '__main__':
    generator_module.main()
