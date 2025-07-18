#!/bin/bash
# Script for quick fixes and patches

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if fix description is provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: Please provide a fix description${NC}"
    echo "Usage: ./scripts/quick-fix.sh <fix-description>"
    echo "Example: ./scripts/quick-fix.sh 'resolve linting issues'"
    exit 1
fi

FIX_DESCRIPTION=$1
BRANCH_NAME="fix/$(echo "$FIX_DESCRIPTION" | tr ' ' '-' | tr '[:upper:]' '[:lower:]')"

echo -e "${BLUE}Creating quick fix: $FIX_DESCRIPTION${NC}"

# Create branch
git checkout main
git pull origin main
git checkout -b "$BRANCH_NAME"

echo -e "${GREEN}✅ Branch '$BRANCH_NAME' created${NC}"
echo ""
echo "Make your fixes, then run:"
echo "git add -A"
echo "git commit -m \"fix: $FIX_DESCRIPTION\""
echo "git push -u origin $BRANCH_NAME"
echo ""
echo -n "Press Enter when fixes are committed..."
read -r

# Create and merge PR quickly
PR_URL=$(gh pr create \
  --title "fix: $FIX_DESCRIPTION" \
  --body "## Fix
- $FIX_DESCRIPTION

## Type
- [ ] Bug fix
- [ ] Performance improvement
- [ ] Code cleanup

🤖 Generated with automation script" \
  --base main)

PR_NUMBER=$(echo "$PR_URL" | grep -o '[0-9]*$')

echo -e "${YELLOW}Waiting for CI...${NC}"
gh pr checks "$PR_NUMBER" --watch

# Auto-merge if checks pass
echo -e "${YELLOW}Merging...${NC}"
gh pr merge "$PR_NUMBER" --merge --auto

echo -e "${GREEN}✅ Fix merged!${NC}"