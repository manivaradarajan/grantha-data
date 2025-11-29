# Release Process

This document provides step-by-step instructions for creating a new grantha-data release.

## Prerequisites

Before creating a release:

- [ ] All changes are merged to `main` branch
- [ ] All tests pass (`pytest` and `bazel test`)
- [ ] Working directory is clean (no uncommitted changes)
- [ ] You have determined the correct version bump (major/minor/patch)
- [ ] You have write access to the repository

## Release Checklist

### 1. Determine Version Bump

Refer to `docs/VERSIONING.md` to determine the appropriate version increment:

- **Major**: Breaking schema changes
- **Minor**: Compatible schema additions
- **Patch**: Data-only changes

Current version is in the `VERSION` file.

### 2. Update VERSION File

Edit the `VERSION` file at the repository root:

```bash
# Example: bumping from 0.1.0 to 0.2.0
echo "0.2.0" > VERSION
```

### 3. Update CHANGELOG.md

Add an entry to `CHANGELOG.md` for the new version:

```markdown
## [0.2.0] - 2025-11-28

### Added
- New Kena Upanishad with commentary
- Optional `contributor` field in schema

### Fixed
- Typo in Isavasya Upanishad mantra 3

### Breaking Changes
- None
```

### 4. Commit Version Bump

```bash
git add VERSION CHANGELOG.md
git commit -m "Bump version to 0.2.0"
git push origin main
```

### 5. Trigger Release Workflow

1. Go to GitHub Actions: `https://github.com/USER/grantha-data/actions`
2. Select "Release" workflow from the left sidebar
3. Click "Run workflow" button
4. Fill in the required inputs:
   - **Confirm version**: Enter the version from VERSION file (e.g., `0.2.0`)
   - **Is this a breaking change?**: Check if major version bump
   - **Additional release notes**: Optional extra context
5. Click "Run workflow"

### 6. Monitor Workflow

The workflow will:

1. ✅ Validate VERSION file format
2. ✅ Verify version confirmation matches
3. ✅ Check that tag doesn't already exist
4. ✅ Verify working directory is clean
5. ✅ Run all pytest tests
6. ✅ Run all Bazel tests
7. ✅ Build release artifact
8. ✅ Create Git tag `v0.2.0`
9. ✅ Push tag to GitHub
10. ✅ Create GitHub Release
11. ✅ Upload `grantha-data-v0.2.0.zip`

Monitor the workflow progress at:
`https://github.com/USER/grantha-data/actions`

### 7. Verify Release

Once the workflow completes:

1. Go to: `https://github.com/USER/grantha-data/releases`
2. Verify the new release `v0.2.0` is listed
3. Verify the artifact `grantha-data-v0.2.0.zip` is attached
4. Check the release notes are accurate

### 8. Test Artifact Locally (Optional)

Download and verify the release artifact:

```bash
# Download from GitHub Releases
wget https://github.com/USER/grantha-data/releases/download/v0.2.0/grantha-data-v0.2.0.zip

# Extract
unzip grantha-data-v0.2.0.zip

# Verify structure
ls grantha-data-v0.2.0/
# Should show: manifest.json, schemas/, data/

# Verify manifest
cat grantha-data-v0.2.0/manifest.json | jq .version
# Should output: "0.2.0"

# Verify checksums (example)
cd grantha-data-v0.2.0
sha256sum -c <(jq -r '.files[] | "\(.sha256)  \(.path)"' manifest.json)
```

## Troubleshooting

### Workflow Fails: "Tag already exists"

**Cause**: You tried to release the same version twice.

**Solution**: Bump the version in VERSION file and try again.

### Workflow Fails: "Version mismatch"

**Cause**: You entered a different version in the workflow input than what's in the VERSION file.

**Solution**: Re-run the workflow and enter the exact version from the VERSION file.

### Workflow Fails: "Working directory has uncommitted changes"

**Cause**: You have local changes that aren't committed.

**Solution**:
```bash
git status
git add .
git commit -m "Prepare for release"
git push
```

Then re-run the workflow.

### Tests Fail During Release

**Cause**: Tests are failing in the current codebase.

**Solution**: Fix the failing tests before releasing:

