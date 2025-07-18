#!/bin/bash
# Script to merge PR after CI checks pass

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if PR number is provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: Please provide a PR number${NC}"
    echo "Usage: ./scripts/merge-pr.sh <pr-number>"
    echo "Example: ./scripts/merge-pr.sh 8"
    exit 1
fi

PR_NUMBER=$1

echo -e "${BLUE}Processing PR #$PR_NUMBER${NC}"

# Check PR status
echo -e "${YELLOW}Checking PR status...${NC}"
PR_STATE=$(gh pr view "$PR_NUMBER" --json state -q .state)

if [ "$PR_STATE" = "MERGED" ]; then
    echo -e "${YELLOW}PR is already merged${NC}"
    exit 0
fi

if [ "$PR_STATE" != "OPEN" ]; then
    echo -e "${RED}Error: PR is not open (state: $PR_STATE)${NC}"
    exit 1
fi

# Check if PR is draft
IS_DRAFT=$(gh pr view "$PR_NUMBER" --json isDraft -q .isDraft)
if [ "$IS_DRAFT" = "true" ]; then
    echo -e "${YELLOW}PR is in draft state. Marking as ready for review...${NC}"
    gh pr ready "$PR_NUMBER"
    sleep 2
fi

# Check CI status
echo -e "${YELLOW}Checking CI status...${NC}"
CHECKS_STATUS=$(gh pr checks "$PR_NUMBER" --json state -q '.[] | select(.state != "COMPLETED") | .state' | head -1)

if [ -n "$CHECKS_STATUS" ]; then
    echo -e "${YELLOW}CI checks are still running. Waiting for completion...${NC}"
    gh pr checks "$PR_NUMBER" --watch
fi

# Check if all checks passed
FAILED_CHECKS=$(gh pr checks "$PR_NUMBER" --json state -q '.[] | select(.state == "FAILURE") | .state' | head -1)

if [ -n "$FAILED_CHECKS" ]; then
    echo -e "${RED}Error: Some CI checks failed${NC}"
    gh pr checks "$PR_NUMBER"
    exit 1
fi

echo -e "${GREEN}✅ All CI checks passed!${NC}"

# Merge PR
echo -e "${YELLOW}Merging PR...${NC}"
gh pr merge "$PR_NUMBER" --merge --auto

# Wait for merge
echo -e "${YELLOW}Waiting for merge to complete...${NC}"
sleep 5

# Check if merged
PR_STATE=$(gh pr view "$PR_NUMBER" --json state -q .state)
if [ "$PR_STATE" = "MERGED" ]; then
    echo -e "${GREEN}✅ PR #$PR_NUMBER merged successfully!${NC}"
    
    # Get merge commit
    MERGE_COMMIT=$(gh pr view "$PR_NUMBER" --json mergeCommit -q .mergeCommit.oid | cut -c1-7)
    echo -e "${BLUE}Merge commit: $MERGE_COMMIT${NC}"
else
    echo -e "${RED}Error: PR merge failed${NC}"
    exit 1
fi

echo ""
echo "Next steps:"
echo "1. Run './scripts/create-release.sh' to create a release"
echo "2. Or switch to main: git checkout main && git pull"