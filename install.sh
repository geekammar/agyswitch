#!/usr/bin/env bash
# AGY Switch (ags) - Headless Linux VPS Installer & Updater
# Minimal, idempotent, zero-daemon installation script.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_SOURCE="${SCRIPT_DIR}/bin/ags"
INSTALL_PREFIX="${HOME}/.local"
AGS_DATA_DIR="${AGS_HOME:-${HOME}/.agyswitch}"
UNINSTALL=false
UPDATE=false
CHECK_ONLY=false
SYSTEM_WIDE=false

usage() {
    cat << 'EOF'
Usage: ./install.sh [OPTIONS]

Options:
  --user            Install for current user into ~/.local/bin (default)
  --system          Install system-wide into /usr/local/bin (requires root)
  --prefix DIR      Set custom installation prefix (default: ~/.local)
  --update          Update repository from origin and refresh symlinks
  --check           Verify prerequisites without making any changes
  --uninstall       Remove ags binary symlink (preserves ~/.agyswitch data)
  -h, --help        Show this help message
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --user)
            SYSTEM_WIDE=false
            INSTALL_PREFIX="${HOME}/.local"
            shift
            ;;
        --system)
            SYSTEM_WIDE=true
            INSTALL_PREFIX="/usr/local"
            shift
            ;;
        --prefix)
            INSTALL_PREFIX="$2"
            shift 2
            ;;
        --update)
            UPDATE=true
            shift
            ;;
        --check)
            CHECK_ONLY=true
            shift
            ;;
        --uninstall)
            UNINSTALL=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            ;;
    esac
done

TARGET_BIN="${INSTALL_PREFIX}/bin"

# Prerequisite Checks
check_prerequisites() {
    echo "Checking system prerequisites for AGY Switch..."

    # 1. Python 3.8+
    if ! command -v python3 >/dev/null 2>&1; then
        echo "[ERROR] Python 3 was not found in PATH. Please install Python 3.8 or higher." >&2
        return 1
    fi

    if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >/dev/null 2>&1; then
        echo "[ERROR] Python version $(python3 --version) is too old. Python 3.8+ is required." >&2
        return 1
    fi
    echo "[OK] Python 3: $(python3 --version)"

    # 2. D-Bus session support (dbus-run-session)
    if command -v dbus-run-session >/dev/null 2>&1; then
        echo "[OK] D-Bus session isolation: available ($(command -v dbus-run-session))"
    else
        echo "[WARN] 'dbus-run-session' not found in PATH."
        echo "       D-Bus session isolation improves token security on headless VPS."
        echo "       You can install it on Ubuntu/Debian with: apt-get install -y dbus-x11 dbus-bin"
    fi

    # 3. Google Antigravity CLI (agy)
    local agy_found=false
    if command -v agy >/dev/null 2>&1; then
        echo "[OK] Antigravity CLI ('agy'): available ($(command -v agy))"
        agy_found=true
    elif [[ -x "${HOME}/.local/bin/agy" ]]; then
        echo "[OK] Antigravity CLI ('agy'): found in ${HOME}/.local/bin/agy"
        agy_found=true
    elif [[ -x "/root/.local/bin/agy" ]]; then
        echo "[OK] Antigravity CLI ('agy'): found in /root/.local/bin/agy"
        agy_found=true
    elif [[ -n "${AGY_BIN:-}" && -x "${AGY_BIN:-}" ]]; then
        echo "[OK] Antigravity CLI ('agy'): found at AGY_BIN=${AGY_BIN}"
        agy_found=true
    fi

    if [[ "$agy_found" = false ]]; then
        echo "[WARN] Antigravity CLI ('agy') binary was not found in standard paths."
        echo "       You can still use 'ags' to manage profiles, but sessions will require"
        echo "       'agy' installed or exported via AGY_BIN."
    fi

    return 0
}

# Uninstall
if [[ "$UNINSTALL" = true ]]; then
    echo "Uninstalling AGY Switch executable symlink..."
    if [[ -L "${TARGET_BIN}/ags" || -f "${TARGET_BIN}/ags" ]]; then
        rm -f "${TARGET_BIN}/ags"
        echo "[OK] Removed ${TARGET_BIN}/ags"
    else
        echo "No ags binary found at ${TARGET_BIN}/ags"
    fi

    echo ""
    echo "Note: Your profile data, Google OAuth tokens, and conversation history in:"
    echo "      ${AGS_DATA_DIR}"
    echo "      have been preserved untouched."
    echo "To completely purge all account data, delete that directory manually."
    exit 0
fi

# Check Only
if [[ "$CHECK_ONLY" = true ]]; then
    check_prerequisites
    echo ""
    echo "Prerequisite check completed successfully."
    exit 0
fi

# Update
if [[ "$UPDATE" = true ]]; then
    echo "Updating AGY Switch application..."
    if [[ -d "${SCRIPT_DIR}/.git" ]]; then
        echo "Pulling latest changes from git repository..."
        git -C "${SCRIPT_DIR}" pull --ff-only
    else
        echo "Note: Not a git repository. Skipping git pull."
    fi
    echo ""
fi

# Perform Installation
check_prerequisites
echo ""

if [[ ! -f "${BIN_SOURCE}" ]]; then
    echo "[ERROR] Entrypoint binary not found at ${BIN_SOURCE}" >&2
    exit 1
fi

chmod +x "${BIN_SOURCE}"
mkdir -p "${TARGET_BIN}"

# Create symlink
ln -sf "${BIN_SOURCE}" "${TARGET_BIN}/ags"
echo "[OK] Linked ${BIN_SOURCE} -> ${TARGET_BIN}/ags"

# Check PATH
case ":$PATH:" in
    *":${TARGET_BIN}:"*)
        echo "[OK] ${TARGET_BIN} is already present in your PATH."
        ;;
    *)
        echo ""
        echo "[NOTICE] ${TARGET_BIN} is not in your current PATH."
        echo "To use 'ags' from anywhere, add it to your shell configuration:"
        echo "    echo 'export PATH=\"${TARGET_BIN}:\$PATH\"' >> ~/.bashrc"
        echo "    source ~/.bashrc"
        ;;
esac

echo ""
echo "=================================================="
echo "    AGY Switch (ags) installed successfully!     "
echo "=================================================="
echo "Application code: ${SCRIPT_DIR}"
echo "Executable:       ${TARGET_BIN}/ags"
echo "Profile data dir: ${AGS_DATA_DIR}"
echo ""
echo "Quick Start:"
echo "  ags               # Open mobile-friendly numbered menu"
echo "  ags add personal  # Add a new named profile"
echo "  ags list          # List profiles and auth status"
echo "  ags run personal  # Start an isolated session"
echo "  ags run personal -c # Resume latest conversation"
echo "=================================================="