```bash
# Run tests locally
pytest tools/lib/grantha_converter/ -v
bazel test //tools/lib/grantha_converter/...

# Fix issues, commit, and push
git add .
git commit -m "Fix failing tests"
git push
```

Then re-run the workflow.

### Build Fails During Release

**Cause**: Bazel build is broken.

**Solution**: Test the build locally:

```bash
bazel build //:grantha_data_release
```

Fix any issues, commit, push, and re-run the workflow.

## Manual Release (Emergency)

If the automated workflow is broken, you can create a release manually:

### 1. Build Locally

```bash
# Ensure VERSION file is correct
cat VERSION

# Build artifact
bazel build //:grantha_data_release

# Rename artifact
VERSION=$(cat VERSION | tr -d '\n')
cp bazel-bin/grantha-data-release.zip "grantha-data-v$VERSION.zip"
```

### 2. Create Tag

```bash
VERSION=$(cat VERSION | tr -d '\n')
git tag -a "v$VERSION" -m "Release v$VERSION"
git push origin "v$VERSION"
```

### 3. Create Release via GitHub CLI

```bash
VERSION=$(cat VERSION | tr -d '\n')

gh release create "v$VERSION" \
  --title "Grantha Data v$VERSION" \
  --notes "Manual release of v$VERSION" \
  "grantha-data-v$VERSION.zip"
```

## Release Artifact Contents

Each release artifact (`grantha-data-vX.Y.Z.zip`) contains:

```
grantha-data-vX.Y.Z/
├── manifest.json          # Release metadata with checksums
├── schemas/               # JSON Schema files
│   ├── grantha.schema.json
│   ├── grantha-envelope.schema.json
│   └── grantha-part.schema.json
└── data/
    └── upanishads/        # All Upanishad JSON files
        ├── isavasya/
        │   ├── isavasya-upanishad-vedantadesika.json
        │   └── ...
        ├── brihadaranyaka/
        │   ├── brihadaranyaka-upanishad/
        │   │   ├── envelope.json
        │   │   ├── part1.json
        │   │   └── ...
        └── ...
```

### manifest.json Structure

```json
{
  "version": "X.Y.Z",
  "schema_version": "X.Y.Z",
  "release_date": "2025-11-28T12:00:00Z",
  "checksums": {
    "manifest_sha256": "...",
    "data_sha256": "...",
    "schemas_sha256": "..."
  },
  "files": [
    {
      "path": "data/upanishads/isavasya/isavasya-upanishad-vedantadesika.json",
      "sha256": "abc123...",
      "size_bytes": 110592
    },
    ...
  ],
  "upanishads": [
    {
      "grantha_id": "isavasya-upanishad",
      "canonical_title": "ईशावास्योपनिषत्",
      "multipart": false,
      "commentaries": ["vedantadesika", "srivatsanarayana"]
    },
    ...
  ],
  "statistics": {
    "total_upanishads": 12,
    "total_commentaries": 18,
    "total_files": 95
  }
}
```

## Best Practices

### Version Bumps

- **Be conservative**: When in doubt, use a major bump for schema changes
- **Test thoroughly**: Run all tests before bumping version
- **Document changes**: Update CHANGELOG.md with clear descriptions

### Release Timing

- **Batch changes**: Don't release for every tiny change
- **Meaningful releases**: Group related changes into logical releases
- **Breaking changes**: Plan major versions carefully, provide migration guides

### Communication

- **Announce major versions**: Notify grantha-explorer maintainers
- **Breaking change warnings**: Be explicit in release notes
- **Migration support**: Provide examples and migration guides

## Post-Release

### Update Dependent Projects

If grantha-explorer or other consumers exist:

1. Create PR to update `data-version.json` in grantha-explorer
2. Test the integration
3. Update TypeScript types if schema changed
4. Merge and deploy

### Archive Old Documentation

If significant documentation was written for this release:

1. Move planning docs to `docs/archive/`
2. Keep only current versioning and release docs in `docs/`

## See Also

- `docs/VERSIONING.md` - Versioning strategy details
- `CHANGELOG.md` - Complete version history
- `CLAUDE.md` - General project instructions
