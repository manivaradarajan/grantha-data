# Versioning Strategy

This document describes the versioning strategy for grantha-data releases.

## Overview

Grantha-data uses **Semantic Versioning (semver)** with a unified version number for both data and schemas. Each release is an immutable, versioned artifact distributed via GitHub Releases.

## Version Format

Versions follow the semver pattern: `MAJOR.MINOR.PATCH`

Example: `1.2.3`

## Version Components

### MAJOR

Increment the major version for **breaking schema changes**:

- Removing a required field
- Changing the type of an existing field
- Renaming a field
- Changing the structure of the JSON hierarchy
- Any change that would break existing parsers

**Examples:**
- `canonical_title` field removed → Major bump
- `grantha_id` changed from string to object → Major bump
- `structure_levels` array format changed → Major bump

### MINOR

Increment the minor version for **compatible schema additions**:

- Adding a new optional field
- Adding a new enum value
- Adding a new commentary type
- Any backward-compatible schema enhancement

**Examples:**
- New optional field `contributor` added → Minor bump
- New text_type value "stotra" added → Minor bump
- New structure_level type "verse" added → Minor bump

### PATCH

Increment the patch version for **data-only changes**:

- Text corrections and fixes
- New Upanishads added
- New commentaries added
- Hash updates due to content changes
- No schema modifications

**Examples:**
- Fixed typo in Isavasya Upanishad → Patch bump
- Added new commentary for Kena Upanishad → Patch bump
- Added entirely new Upanishad (Kaivalya) → Patch bump

## Single Source of Truth: VERSION File

The repository root contains a `VERSION` file with a single line containing the current version:

```
1.0.0
```

This file is:
- Manually updated before triggering a release
- Read by all build tools (Bazel, Python)
- Embedded in all generated JSON files via `schema_version` field
- Used to tag Git commits
- Used to name release artifacts

## Schema Version Field

All three JSON schemas include a required `schema_version` field:

```json
{
  "schema_version": "1.0.0",
  "grantha_id": "isavasya-upanishad",
  ...
}
```

This field:
- Is automatically injected during Markdown → JSON conversion
- Matches the VERSION file exactly
- Enables clients to validate compatibility
- Allows detecting version mismatches

## Compatibility Rules

### For Consumers (grantha-explorer)

- **Major version match required**: Client expecting v2.x.x cannot use v1.x.x data
- **Minor version compatibility**: Client expecting v1.2.x can safely use v1.5.x data
- **Patch version ignored**: Client expecting v1.2.3 can use any v1.2.x data

### Version Checking Logic

```javascript
function isCompatible(requiredVersion, dataVersion) {
  const [reqMajor, reqMinor, _] = requiredVersion.split('.').map(Number);
  const [dataMajor, dataMinor, __] = dataVersion.split('.').map(Number);

  // Major must match exactly
  if (reqMajor !== dataMajor) return false;

  // Data minor must be >= required minor (backward compatible)
  return dataMinor >= reqMinor;
}
```

## Version Lifecycle

### 1. Development

- Work on `main` branch
- VERSION file stays at current version
- Changes accumulate

### 2. Prepare Release

- Determine version bump (major/minor/patch)
- Update VERSION file
- Commit: `git commit -m "Bump version to X.Y.Z"`
- Push to main

### 3. Trigger Release

- Go to GitHub Actions
- Run "Release" workflow manually
- Confirm version matches VERSION file
- Indicate if breaking change

### 4. Automated Release

- Tests run automatically
- Artifact built with Bazel
- Git tag created: `vX.Y.Z`
- GitHub Release created
- Artifact uploaded: `grantha-data-vX.Y.Z.zip`

### 5. Consumption

- Clients fetch specific version from GitHub Releases
- Download URL pattern: `https://github.com/USER/grantha-data/releases/download/vX.Y.Z/grantha-data-vX.Y.Z.zip`
- Verify checksums from `manifest.json`

## Rollback Strategy

**Releases are immutable** - never delete tags or releases.

If a release has critical issues:

1. **For patch issues**: Create new patch version (e.g., v1.2.4 fixes v1.2.3)
2. **For breaking issues**: Document in CHANGELOG, create new patch with revert
3. **Never use**: Force-push, tag deletion, or release deletion

## Version History

See `CHANGELOG.md` for complete version history.

## Migration Guides

When releasing a major version, create a migration guide:

- Document breaking changes
- Provide before/after examples
- Update TypeScript types for grantha-explorer
- Create `docs/migrations/v1-to-v2.md`

## Pre-1.0 Versions

Versions before 1.0.0 are considered **unstable**:

- Schema may change without major version bumps
- Use only for development and testing
- No compatibility guarantees

First stable release will be `v1.0.0`.
