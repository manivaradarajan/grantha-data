#!/bin/bash
set -e

# Parse arguments
SKIP_GEMINI=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --skip-gemini-tests)
      SKIP_GEMINI=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--skip-gemini-tests]"
      exit 1
      ;;
  esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Release Dry Run ===${NC}"
echo ""

# Check we're in the right directory
if [ ! -f VERSION ]; then
  echo -e "${RED}ERROR: VERSION file not found. Run this script from repository root.${NC}"
  exit 1
fi

# 1. Check environment
echo -e "${YELLOW}→ Checking environment...${NC}"
VERSION=$(cat VERSION | tr -d '\n')
echo -e "  ${GREEN}✓${NC} Version: ${BLUE}$VERSION${NC}"

# 2. Validate version format
echo -e "${YELLOW}→ Validating version format...${NC}"
if ! echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo -e "  ${RED}✗ Invalid version format: $VERSION${NC}"
  echo -e "  Expected: MAJOR.MINOR.PATCH (e.g., 1.2.3)"
  exit 1
fi
echo -e "  ${GREEN}✓${NC} Version format is valid semver"

# 3. Check Git status
echo -e "${YELLOW}→ Checking Git status...${NC}"
if [ -n "$(git status --porcelain)" ]; then
  echo -e "  ${YELLOW}⚠${NC}  Working directory has uncommitted changes"
  git status --short
  echo -e "  ${YELLOW}Note: Release workflow will fail if directory is not clean${NC}"
else
  echo -e "  ${GREEN}✓${NC} Working directory is clean"
fi

# 4. Check if tag exists
echo -e "${YELLOW}→ Checking if tag exists...${NC}"
if git rev-parse "v$VERSION" >/dev/null 2>&1; then
  echo -e "  ${RED}✗ Tag v$VERSION already exists!${NC}"
  echo -e "  ${YELLOW}Note: You need to bump the version in VERSION file${NC}"
  exit 1
else
  echo -e "  ${GREEN}✓${NC} Tag v$VERSION does not exist yet"
fi

# 5. Check Python environment
echo -e "${YELLOW}→ Checking Python environment...${NC}"
if ! command -v pytest &> /dev/null; then
  echo -e "  ${RED}✗ pytest not found${NC}"
  echo -e "  Run: pip install -e ."
  exit 1
fi
echo -e "  ${GREEN}✓${NC} pytest is available"

# 6. Run pytest tests
echo -e "${YELLOW}→ Running pytest tests...${NC}"
if pytest tools/lib/grantha_converter/ -q --tb=short; then
  echo -e "  ${GREEN}✓${NC} grantha_converter tests passed"
else
  echo -e "  ${RED}✗ grantha_converter tests failed${NC}"
  exit 1
fi

if [ "$SKIP_GEMINI" = true ]; then
  echo -e "  ${YELLOW}⊘${NC} gemini_processor tests skipped"
else
  if pytest tools/lib/gemini_processor/ -q --tb=short; then
    echo -e "  ${GREEN}✓${NC} gemini_processor tests passed"
  else
    echo -e "  ${RED}✗ gemini_processor tests failed${NC}"
    echo -e "  ${YELLOW}Hint: Run with --skip-gemini-tests to skip these tests${NC}"
    exit 1
  fi
fi

# 7. Run Bazel tests
echo -e "${YELLOW}→ Running Bazel tests...${NC}"
if bazel test //tools/lib/grantha_converter/... --test_output=errors 2>&1 | grep -q "PASSED"; then
  echo -e "  ${GREEN}✓${NC} Bazel tests passed"
else
  echo -e "  ${RED}✗ Bazel tests failed${NC}"
  exit 1
fi

