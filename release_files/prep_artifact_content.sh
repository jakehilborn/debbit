#!/usr/bin/env bash
set -e
set -x

ROOT=$(dirname $(cd "$(dirname "$0")"; pwd -P))

cd "$ROOT/src"
rm -rf release
mkdir -p release/common

tail -n +2 sample_config.txt > release/common/config.txt # the tail command removes the first line from the file
cp "$ROOT/release_files/INSTRUCTIONS.html" release/common
cp -a program_files release/common/program_files
cp "$ROOT/release_files/HOW_TO_EDIT_MERCHANTS.txt" release/common/program_files/merchants

cd "$ROOT/src/release"

# remove non source files
rm -rf common/program_files/cookies
rm -rf common/program_files/*.log
find common -name "__pycache__" -print0 | xargs -0 rm -rf
find common -name ".DS_Store" -delete

cp -a common macOS
cp -a common win64

# extract v0.30.0 from <html><body>You are being <a href="https://github.com/mozilla/geckodriver/releases/tag/v0.30.0">redirected</a>.</body></html>%
GECKODRIVER_VERSION=$(curl https://github.com/mozilla/geckodriver/releases/latest | sed 's|.*tag/\(.*\)\".*|\1|')

# macOS specific files
curl -LJO https://github.com/mozilla/geckodriver/releases/download/$GECKODRIVER_VERSION/geckodriver-$GECKODRIVER_VERSION-macos.tar.gz
tar -xzf geckodriver-*-macos.tar.gz
mv geckodriver macOS/program_files

# win64 specific files
curl -LJO https://github.com/mozilla/geckodriver/releases/download/$GECKODRIVER_VERSION/geckodriver-$GECKODRIVER_VERSION-win64.zip
unzip geckodriver-*-win64.zip
mv geckodriver.exe win64/program_files
cp "$ROOT/release_files/debbit_keep_window_open.bat" win64
unix2dos win64/config.txt # if we don't do this, Notepad on Windows 7 does not show new lines

# specific to author's dev env
rm -rf "$HOME/VirtualBox VMs/shared/debbit"
mkdir -p "$HOME/VirtualBox VMs/shared/debbit"
cp -a "$ROOT/release_files" "$HOME/VirtualBox VMs/shared/debbit"
cp -a "$ROOT/src" "$HOME/VirtualBox VMs/shared/debbit"

rm -rf "$HOME/VirtualBox VMs/shared_mac/Dropbox/debbit"
mkdir -p "$HOME/VirtualBox VMs/shared_mac/Dropbox/debbit"
cp -a "$ROOT/release_files" "$HOME/VirtualBox VMs/shared_mac/Dropbox/debbit"
cp -a "$ROOT/src" "$HOME/VirtualBox VMs/shared_mac/Dropbox/debbit"
