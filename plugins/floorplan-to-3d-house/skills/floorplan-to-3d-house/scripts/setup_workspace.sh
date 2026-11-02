#!/usr/bin/env bash
# One-time setup of a project work dir (run inside it):  bash <skill>/scripts/setup_workspace.sh
# Creates site3d/tex with the bundled textures, fetches ezdxf (DXF I/O) and the three.js r160 files the
# local Playwright tests need. PyPI/CDNs may be blocked in sandboxes; GitHub usually works.
set -euo pipefail
SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p site3d/tex export
cp -n "$SKILL"/scripts/web/tex/* site3d/tex/ || true
python3 -c "import ezdxf" 2>/dev/null || {
  [ -d ezdxf-src ] || git clone --depth 1 --branch v1.4.5 https://github.com/mozman/ezdxf.git ezdxf-src
  echo "ezdxf: use EZDXF_SRC=$PWD/ezdxf-src/src (scripts default to ./ezdxf-src/src)"; }
if [ ! -f three/t/build/three.module.js ]; then
  rm -rf three/_src && git clone --depth 1 --branch r160 --filter=blob:none --sparse https://github.com/mrdoob/three.js.git three/_src
  (cd three/_src && git sparse-checkout set build examples/jsm/controls examples/jsm/loaders examples/jsm/exporters examples/jsm/utils)
  mkdir -p three/t/build three/t/examples/jsm/controls
  cp three/_src/build/three.module.js three/t/build/
  cp three/_src/examples/jsm/controls/OrbitControls.js three/t/examples/jsm/controls/
  cp three/_src/examples/jsm/loaders/RGBELoader.js three/_src/examples/jsm/exporters/GLTFExporter.js three/_src/examples/jsm/utils/TextureUtils.js three/
fi
python3 -c "import pdfplumber, numpy, cv2, PIL" 2>/dev/null || echo "WARNING: install pdfplumber numpy opencv-python pillow (pip --break-system-packages)"
node -e "require('playwright')" 2>/dev/null || echo "WARNING: Playwright not found (needed for 3D tests, GLB export and renders)"
echo "workspace ready: $PWD"
