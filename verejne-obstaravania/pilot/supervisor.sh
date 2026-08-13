#!/bin/bash
# Supervízor: drží zber pri živote bez zásahu zvonka.
# - ak vlákna zberu spadnú, reštartuje ich (resume cez hotovo.txt je okamžitý)
# - každých 30 min prerieďuje ZIPy (šetrí disk)
# - keď sú všetky zákazky hotové, spustí build DB a push, potom končí
set -u
cd "$(dirname "$0")"
LOG=data/supervisor.log

celkom() { tail -n +2 data/zakazky.csv | wc -l; }
hotove()  { sort -u data/hotovo.txt 2>/dev/null | wc -l; }

while true; do
  if ! ps ax -o args | grep -q "^python3 02_dokumenty"; then
    if [ "$(hotove)" -ge "$(celkom)" ]; then
      echo "[$(date +%H:%M)] zber hotový ($(hotove)) – finalizujem" >> $LOG
      python3 03_vyhodnotenie.py > data/03_out.txt 2>&1
      python3 04_postav_db.py  > data/04_log.txt 2>&1
      cp data/ceny.db ceny-pilot-2026-08.db
      git add ceny-pilot-2026-08.db && git commit -m "Finálny zber: databáza z celého registra

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01KqjaLR9knmcRcHFzmDDq1V" \
        && git push -u origin claude/verejne-obstaravania-rozpocty-r4lnl7
      echo "[$(date +%H:%M)] HOTOVO" >> $LOG
      exit 0
    fi
    echo "[$(date +%H:%M)] vlákna nebežia ($(hotove)/$(celkom)) – reštart" >> $LOG
    for i in 0 1 2 3 4 5; do
      nohup python3 02_dokumenty.py --limit-zakaziek 999999 --shard $i/6 \
        >> data/02_shard$i.log 2>&1 &
    done
  fi
  # údržba disku
  python3 07_prune.py >> data/prune.log 2>&1
  sleep 1800
done