# 8. Build release artifact
echo -e "${YELLOW}→ Building release artifact...${NC}"
BUILD_OUTPUT=$(bazel build //:grantha_data_release 2>&1)
if echo "$BUILD_OUTPUT" | grep -q "Build completed successfully"; then
  echo -e "  ${GREEN}✓${NC} Release artifact built successfully"
else
  echo -e "  ${RED}✗ Build failed${NC}"
  echo "$BUILD_OUTPUT" | tail -20
  exit 1
fi

# 9. Verify artifact exists
echo -e "${YELLOW}→ Verifying artifact...${NC}"
if [ ! -f bazel-bin/grantha-data-release.zip ]; then
  echo -e "  ${RED}✗ Artifact not created!${NC}"
  exit 1
fi
SIZE=$(ls -lh bazel-bin/grantha-data-release.zip | awk '{print $5}')
echo -e "  ${GREEN}✓${NC} Artifact created: ${BLUE}$SIZE${NC}"

# 10. Extract and validate manifest
echo -e "${YELLOW}→ Extracting and validating manifest...${NC}"

# Clean up any previous extraction
rm -rf "grantha-data-v$VERSION" 2>/dev/null || true

# Extract
unzip -q bazel-bin/grantha-data-release.zip

if [ ! -f "grantha-data-v$VERSION/manifest.json" ]; then
  echo -e "  ${RED}✗ Manifest not found in artifact${NC}"
  exit 1
fi

# Validate manifest version matches VERSION file
MANIFEST_VERSION=$(jq -r '.version' "grantha-data-v$VERSION/manifest.json")
if [ "$MANIFEST_VERSION" != "$VERSION" ]; then
  echo -e "  ${RED}✗ Manifest version mismatch: $MANIFEST_VERSION != $VERSION${NC}"
  exit 1
fi
echo -e "  ${GREEN}✓${NC} Manifest version matches: ${BLUE}$VERSION${NC}"

# Validate schema version matches
SCHEMA_VERSION=$(jq -r '.schema_version' "grantha-data-v$VERSION/manifest.json")
if [ "$SCHEMA_VERSION" != "$VERSION" ]; then
  echo -e "  ${RED}✗ Schema version mismatch: $SCHEMA_VERSION != $VERSION${NC}"
  exit 1
fi
echo -e "  ${GREEN}✓${NC} Schema version matches: ${BLUE}$VERSION${NC}"

# 11. Show release statistics
echo -e "${YELLOW}→ Release statistics:${NC}"
TOTAL_FILES=$(jq -r '.statistics.total_files' "grantha-data-v$VERSION/manifest.json")
TOTAL_UPANISHADS=$(jq -r '.statistics.total_upanishads' "grantha-data-v$VERSION/manifest.json")
TOTAL_COMMENTARIES=$(jq -r '.statistics.total_commentaries' "grantha-data-v$VERSION/manifest.json")
echo -e "  ${GREEN}✓${NC} Total files: ${BLUE}$TOTAL_FILES${NC}"
echo -e "  ${GREEN}✓${NC} Total Upanishads: ${BLUE}$TOTAL_UPANISHADS${NC}"
echo -e "  ${GREEN}✓${NC} Total commentaries: ${BLUE}$TOTAL_COMMENTARIES${NC}"

# 12. Verify checksums (sample first 3 files)
echo -e "${YELLOW}→ Verifying checksums (sample)...${NC}"
cd "grantha-data-v$VERSION"

# Check first 3 files
for i in 0 1 2; do
  FILE_PATH=$(jq -r ".files[$i].path" manifest.json)
  EXPECTED_SHA=$(jq -r ".files[$i].sha256" manifest.json)

  # Prepend "data/" to the path to get actual file location
  ACTUAL_FILE="data/$FILE_PATH"

  if [ -f "$ACTUAL_FILE" ]; then
    ACTUAL_SHA=$(shasum -a 256 "$ACTUAL_FILE" | awk '{print $1}')
    if [ "$EXPECTED_SHA" = "$ACTUAL_SHA" ]; then
      echo -e "  ${GREEN}✓${NC} $(basename $FILE_PATH)"
    else
      echo -e "  ${RED}✗ Checksum mismatch for $FILE_PATH${NC}"
      exit 1
    fi
  else
    echo -e "  ${RED}✗ File not found: $ACTUAL_FILE${NC}"
    exit 1
  fi
done

cd ..

# 13. Verify schema files are present
echo -e "${YELLOW}→ Verifying schema files...${NC}"
SCHEMAS=("grantha.schema.json" "grantha-envelope.schema.json" "grantha-part.schema.json")
for schema in "${SCHEMAS[@]}"; do
  if [ -f "grantha-data-v$VERSION/schemas/$schema" ]; then
    echo -e "  ${GREEN}✓${NC} $schema"
  else
    echo -e "  ${RED}✗ Missing schema: $schema${NC}"
    exit 1
  fi
done

# 14. Verify sample JSON has schema_version
echo -e "${YELLOW}→ Verifying JSON files have schema_version...${NC}"
SAMPLE_JSON=$(find "grantha-data-v$VERSION/data" -name "*.json" -type f | head -1)
if [ -n "$SAMPLE_JSON" ]; then
  JSON_SCHEMA_VERSION=$(jq -r '.schema_version' "$SAMPLE_JSON")
  if [ "$JSON_SCHEMA_VERSION" = "$VERSION" ]; then
    echo -e "  ${GREEN}✓${NC} Sample JSON has correct schema_version: ${BLUE}$VERSION${NC}"
  else
    echo -e "  ${RED}✗ Sample JSON schema_version mismatch: $JSON_SCHEMA_VERSION != $VERSION${NC}"
    exit 1
  fi
else
  echo -e "  ${RED}✗ No JSON files found in data directory${NC}"
  exit 1
fi

# Summary
echo ""
echo -e "${BLUE}=== Dry Run Complete ===${NC}"
echo ""
echo -e "${GREEN}✓ All checks passed!${NC}"
echo ""
echo -e "Release artifact is ready: ${BLUE}grantha-data-v$VERSION.zip${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Commit any pending changes"
echo "  2. Update CHANGELOG.md with release notes"
echo "  3. Commit: git commit -m 'Bump version to $VERSION'"
echo "  4. Push: git push origin main"
echo "  5. Go to GitHub Actions → Release workflow → Run workflow"
echo "  6. Enter version: $VERSION"
echo ""
echo -e "${YELLOW}Cleanup:${NC}"
echo "  rm -rf grantha-data-v$VERSION"
echo ""
