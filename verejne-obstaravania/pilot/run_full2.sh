#!/bin/bash
# Pokračovanie plného zberu s rýchlym discovery dokumentov (tab Dokumenty).
# Predpokladá hotový data/zakazky.csv z kroku 1.
set -u
cd "$(dirname "$0")"

# pred prepísaním logov zachovaj IDs už spracovaných zákaziek
grep -h '^=== \[' data/02_shard*.log 2>/dev/null \
  | grep -oE '\[[0-9]+\]' | tr -d '[]' >> data/hotovo.txt || true

echo "[$(date +%H:%M)] krok 2: 4 paralelné vlákna (rýchle discovery)"
for i in 0 1 2 3 4 5; do
  python3 02_dokumenty.py --limit-zakaziek 999999 --shard $i/6 \
    > data/02_shard$i.log 2>&1 &
done
wait

echo "[$(date +%H:%M)] krok 3+4: vyhodnotenie a build DB"
python3 03_vyhodnotenie.py > data/03_out.txt 2>&1
python3 04_postav_db.py > data/04_log.txt 2>&1
cp data/ceny.db ceny-pilot-2026-08.db

echo "[$(date +%H:%M)] commit + push"
git add ceny-pilot-2026-08.db
git commit -m "Plný zber: databáza z celého registra pozemných stavieb + CRZ

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01KqjaLR9knmcRcHFzmDDq1V"
git push -u origin claude/verejne-obstaravania-rozpocty-r4lnl7
echo "[$(date +%H:%M)] HOTOVO"
