#!/bin/bash
# Plný zber: celý dostupný register (19 CPV kódov), 4 paralelné vlákna.
# Na konci vyhodnotenie, build ceny.db a push snapshotu na GitHub.
set -u
cd "$(dirname "$0")"

echo "[$(date +%H:%M)] krok 1: zoznam zákaziek (všetky stránky)"
python3 01_zakazky.py --max-stran 200 > data/01_log.txt 2>&1

echo "[$(date +%H:%M)] krok 2: 4 paralelné vlákna"
for i in 0 1 2 3; do
  python3 02_dokumenty.py --limit-zakaziek 999999 --shard $i/4 \
    > data/02_shard$i.log 2>&1 &
done
wait

echo "[$(date +%H:%M)] krok 3+4: vyhodnotenie a build DB"
python3 03_vyhodnotenie.py > data/03_out.txt 2>&1
python3 04_postav_db.py > data/04_log.txt 2>&1
cp data/ceny.db ceny-pilot-2026-08.db

echo "[$(date +%H:%M)] commit + push"
git add ceny-pilot-2026-08.db
git commit -m "Plný zber: databáza z celého registra pozemných stavieb

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01KqjaLR9knmcRcHFzmDDq1V"
git push -u origin claude/verejne-obstaravania-rozpocty-r4lnl7
echo "[$(date +%H:%M)] HOTOVO"
