#!/bin/bash
# Script to create a pull request with CI checks

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get current branch
CURRENT_BRANCH=$(git branch --show-current)

# Check if on feature branch
if [[ ! "$CURRENT_BRANCH" =~ ^feature/ ]]; then
    echo -e "${RED}Error: Not on a feature branch${NC}"
    echo "Current branch: $CURRENT_BRANCH"
    echo "Please switch to a feature branch first"
    exit 1
fi

echo -e "${BLUE}Creating PR for branch: $CURRENT_BRANCH${NC}"

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo -e "${RED}Error: You have uncommitted changes${NC}"
    echo "Please commit or stash your changes first"
    exit 1
fi

# Push branch
echo -e "${YELLOW}Pushing branch to remote...${NC}"
git push -u origin "$CURRENT_BRANCH"

# Extract feature name from branch
FEATURE_NAME=${CURRENT_BRANCH#feature/}
PR_TITLE="feat: Add $FEATURE_NAME"

# Create PR using gh CLI
echo -e "${YELLOW}Creating pull request...${NC}"
PR_URL=$(gh pr create \
  --title "$PR_TITLE" \
  --body "## Summary
- Add $FEATURE_NAME functionality

## Changes
- [ ] Implementation completed
- [ ] Tests added
- [ ] Documentation updated

## Test plan
- [ ] All tests pass locally
- [ ] Manual testing completed

🤖 Generated with automation script" \
  --base main \
  --draft)

echo -e "${GREEN}✅ Pull request created: $PR_URL${NC}"

# Watch CI checks
echo -e "${YELLOW}Watching CI checks...${NC}"
echo "Press Ctrl+C to stop watching"

# Extract PR number from URL
PR_NUMBER=$(echo "$PR_URL" | grep -o '[0-9]*$')

# Watch checks
gh pr checks "$PR_NUMBER" --watch || true

echo ""
echo "Next steps:"
echo "1. Wait for CI checks to pass"
echo "2. Mark PR as ready for review: gh pr ready $PR_NUMBER"
echo "3. Run './scripts/merge-pr.sh $PR_NUMBER' to merge"