#!/bin/bash
# Script to check PR status and prepare for merge

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if PR number is provided
if [ -z "$1" ]; then
    # Try to get PR for current branch
    CURRENT_BRANCH=$(git branch --show-current)
    PR_NUMBER=$(gh pr list --head "$CURRENT_BRANCH" --json number -q '.[0].number' 2>/dev/null || echo "")
    
    if [ -z "$PR_NUMBER" ]; then
        echo -e "${RED}Error: No PR number provided and no PR found for current branch${NC}"
        echo "Usage: ./scripts/pr-status.sh [pr-number]"
        exit 1
    fi
    echo -e "${BLUE}Found PR #$PR_NUMBER for branch $CURRENT_BRANCH${NC}"
else
    PR_NUMBER=$1
fi

echo -e "${BLUE}Checking PR #$PR_NUMBER${NC}"
echo "================================"

# Get PR details
PR_INFO=$(gh pr view "$PR_NUMBER" --json state,isDraft,title,headRefName,statusCheckRollup)
PR_STATE=$(echo "$PR_INFO" | jq -r .state)
IS_DRAFT=$(echo "$PR_INFO" | jq -r .isDraft)
PR_TITLE=$(echo "$PR_INFO" | jq -r .title)
PR_BRANCH=$(echo "$PR_INFO" | jq -r .headRefName)

# Display PR info
echo -e "${BLUE}Title:${NC} $PR_TITLE"
echo -e "${BLUE}Branch:${NC} $PR_BRANCH"
echo -e "${BLUE}State:${NC} $PR_STATE"
echo -e "${BLUE}Draft:${NC} $IS_DRAFT"
echo ""

# Check state
if [ "$PR_STATE" = "MERGED" ]; then
    echo -e "${GREEN}✅ PR is already merged${NC}"
    exit 0
fi

if [ "$PR_STATE" = "CLOSED" ]; then
    echo -e "${RED}❌ PR is closed${NC}"
    exit 1
fi

# Check draft status
if [ "$IS_DRAFT" = "true" ]; then
    echo -e "${YELLOW}⚠️  PR is in draft mode${NC}"
    echo -n "Mark as ready for review? [y/N]: "
    read -r MARK_READY
    
    if [ "$MARK_READY" = "y" ] || [ "$MARK_READY" = "Y" ]; then
        gh pr ready "$PR_NUMBER"
        echo -e "${GREEN}✅ PR marked as ready${NC}"
    fi
fi

# Check CI status
echo ""
echo -e "${BLUE}CI Checks:${NC}"
gh pr checks "$PR_NUMBER"

# Get check summary
TOTAL_CHECKS=$(gh pr checks "$PR_NUMBER" --json state -q '. | length')
COMPLETED_CHECKS=$(gh pr checks "$PR_NUMBER" --json state -q '.[] | select(.state == "COMPLETED") | .state' | wc -l | tr -d ' ')
FAILED_CHECKS=$(gh pr checks "$PR_NUMBER" --json state -q '.[] | select(.state == "FAILURE") | .state' | wc -l | tr -d ' ')

echo ""
echo -e "${BLUE}Check Summary:${NC}"
echo "Total checks: $TOTAL_CHECKS"
echo "Completed: $COMPLETED_CHECKS"
echo "Failed: $FAILED_CHECKS"

# Recommendations
echo ""
echo -e "${BLUE}Recommendations:${NC}"

if [ "$FAILED_CHECKS" -gt 0 ]; then
    echo -e "${RED}❌ Fix failing CI checks before merging${NC}"
elif [ "$COMPLETED_CHECKS" -lt "$TOTAL_CHECKS" ]; then
    echo -e "${YELLOW}⏳ Wait for all CI checks to complete${NC}"
    echo "   Run: gh pr checks $PR_NUMBER --watch"
else
    echo -e "${GREEN}✅ PR is ready to merge!${NC}"
    echo "   Run: ./scripts/merge-pr.sh $PR_NUMBER"
fi

# Show recent comments
echo ""
echo -e "${BLUE}Recent Activity:${NC}"
gh pr view "$PR_NUMBER" --json comments -q '.comments[-3:] | .[] | "[\(.author.login)]: \(.body)"' 2>/dev/null || echo "No recent comments"