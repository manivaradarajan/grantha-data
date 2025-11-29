# Changelog

All notable changes to grantha-data will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Nothing yet

## [0.1.0] - 2025-11-28

### Added
- Initial release with versioning and release system
- VERSION file as single source of truth for version numbers
- `schema_version` field added to all three JSON schemas (grantha, grantha-envelope, grantha-part)
- Automatic schema version injection during Markdown → JSON conversion
- `grantha-manifest` CLI tool for generating release manifests
- Bazel build rule `grantha_release_artifact` for packaging releases
- Build target `//:grantha_data_release` for creating versioned release artifacts
- GitHub Actions workflow for automated CI testing
- GitHub Actions workflow for automated releases via workflow_dispatch
- Release artifacts distributed as `.zip` files via GitHub Releases
- Comprehensive `manifest.json` with checksums, file listings, and metadata
- Documentation: `docs/VERSIONING.md` - versioning strategy
- Documentation: `docs/RELEASING.md` - release process guide

### Changed
- All JSON files now include required `schema_version` field
- JSON schemas updated to require `schema_version` property with semver pattern
- `md_to_json.py` now auto-reads VERSION file and injects schema version
- `envelope_generator.py` now auto-reads VERSION file for envelope generation

### Technical Details
- **Total Upanishads**: 12
- **Total Commentaries**: 5
- **Total JSON Files**: 68
- **Schemas**: grantha.schema.json, grantha-envelope.schema.json, grantha-part.schema.json
- **Build System**: Bazel with custom release rule
- **CI/CD**: GitHub Actions
- **Distribution**: GitHub Releases

### Files Modified
- `VERSION` - Created
- `formats/schemas/grantha.schema.json` - Added schema_version
- `formats/schemas/grantha-envelope.schema.json` - Added schema_version
- `formats/schemas/grantha-part.schema.json` - Added schema_version
- `tools/lib/grantha_converter/md_to_json.py` - Version injection
- `tools/lib/grantha_converter/envelope_generator.py` - Version injection
- `tools/lib/grantha_converter/manifest_generator.py` - Created
- `tools/bazel/release.bzl` - Created
- `BUILD.bazel` - Added release target
- `formats/schemas/BUILD` - Added filegroup
- `pyproject.toml` - Added grantha-manifest CLI
- `tools/lib/grantha_converter/BUILD` - Added manifest generator binary
- `.github/workflows/test.yml` - Created
- `.github/workflows/release.yml` - Created

### Breaking Changes
- All JSON files now require `schema_version` field
- Existing JSON files without `schema_version` will fail validation
- Re-generate all JSON files from Markdown sources to update schema version

### Migration Guide
To update existing JSON files:

```bash
# Re-generate all Upanishads from Markdown sources
bazel build //structured_md/upanishads:all_upanishads_json

# Or manually add schema_version to existing JSON:
# Add this field at the top of each JSON file:
# "schema_version": "0.1.0"
```

---

## Release Links

- [0.1.0](https://github.com/USER/grantha-data/releases/tag/v0.1.0)

## Version History

| Version | Date       | Type  | Description                          |
|---------|------------|-------|--------------------------------------|
| 0.1.0   | 2025-11-28 | Minor | Initial release with versioning      |
