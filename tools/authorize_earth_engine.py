"""Authenticate and initialize Google Earth Engine for FieldMoist."""
import os
from pathlib import Path
import ee
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env')
project = os.getenv('EARTH_ENGINE_PROJECT')
if not project:
    raise SystemExit('Set EARTH_ENGINE_PROJECT in .env before authenticating.')
ee.Authenticate()
ee.Initialize(project=project)
print('Google Earth Engine authentication succeeded.')
