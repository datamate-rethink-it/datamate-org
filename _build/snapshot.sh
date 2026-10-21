#!/bin/bash
# Referenz-Snapshot der Live-Seite www.datamate.org.
#
# Laeuft EINMAL, vor dem Bau der statischen Seite, und haelt den Stand fest,
# gegen den spaeter verglichen wird. Jede Antwort landet unverändert in
# _build/reference/<pfad>/index.html, der HTTP-Status in status.tsv.
set -u
BASE="$(cd "$(dirname "$0")" && pwd)"
OUT="$BASE/reference"
STATUS="$BASE/reference-status.tsv"
: > "$STATUS"
n=0
while read -r url; do
    [ -z "$url" ] && continue
    path="${url#https://www.datamate.org}"
    case "$path" in
        */)   file="$OUT$path"index.html ;;
        "")   file="$OUT/index.html" ;;
        *.*)  file="$OUT$path" ;;
        *)    file="$OUT$path/index.html" ;;
    esac
    mkdir -p "$(dirname "$file")"
    code=$(curl -sS -m 60 -o "$file" -w '%{http_code}' "$url")
    bytes=$(wc -c < "$file" 2>/dev/null || echo 0)
    printf '%s\t%s\t%s\n' "$code" "$bytes" "$path" >> "$STATUS"
    n=$((n+1))
done < "$BASE/urls.txt"
echo "$n Adressen abgerufen"
awk -F'\t' '{c[$1]++} END {for (k in c) printf "  HTTP %s: %d\n", k, c[k]}' "$STATUS"
