# 🚀 Automation Scripts

This directory contains automation scripts for streamlining the development workflow.

## Prerequisites

- GitHub CLI (`gh`) installed and authenticated
- Git configured
- Bash shell

## Available Scripts

### 🌟 Full Release Cycle
```bash
./scripts/full-release-cycle.sh <feature-name> [bump-type]
```
Automates the entire process from feature branch to production release.

**Example:**
```bash
./scripts/full-release-cycle.sh daily-reminders minor
```

**Bump types:**
- `patch` - Bug fixes (0.0.X)
- `minor` - New features (0.X.0) - default
- `major` - Breaking changes (X.0.0)

### 🔧 Individual Scripts

#### 1. Create Feature Branch
```bash
./scripts/create-feature.sh <feature-name>
```
Creates a new feature branch from main.

#### 2. Create Pull Request
```bash
./scripts/create-pr.sh
```
Creates a PR from current feature branch with CI checks.

#### 3. Merge Pull Request
```bash
./scripts/merge-pr.sh <pr-number>
```
Waits for CI and merges PR automatically.

#### 4. Create Release
```bash
./scripts/create-release.sh
```
Interactive script to create a new release with proper versioning.

#### 5. Quick Fix
```bash
./scripts/quick-fix.sh <fix-description>
```
Fast track for small fixes and patches.

### 📚 Seed Curated Word Lists
```bash
uv run python scripts/seed_words.py <db> <telegram_id> <seed/*.json> [--dry-run]
```
Loads authored card sets into a user's dictionary. Words already in the
user's list are skipped, so re-running adds nothing.

**Examples:**
```bash
# Preview the route and drill sets without writing
uv run python scripts/seed_words.py data/bot.db 739529 \
    seed/route_phrases.json seed/cloze_route.json seed/error_fix_route.json --dry-run

# Load everything (same set the Makefile target uses)
make seed-words TELEGRAM_ID=739529
```

**Available sets:**
- `seed/reflexive_verbs.json` — reflexive verbs, studied via `/study_reflexive`
- `seed/preposition_verbs.json` — verbs governing a preposition, `/study_rektion`
- `seed/route_phrases.json` — route chunks, `/study_route`
- `seed/cloze_route.json` — gap-fill drills, `/study_cloze`
- `seed/error_fix_route.json` — error-correction drills, `/study_cloze`

A `cloze` card is rejected before anything is written unless its
`additional_forms` carries an `answer`.

## Workflow Examples

### New Feature Development
```bash
# 1. Start feature
./scripts/create-feature.sh user-notifications

# 2. Develop feature
# ... make changes ...
make test
git add -A
git commit -m "feat: add user notifications"

# 3. Create PR
./scripts/create-pr.sh

# 4. After CI passes, merge
./scripts/merge-pr.sh 10

# 5. Create release
./scripts/create-release.sh
```

### Quick Bug Fix
```bash
./scripts/quick-fix.sh "fix memory leak in parser"
# Make fixes...
git add -A
git commit -m "fix: resolve memory leak in parser"
# Script handles the rest
```

### Automated Full Cycle
```bash
# One command for entire workflow
./scripts/full-release-cycle.sh awesome-feature minor
# Follow prompts to implement feature
# Script handles PR, CI, merge, and release
```

## Best Practices

1. **Always run tests locally** before creating PR
   ```bash
   make test
   make lint
   ```

2. **Use semantic commit messages**
   - `feat:` for new features
   - `fix:` for bug fixes
   - `test:` for test additions
   - `docs:` for documentation

3. **Version bumping guidelines**
   - Bug fixes → patch
   - New features → minor
   - Breaking changes → major

4. **PR descriptions**
   - Clearly describe what changed
   - Include test plan
   - Reference related issues

## Troubleshooting

### CI Failures
If CI fails during automated workflow:
1. Fix issues locally
2. Push fixes to branch
3. Re-run failed script or continue manually

### Permission Issues
Make scripts executable:
```bash
chmod +x scripts/*.sh
```

### GitHub CLI Auth
Authenticate GitHub CLI:
```bash
gh auth login
```

## Contributing

When adding new scripts:
1. Follow existing naming convention
2. Add proper error handling
3. Include help text
4. Update this README
5. Test thoroughly

## Support

For issues or improvements, create an issue in the repository.