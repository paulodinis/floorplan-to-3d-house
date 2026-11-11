#!/usr/bin/env bash
# One-time setup of a project work dir (run inside it):  bash <skill>/scripts/setup_workspace.sh
# Copies the bundled textures to site3d/tex and checks the Python and Node dependencies. It downloads nothing:
# the three.js r160 files the local Playwright tests need ship with the plugin (scripts/web/three/).
set -euo pipefail
SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p site3d/tex export
cp -n "$SKILL"/scripts/web/tex/* site3d/tex/ || true
python3 -c "import ezdxf" 2>/dev/null || echo "WARNING: ezdxf not found (DXF read/write): python3 -m pip install ezdxf==1.4.5 (see references/inputs.md if PyPI is blocked)"
python3 -c "import pdfplumber, numpy, cv2, PIL" 2>/dev/null || echo "WARNING: install pdfplumber numpy opencv-python pillow (pip --break-system-packages)"
node -e "require('playwright')" 2>/dev/null || echo "WARNING: Playwright not found (needed for 3D tests, GLB export and renders)"
echo "workspace ready: $(pwd)"
