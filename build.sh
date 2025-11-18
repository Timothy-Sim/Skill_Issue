#!/usr/bin/env bash
# Exit on error
set -o errexit

pip install -r requirements.txt

echo "Downloading Stockfish 17.1..."
curl -L -o stockfish.tar https://github.com/official-stockfish/Stockfish/releases/download/sf_17.1/stockfish-ubuntu-x86-64-avx2.tar

echo "Extracting Stockfish..."
tar -xf stockfish.tar

echo "Moving executable..."
find . -type f -name 'stockfish-ubuntu-x86-64-avx2' -exec mv {} ./stockfish \;

rm stockfish.tar
rm -rf stockfish-ubuntu-x86-64-avx2

chmod +x ./stockfish
echo "Stockfish binary is ready."