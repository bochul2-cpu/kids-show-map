@echo off
cd /d "%~dp0"
python collect.py
python build_map.py
