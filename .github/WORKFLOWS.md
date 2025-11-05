# CI/CD Workflows Documentation

This document describes all GitHub Actions workflows configured for this project.

## Table of Contents

1. [Tests](#tests)
2. [Code Quality](#code-quality)
3. [Pre-commit Checks](#pre-commit-checks)
4. [Release](#release)
5. [Documentation](#documentation)
6. [Pull Request Management](#pull-request-management)
7. [Dependency Management](#dependency-management)

---

## Tests

**File**: `.github/workflows/test.yml`

**Triggers**:
- Push to `main`/`master` branches
- Pull requests to `main`/`master` branches

**What it does**:
- Runs tests on Python 3.10, 3.11, and 3.12
- Generates coverage reports
- Uploads coverage to Codecov (Python 3.11 only)
- Enforces 85% minimum coverage threshold
- Uploads HTML coverage report as artifact

**Required Secrets**:
- `CODECOV_TOKEN` (optional but recommended)

---

## Code Quality

**File**: `.github/workflows/code-quality.yml`

**Triggers**:
- Push to `main`/`master`/`develop` branches
- Pull requests to these branches

**What it does**:

### Linting
- Runs `ruff` linter on all Python files
- Checks code formatting with `ruff format`

### Type Checking
- Runs `mypy` type checker on source code

### Security
- Runs `bandit` security linter
- Runs `safety` to check for known vulnerabilities in dependencies
- Uploads security reports as artifacts

---

## Pre-commit Checks

**File**: `.github/workflows/pre-commit.yml`

**Triggers**:
- Pull requests only

**What it does**:
- Runs all pre-commit hooks on changed files
- Comments on PR if hooks fail
- Uses cached pre-commit environments for speed

---

## Release

**File**: `.github/workflows/release.yml`

**Triggers**:
- Push of version tags (e.g., `v1.0.0`)
- Manual workflow dispatch

**What it does**:

### Build
1. Builds Python wheel and source distribution
2. Validates distributions with `twine check`
3. Uploads artifacts for inspection

### Test Release
1. Tests installation on Python 3.10, 3.11, 3.12
2. Verifies imports work correctly
3. Runs basic functionality tests

### Publish to Test PyPI
1. Publishes to Test PyPI for validation
2. Uses trusted publishing (no API tokens needed)

### Publish to PyPI
1. Publishes to production PyPI
2. Only runs after successful Test PyPI publish

### GitHub Release
1. Creates GitHub release with changelog
2. Attaches distribution files
3. Auto-generates changelog from commits
4. Marks as pre-release if version contains alpha/beta/rc

**Required Setup**:
- Configure trusted publishing on PyPI and Test PyPI
- Set up `pypi` and `test-pypi` environments in GitHub

**To create a release**:
```bash
# Update version in pyproject.toml
# Commit changes
git tag v1.0.0
git push origin v1.0.0
```

---

## Documentation

**File**: `.github/workflows/docs.yml`

**Triggers**:
- Push to `main`/`master` with changes to docs or markdown
- Pull requests with doc changes

**What it does**:

### Lint Documentation
- Checks Markdown links for dead links
- Lints Markdown files for style consistency

### Check Examples
- Extracts and validates Python code examples from README
- Tests example files in `docs/examples/`

### Build API Docs
- Generates API documentation with `pdoc3`
- Uploads as artifact (on push to main only)

---

## Pull Request Management

### Labeler

**File**: `.github/workflows/labeler.yml`

**Triggers**: PR open, sync, reopen

**What it does**:
- Auto-labels PRs based on changed files
- Labels by size (XS/S/M/L/XL based on line changes)
- Labels by type (bug, feature, refactor, etc.) based on branch name/title

**Labels Applied**:
- `documentation` - Changes to docs or markdown
- `core` - Changes to core source code
- `services` - Changes to services layer
- `tests` - Changes to tests
- `ci-cd` - Changes to workflows
- `configuration` - Changes to config files
- `dependencies` - Dependency updates
- `bug`, `feature`, `refactor`, `performance` - Based on branch/title
- `size/*` - Based on total lines changed

**Configuration**: `.github/labeler.yml`

### Stale Issues/PRs

**File**: `.github/workflows/stale.yml`

**Triggers**:
- Daily at midnight UTC
- Manual workflow dispatch

**What it does**:
- Marks issues stale after 90 days of inactivity
- Closes stale issues after 7 more days
- Marks PRs stale after 60 days of inactivity
- Closes stale PRs after 14 more days
- Removes stale label when activity resumes

**Exempt Labels**:
- `pinned` - Never marked stale
- `security` - Never marked stale
- `roadmap` - Never marked stale (issues only)
- `work-in-progress` - Never marked stale (PRs only)

---

## Dependency Management

### Dependabot

**File**: `.github/dependabot.yml`

**What it does**:
- Checks for Python dependency updates weekly (Mondays at 9 AM)
- Checks for GitHub Actions updates weekly
- Creates PRs for updates
- Auto-labels PRs with `dependencies`
- Ignores major version updates (can be overridden)

**Reviewers**: Automatically requests review from repository owner

---

## Workflow Status Badges

Add these badges to your README:

```markdown
[![Tests](https://github.com/redbaron/kanban-core/workflows/Tests/badge.svg)](https://github.com/redbaron/kanban-core/actions?query=workflow%3ATests)
[![Code Quality](https://github.com/redbaron/kanban-core/workflows/Code%20Quality/badge.svg)](https://github.com/redbaron/kanban-core/actions?query=workflow%3A%22Code+Quality%22)
[![codecov](https://codecov.io/gh/redbaron/kanban-core/branch/main/graph/badge.svg)](https://codecov.io/gh/redbaron/kanban-core)
```

---

## Local Testing

Before pushing, you can test your changes locally:

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v --cov=src/kanban

# Run linting
ruff check src/ tests/
ruff format --check src/ tests/

# Run type checking
mypy src/

# Run pre-commit hooks
pre-commit run --all-files

# Test code examples
python scripts/test_readme_examples.py
```

---

## Troubleshooting

### Coverage Upload Fails
- Ensure `CODECOV_TOKEN` secret is set in repository settings
- Set `fail_ci_if_error: false` to make it non-blocking

### Release Workflow Fails
- Verify trusted publishing is configured on PyPI
- Check that version tag format is correct (vX.Y.Z)
- Ensure `pypi` and `test-pypi` environments exist

### Pre-commit Hook Failures
- Run `pre-commit run --all-files` locally
- Commit the auto-fixes
- Push again

### Dependabot PRs Not Created
- Check that `redbaron` username is correct in `.github/dependabot.yml`
- Verify Dependabot is enabled in repository settings

---

## Best Practices

1. **Always run tests locally** before pushing
2. **Use meaningful commit messages** - they appear in release notes
3. **Tag releases properly** - follow semver (vMAJOR.MINOR.PATCH)
4. **Review security reports** - check uploaded artifacts for vulnerabilities
5. **Keep dependencies updated** - merge Dependabot PRs regularly
6. **Monitor coverage** - don't let it drop below 85%
7. **Test examples** - ensure README examples work before documenting them

---

## Adding New Workflows

When adding new workflows:

1. Create file in `.github/workflows/`
2. Use descriptive name and proper triggers
3. Add caching where appropriate
4. Document it in this file
5. Test with `act` tool if possible
6. Set `continue-on-error: true` for non-critical steps

---

## Contact

For questions about CI/CD setup, open an issue or contact the maintainers.
