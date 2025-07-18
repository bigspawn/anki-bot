#!/bin/bash
# Script to create a new feature branch and set up development

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if feature name is provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: Please provide a feature name${NC}"
    echo "Usage: ./scripts/create-feature.sh <feature-name>"
    echo "Example: ./scripts/create-feature.sh daily-reminders"
    exit 1
fi

FEATURE_NAME=$1
BRANCH_NAME="feature/$FEATURE_NAME"

echo -e "${BLUE}Creating new feature branch: $BRANCH_NAME${NC}"

# Ensure we're on main and up to date
echo -e "${YELLOW}Switching to main branch...${NC}"
git checkout main

echo -e "${YELLOW}Pulling latest changes...${NC}"
git pull origin main

# Create and checkout new branch
echo -e "${YELLOW}Creating feature branch...${NC}"
git checkout -b "$BRANCH_NAME"

echo -e "${GREEN}✅ Feature branch '$BRANCH_NAME' created successfully!${NC}"
echo -e "${BLUE}You can now start developing your feature.${NC}"
echo ""
echo "Next steps:"
echo "1. Make your changes"
echo "2. Run 'make test' to test locally"
echo "3. Commit your changes"
echo "4. Run './scripts/create-pr.sh' to create a pull request"