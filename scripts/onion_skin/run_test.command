#!/bin/bash
# Onion Skin - the test in real Maya: double-click (first time: right-click > Open), or: bash run_test.command
HERE="$(cd "$(dirname "$0")" && pwd)"
CFG="$HOME/onion_skin_mayapy.txt"
MAYAPY="/Applications/Autodesk/maya2024/Maya.app/Contents/bin/mayapy"
[ -f "$CFG" ] && MAYAPY="$(cat "$CFG")"
if [ ! -x "$MAYAPY" ]; then
  echo "Maya's mayapy isn't at: $MAYAPY"
  read -r -p "Drag mayapy here and press Enter: " MAYAPY
  MAYAPY="${MAYAPY//\\ / }"; MAYAPY="${MAYAPY%"${MAYAPY##*[![:space:]]}"}"
  MAYAPY="${MAYAPY%\'}"; MAYAPY="${MAYAPY#\'}"
  if [ ! -x "$MAYAPY" ]; then echo "Still not found - nothing was run."; read -r -p "Press Enter"; exit 1; fi
  echo "$MAYAPY" > "$CFG"
fi
echo "Using $MAYAPY"
"$MAYAPY" "$HERE/tests/test_in_maya.py"
echo
read -r -p "Press Enter to close"
