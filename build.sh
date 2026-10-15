#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -e

echo "=================================================="
echo "  1. Building Frontend Widget & Showcase Page     "
echo "=================================================="
cd widget
npm install --no-audit
npm run build
cd ..

echo "=================================================="
echo "  2. Installing Python Backend Dependencies       "
echo "=================================================="
pip install --upgrade pip
pip install -r backend/requirements.txt

echo "=================================================="
echo "  Build Completed Successfully!                   "
echo "=================================================="
