#!/bin/bash
# Script to create a new release

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Switch to main and pull latest
echo -e "${YELLOW}Switching to main branch...${NC}"
git checkout main
git pull origin main

# Get latest tag
LATEST_TAG=$(git tag -l | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1)

if [ -z "$LATEST_TAG" ]; then
    echo -e "${YELLOW}No previous tags found. Starting with v0.0.1${NC}"
    LATEST_TAG="v0.0.0"
fi

echo -e "${BLUE}Latest tag: $LATEST_TAG${NC}"

# Parse version components
VERSION=${LATEST_TAG#v}
IFS='.' read -r MAJOR MINOR PATCH <<< "$VERSION"

# Determine version bump type
echo ""
echo "Select version bump type:"
echo "1) Patch (bug fixes) - v$MAJOR.$MINOR.$((PATCH + 1))"
echo "2) Minor (new features) - v$MAJOR.$((MINOR + 1)).0"
echo "3) Major (breaking changes) - v$((MAJOR + 1)).0.0"
echo -n "Enter choice [1-3]: "
read -r BUMP_TYPE

case $BUMP_TYPE in
    1)
        NEW_VERSION="v$MAJOR.$MINOR.$((PATCH + 1))"
        BUMP_NAME="patch"
        ;;
    2)
        NEW_VERSION="v$MAJOR.$((MINOR + 1)).0"
        BUMP_NAME="minor"
        ;;
    3)
        NEW_VERSION="v$((MAJOR + 1)).0.0"
        BUMP_NAME="major"
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo -e "${BLUE}Creating $BUMP_NAME release: $NEW_VERSION${NC}"

# Get commits since last tag
echo -e "${YELLOW}Analyzing commits since $LATEST_TAG...${NC}"

# Generate release notes
RELEASE_NOTES="## What's Changed

"

# Get merged PRs since last tag
PRS=$(gh pr list --state merged --base main --search "merged:>=$(git log -1 --format=%aI $LATEST_TAG)" --json number,title,author --limit 100)

if [ "$PRS" != "[]" ]; then
    RELEASE_NOTES+="### Pull Requests
"
    echo "$PRS" | jq -r '.[] | "- \(.title) (#\(.number)) by @\(.author.login)"' | while read -r line; do
        RELEASE_NOTES+="$line
"
    done
    RELEASE_NOTES+="
"
fi

# Get commit messages
COMMITS=$(git log --pretty=format:"- %s (%h)" "$LATEST_TAG"..HEAD)
if [ -n "$COMMITS" ]; then
    RELEASE_NOTES+="### Commits
$COMMITS

"
fi

RELEASE_NOTES+="**Full Changelog**: https://github.com/bigspawn/anki-bot/compare/$LATEST_TAG...$NEW_VERSION"

# Show release notes preview
echo -e "${BLUE}Release Notes Preview:${NC}"
echo "========================"
echo "$RELEASE_NOTES"
echo "========================"
echo ""

# Confirm release
echo -n "Create release $NEW_VERSION? [y/N]: "
read -r CONFIRM

if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo -e "${YELLOW}Release cancelled${NC}"
    exit 0
fi

# Create release
echo -e "${YELLOW}Creating release...${NC}"
RELEASE_URL=$(gh release create "$NEW_VERSION" \
  --title "Release $NEW_VERSION" \
  --notes "$RELEASE_NOTES" \
  --generate-notes)

echo -e "${GREEN}✅ Release $NEW_VERSION created successfully!${NC}"
echo -e "${BLUE}Release URL: $RELEASE_URL${NC}"

# Show deployment info
echo ""
echo -e "${YELLOW}Deployment Info:${NC}"
echo "The GitHub Actions will automatically:"
echo "1. Build Docker image with tag: $NEW_VERSION"
echo "2. Push to ghcr.io/bigspawn/anki-bot:$NEW_VERSION"
echo "3. Also tag as 'latest'"
echo ""
echo "To deploy to production:"
echo "docker pull ghcr.io/bigspawn/anki-bot:$NEW_VERSION"
echo "docker-compose up -d"