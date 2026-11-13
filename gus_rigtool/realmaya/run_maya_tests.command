#!/bin/bash
# Gus_Rigtool real-Maya tests (5.6.35): double-click (the first time: right-click > Open).
# Writes maya_test_results.txt next to this file.
HERE="$(cd "$(dirname "$0")" && pwd)"
CFG="$HOME/gus_maya_tests_mayapy.txt"
MAYAPY="/Applications/Autodesk/maya2024/Maya.app/Contents/bin/mayapy"
[ -f "$CFG" ] && MAYAPY="$(cat "$CFG")"
if [ ! -x "$MAYAPY" ]; then
  echo "Maya's mayapy isn't at: $MAYAPY"
  echo "Find it (Maya.app > Contents > bin > mayapy), drag it into this window and press Enter."
  read -r -p "mayapy: " MAYAPY
  MAYAPY="${MAYAPY%"${MAYAPY##*[![:space:]]}"}"
  MAYAPY="${MAYAPY//\\ / }"
  MAYAPY="${MAYAPY%\'}"; MAYAPY="${MAYAPY#\'}"; MAYAPY="${MAYAPY%\"}"; MAYAPY="${MAYAPY#\"}"
  if [ ! -x "$MAYAPY" ]; then echo "Still not found - nothing was run."; read -r -p "Press Enter to close"; exit 1; fi
  echo "$MAYAPY" > "$CFG"
fi
echo "Using $MAYAPY"
"$MAYAPY" "$HERE/run_maya_tests.py" "$@"
echo
read -r -p "Press Enter to close"
