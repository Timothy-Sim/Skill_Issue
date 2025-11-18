#!/usr/bin/env bash
# Exit on error
set -o errexit

pip install -r requirements.txt

echo "Downloading Stockfish..."
curl -L -o stockfish.zip https://stockfishchess.org/files/stockfish_16_linux_x64_avx2.zip

unzip stockfish.zip
mv stockfish-ubuntu-x86-64-avx2/stockfish-ubuntu-x86-64-avx2 ./stockfish
rm stockfish.zip
rm -rf stockfish-ubuntu-x86-64-avx2
chmod +x ./stockfish
echo "Stockfish binary is ready."