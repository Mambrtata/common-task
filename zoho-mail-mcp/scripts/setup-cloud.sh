#!/bin/bash
# Setup script pre cloud environment (claude.ai/code → nastavenia prostredia).
# Doinštaluje MCP knižnicu; samotný konektor sa načíta z repozitára cez
# PYTHONPATH v .mcp.json, takže netreba `pip install -e` ani čakať na klon.
#
# Obsah tohto súboru vlož do poľa „Setup script" v nastaveniach prostredia.

set -uo pipefail

# Ubuntu 24.04 má externally-managed Python, preto --break-system-packages.
if python3 -m pip install --break-system-packages "mcp>=2.0,<3.0"; then
    echo "MCP knižnica nainštalovaná."
elif python3 -m pip install "mcp>=2.0,<3.0"; then
    echo "MCP knižnica nainštalovaná (bez --break-system-packages)."
else
    echo "VAROVANIE: mcp sa nepodarilo nainštalovať, zoho-mail konektor nenaštartuje." >&2
fi

# Session sa nesmie zaseknúť na tom, že inštalácia zlyhala.
exit 0
