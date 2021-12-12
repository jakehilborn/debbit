#!/usr/bin/env bash
set -e
set -x

ROOT=$(dirname $(dirname $(cd "$(dirname "$0")"; pwd -P)))

# pyinstaller uses globally installed pip packages instead of pipenv packages
cd "$ROOT/src"
pip3 install -U pip
pip3 list --outdated --format=freeze | cut -d'=' -f1 | xargs -n1 pip3 install -U
[ -z $(pip3 list --outdated) ] # exit script if there are still outdated packages
pip3 install coverage==5.3.1 --force-reinstall

if [[ $(sw_vers -productVersion) == "10.12"* ]]; then
    echo "downgrading pyinstaller to work on 10.12"
    pip3 install pyinstaller==4.3 --force-reinstall # workaround "Executable contains code signature" bug on macOS 10.12
fi

find "$ROOT/src" -name "__pycache__" -print0 | xargs -0 rm -rf
rm -rf "$ROOT/src/build"
rm -rf "$ROOT/src/dist"

pyinstaller --clean -F -c debbit.py program_files/merchants/*.py
cp dist/debbit release/macOS

cd "$ROOT/src/release"
REL_VERSION=$(cat rel_version.txt)
mv macOS "debbit-$REL_VERSION-macOS"
zip -r "debbit-$REL_VERSION-macOS.zip" "debbit-$REL_VERSION-macOS"
