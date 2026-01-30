"""
Setup script for creating macOS app bundle.
"""
from setuptools import setup

APP = ['menubar_monitor.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'packages': ['rumps', 'skyfield', 'dotenv', 'src'],
    'iconfile': None,
    'plist': {
        'CFBundleName': 'Transit Monitor',
        'CFBundleDisplayName': 'Transit Monitor',
        'CFBundleGetInfoString': "Monitor airplane transits across Moon/Sun",
        'CFBundleIdentifier': "com.flymoon.transitmonitor",
        'CFBundleVersion': "1.0.0",
        'CFBundleShortVersionString': "1.0.0",
        'NSHumanReadableCopyright': "Flymoon",
        'LSUIElement': True,  # Run as menu bar app (no dock icon)
    }
}

setup(
    app=APP,
    name='Transit Monitor',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
