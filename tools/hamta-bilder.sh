#!/bin/sh
# Hämtar alla bilder som sajten använder från media.treknivar.se till mappen media/.
# Kör från repots rot:  sh tools/hamta-bilder.sh
cd "$(dirname "$0")/.." || exit 1
while IFS= read -r f; do
  [ -z "$f" ] && continue
  if [ ! -f "media/$f" ]; then
    mkdir -p "media/$(dirname "$f")"
    curl -fsSL "https://media.treknivar.se/$f" -o "media/$f" && echo "OK  $f" || echo "FEL $f"
  fi
done < tools/media-list.txt
