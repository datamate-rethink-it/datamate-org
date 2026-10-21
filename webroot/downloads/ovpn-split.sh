#!/bin/bash

echo "----------------------------"
echo "ionas - Ihr Online Assistent"
echo "ovpn-split.sh"
echo "----------------------------"

OVPN_SOURCE=$1

if [ "$#" -ne 1 ]; then
  echo "FEHLER: es wurde keine Datei als Parameter übergeben."
  exit 1
fi

if [ ! -e $OVPN_SOURCE ]; then
  echo "FEHLER: die angegebene Datei existiert nicht."
  exit 1
fi

filename=$(basename $1)
extension="${filename##*.}"
filename="${filename%.*}"

if [[ $extension != "ovpn" ]]; then
  echo "FEHLER: die angegebene Datei ist keine ovpn-Datei."
  exit 1
fi

sed '1,/<ca>/d;/<\/ca>/,$d' $OVPN_SOURCE > $filename"_ca.crt"
sed '1,/<cert>/d;/<\/cert>/,$d' $OVPN_SOURCE > $filename"_client.crt"
sed '1,/<key>/d;/<\/key>/,$d' $OVPN_SOURCE > $filename"_client.key"

echo "FERTIG!"
echo "----------------------------"
exit 0
