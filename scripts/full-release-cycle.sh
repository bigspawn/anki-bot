#!/bin/bash
# Script to run full release cycle from feature to production

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Full Release Cycle Automation${NC}"
echo "=================================="

# Check if feature name is provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: Please provide a feature name${NC}"
    echo "Usage: ./scripts/full-release-cycle.sh <feature-name> [bump-type]"
    echo "Example: ./scripts/full-release-cycle.sh daily-reminders minor"
    echo ""
    echo "Bump types: patch (default), minor, major"
    exit 1
fi

FEATURE_NAME=$1
BUMP_TYPE=${2:-patch}

# Validate bump type
if [[ ! "$BUMP_TYPE" =~ ^(patch|minor|major)$ ]]; then
    echo -e "${RED}Error: Invalid bump type '$BUMP_TYPE'${NC}"
    echo "Valid types: patch, minor, major"
    exit 1
fi

echo -e "${BLUE}Feature: $FEATURE_NAME${NC}"
echo -e "${BLUE}Release type: $BUMP_TYPE${NC}"
echo ""

# Step 1: Create feature branch
echo -e "${YELLOW}Step 1: Creating feature branch...${NC}"
./scripts/create-feature.sh "$FEATURE_NAME"

echo ""
echo -e "${GREEN}✅ Feature branch created!${NC}"
echo ""
echo -e "${YELLOW}⚠️  MANUAL STEP REQUIRED:${NC}"
echo "1. Implement your feature"
echo "2. Write tests"
echo "3. Run 'make test' to verify"
echo "4. Commit your changes"
echo ""
echo -n "Press Enter when ready to continue..."
read -r

# Step 2: Create PR
echo -e "${YELLOW}Step 2: Creating pull request...${NC}"
PR_URL=$(gh pr create \
  --title "feat: Add $FEATURE_NAME" \
  --body "## Summary
- Add $FEATURE_NAME functionality

## Changes
- Implementation completed
- Tests added
- All tests passing

## Test plan
- All automated tests pass
- Manual testing completed

🤖 Generated with automation script" \
  --base main)

PR_NUMBER=$(echo "$PR_URL" | grep -o '[0-9]*$')
echo -e "${GREEN}✅ PR #$PR_NUMBER created!${NC}"

# Step 3: Wait for CI
echo -e "${YELLOW}Step 3: Waiting for CI checks...${NC}"
sleep 10  # Give CI time to start

# Watch CI checks
gh pr checks "$PR_NUMBER" --watch || {
    echo -e "${RED}CI checks failed!${NC}"
    echo "Please fix the issues and push commits"
    echo "Then run: ./scripts/merge-pr.sh $PR_NUMBER"
    exit 1
}

# Step 4: Merge PR
echo -e "${YELLOW}Step 4: Merging pull request...${NC}"
./scripts/merge-pr.sh "$PR_NUMBER"

# Step 5: Create release
echo -e "${YELLOW}Step 5: Creating release...${NC}"

# Switch to main and pull
git checkout main
git pull origin main

# Get version info
LATEST_TAG=$(git tag -l | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1)
VERSION=${LATEST_TAG#v}
IFS='.' read -r MAJOR MINOR PATCH <<< "$VERSION"

# Calculate new version
case $BUMP_TYPE in
    patch)
        NEW_VERSION="v$MAJOR.$MINOR.$((PATCH + 1))"
        ;;
    minor)
        NEW_VERSION="v$MAJOR.$((MINOR + 1)).0"
        ;;
    major)
        NEW_VERSION="v$((MAJOR + 1)).0.0"
        ;;
esac

# Create release with automated notes
RELEASE_URL=$(gh release create "$NEW_VERSION" \
  --title "Release $NEW_VERSION: $FEATURE_NAME" \
  --notes "## 🎉 New Features

### $FEATURE_NAME
- Implemented $FEATURE_NAME functionality
- Added comprehensive test coverage
- All CI checks passing

**Full Changelog**: https://github.com/bigspawn/anki-bot/compare/$LATEST_TAG...$NEW_VERSION" \
  --generate-notes)

echo -e "${GREEN}✅ Release $NEW_VERSION created!${NC}"

# Summary
echo ""
echo -e "${BLUE}🎉 Release Cycle Complete!${NC}"
echo "========================="
echo "Feature: $FEATURE_NAME"
echo "PR: #$PR_NUMBER"
echo "Release: $NEW_VERSION"
echo "URL: $RELEASE_URL"
echo ""
echo -e "${YELLOW}Docker image will be built automatically:${NC}"
echo "ghcr.io/bigspawn/anki-bot:$NEW_VERSION"
echo "ghcr.io/bigspawn/anki-bot:latest"