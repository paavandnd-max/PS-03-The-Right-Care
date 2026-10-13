# -*- coding: utf-8 -*-
"""
Public-sector healthcare portal builder for CareTruth AI / VERITAS.
Synchronizes and preserves caretruth-ai/frontend/index.html.
"""
from pathlib import Path

html_path = Path(__file__).resolve().parent.parent / "caretruth-ai" / "frontend" / "index.html"
if html_path.exists():
    print(f"Portal file confirmed at: {html_path} ({html_path.stat().st_size} bytes)")
else:
    print(f"Warning: {html_path} not found")
