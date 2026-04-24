#!/usr/bin/env bash
# patch-bmm.sh — Idempotent install script for BMAD Issue Tracking
# Copies TOML overrides and shared custom tasks, then applies .patch files.
# Safe to re-run after BMM module updates.
#
# Usage: ./patch-bmm.sh [--force] [PROJECT_ROOT]
#   PROJECT_ROOT defaults to the repository root (detected from git).
#   --force overwrites existing files instead of skipping them.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ASSETS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CUSTOM_DIR="_bmad/_config/custom"
TOML_DIR="_bmad/custom"

FORCE=false
if [[ "${1:-}" == "--force" ]]; then
  FORCE=true
  shift
fi

# Resolve project root
if [ $# -ge 1 ]; then
  PROJECT_ROOT="$1"
else
  PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
fi

BMM_DIR="$PROJECT_ROOT/_bmad/bmm"
if [ ! -d "$BMM_DIR" ]; then
  echo "ERROR: $BMM_DIR not found. Run this script from a BMAD project root."
  exit 1
fi

# Check BMM version (TOML overrides require 6.3+)
BMM_VERSION=$(grep '# Version:' "$BMM_DIR/config.yaml" 2>/dev/null | awk '{print $3}' || echo "")
if [ -n "$BMM_VERSION" ]; then
  BMM_MAJOR=$(echo "$BMM_VERSION" | cut -d. -f1)
  BMM_MINOR=$(echo "$BMM_VERSION" | cut -d. -f2)
  if [ "$BMM_MAJOR" -lt 6 ] || { [ "$BMM_MAJOR" -eq 6 ] && [ "$BMM_MINOR" -lt 3 ]; }; then
    echo "WARN: BMM $BMM_VERSION detected. TOML overrides require BMM 6.3+."
    echo "      Patches will still apply, but on_complete hooks will be ignored."
    echo "      Update BMM to 6.3+ for full functionality."
    echo ""
  fi
fi

echo "Installing BMAD Issue Tracking..."
echo "  Project root: $PROJECT_ROOT"
echo "  BMM dir:      $BMM_DIR"
[ -n "$BMM_VERSION" ] && echo "  BMM version:  $BMM_VERSION"
$FORCE && echo "  Mode:         force (overwrite existing files)"
echo ""

APPLIED=0
SKIPPED=0
FAILED=0

# ──────────────────────────────────────────────
# 1. Copy shared custom tasks to _config/custom
# ──────────────────────────────────────────────

TARGET_CUSTOM="$PROJECT_ROOT/$CUSTOM_DIR"
mkdir -p "$TARGET_CUSTOM"

for task_file in "$ASSETS_DIR"/shared-tasks/bmad-bmm-issue-*.md; do
  [ -f "$task_file" ] || continue
  basename_f="$(basename "$task_file")"
  target="$TARGET_CUSTOM/$basename_f"
  if [ "$FORCE" = true ] || [ ! -f "$target" ]; then
    cp "$task_file" "$target"
    echo "  APPLIED: $CUSTOM_DIR/$basename_f"
    APPLIED=$((APPLIED + 1))
  else
    echo "  SKIPPED: $CUSTOM_DIR/$basename_f (already exists)"
    SKIPPED=$((SKIPPED + 1))
  fi
done

echo ""

# ──────────────────────────────────────────────
# 2. Copy TOML overrides to _bmad/custom
# ──────────────────────────────────────────────

TARGET_TOML="$PROJECT_ROOT/$TOML_DIR"
mkdir -p "$TARGET_TOML"

for toml_file in "$ASSETS_DIR"/custom/bmad-*.toml; do
  [ -f "$toml_file" ] || continue
  basename_f="$(basename "$toml_file")"
  target="$TARGET_TOML/$basename_f"
  if [ "$FORCE" = true ] || [ ! -f "$target" ]; then
    cp "$toml_file" "$target"
    echo "  APPLIED: $TOML_DIR/$basename_f"
    APPLIED=$((APPLIED + 1))
  else
    echo "  SKIPPED: $TOML_DIR/$basename_f (already exists)"
    SKIPPED=$((SKIPPED + 1))
  fi
done

echo ""

# ──────────────────────────────────────────────
# 3. Apply .patch files via git apply
# ──────────────────────────────────────────────

for patch_file in "$SCRIPT_DIR"/*.patch; do
  [ -f "$patch_file" ] || continue
  patch_name="$(basename "$patch_file")"

  # Check if already applied (reverse patch should apply cleanly)
  if git apply --reverse --check "$patch_file" >/dev/null 2>&1; then
    echo "  SKIPPED: $patch_name (already applied)"
    SKIPPED=$((SKIPPED + 1))
    continue
  fi

  # Apply the patch
  if git apply "$patch_file" 2>&1; then
    echo "  APPLIED: $patch_name"
    APPLIED=$((APPLIED + 1))
  else
    echo "  FAILED:  $patch_name"
    FAILED=$((FAILED + 1))
  fi
done

echo ""
echo "═══════════════════════════════════════"
echo "  Issue Tracking Install Summary"
echo "═══════════════════════════════════════"
echo "  Applied: $APPLIED"
echo "  Skipped: $SKIPPED (already exists)"
echo "  Failed:  $FAILED"
echo "═══════════════════════════════════════"

if [ "$FAILED" -gt 0 ]; then
  echo ""
  echo "Some patches failed to apply. This may indicate the BMM version has changed."
  echo "Run 'git apply --stat <patch-file>' to see what changed."
  exit 1
fi

echo ""
echo "All customizations applied successfully."
echo ""
echo "Next steps:"
echo "  1. Edit _bmad/bmm/config.yaml — set issue_tracking.platform to 'gitlab' or 'github'"
echo "  2. Add prd_key to your PRD frontmatter"
echo "  3. Run /bmad-bmm-issue-sync to create issues"
