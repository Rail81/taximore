#!/bin/bash

set -e

echo "Starting deployment..."

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
pip install -r requirements.txt

# Run database migrations
flask db upgrade

# Build frontend
cd frontend
npm install
npm run build
cd ..

# Restart services
sudo supervisorctl restart taximore:*
sudo systemctl restart nginx

echo "Deployment completed successfully!"
