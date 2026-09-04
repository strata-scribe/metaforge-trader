#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
export METAFORGE_TOKEN="" # Set your Supabase token here
uvicorn main:app --host 0.0.0.0 --port 8011
