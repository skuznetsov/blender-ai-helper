#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: install_addon.sh [--method copy|symlink] [--version 5.0]

Installs or updates the AI Helper addon for Blender.

Options:
  --method   copy (default) or symlink
  --version  Blender version directory (default: 5.0)
EOF
}

METHOD="copy"
BLENDER_VERSION="5.0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --method)
      METHOD="${2:-}"
      shift 2
      ;;
    --version)
      BLENDER_VERSION="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ADDON_SRC="${REPO_ROOT}/ai_helper"

if [[ ! -d "${ADDON_SRC}" ]]; then
  echo "Addon source not found: ${ADDON_SRC}" >&2
  exit 1
fi

case "$(uname -s)" in
  Darwin)
    BASE_DIR="${HOME}/Library/Application Support/Blender"
    ;;
  Linux)
    BASE_DIR="${HOME}/.config/blender"
    ;;
  *)
    echo "Unsupported OS. Set BLENDER_ADDONS_DIR manually." >&2
    exit 1
    ;;
esac

ADDONS_DIR="${BASE_DIR}/${BLENDER_VERSION}/scripts/addons"
DEST="${ADDONS_DIR}/ai_helper"
mkdir -p "${ADDONS_DIR}"

if [[ "${METHOD}" == "symlink" ]]; then
  if [[ -e "${DEST}" || -L "${DEST}" ]]; then
    backup="${DEST}.bak.$(date +%Y%m%d%H%M%S)"
    mv "${DEST}" "${backup}"
    echo "Existing addon moved to ${backup}"
  fi
  ln -s "${ADDON_SRC}" "${DEST}"
  echo "Symlinked ${ADDON_SRC} -> ${DEST}"
elif [[ "${METHOD}" == "copy" ]]; then
  mkdir -p "${DEST}"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete --exclude "__pycache__" --exclude "*.pyc" "${ADDON_SRC}/" "${DEST}/"
  else
    rm -rf "${DEST}"
    cp -R "${ADDON_SRC}" "${DEST}"
  fi
  echo "Copied ${ADDON_SRC} -> ${DEST}"
else
  echo "Unknown method: ${METHOD}" >&2
  usage
  exit 1
fi

echo "Open Blender > Preferences > Add-ons and enable 'AI Helper'."
echo "After code changes, use F3 > Reload Scripts or disable/enable the addon."
