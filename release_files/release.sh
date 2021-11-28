#!/usr/bin/env bash
set -e
set -x

if [ "$#" -ne 2 ]; then
    echo "  Usage: release.sh REL_VERSION NEXT_VERSION"
    echo "Example: release.sh 2.1.3 2.1.4"
    exit 1
fi

REL_VERSION=$1
NEXT_VERSION=$2

ROOT=$(dirname $(cd "$(dirname "$0")"; pwd -P))

# update dependencies
cd "$ROOT/src"
pipenv update
git add Pipfile Pipfile.lock
git commit -m "Update dependencies" || true

# publish changelog snippet
cd "$ROOT"
echo "create changelog file, then press enter"
read
git add docs/updates/changelogs/*.txt
git commit -m "Release v$REL_VERSION changelog"

# set versions for release artifacts
CUR_VERSION_INT=$(grep "VERSION_INT = " src/debbit.py | cut -d'=' -f2 | tr -d '[:space:]')
REL_VERSION_INT=$((10#$CUR_VERSION_INT+1))
sed -E -i.sedcopy "s|VERSION = .*|VERSION = 'v$REL_VERSION'|" src/debbit.py
sed -E -i.sedcopy "s|VERSION_INT = .*|VERSION_INT = $REL_VERSION_INT|" src/debbit.py
find . -name "*.sedcopy" -delete
git add src/debbit.py
git commit -m "set release version v$REL_VERSION"

# prep artifact contents for artifacts that are built in VMs
"$ROOT/release_files/prep_artifact_contents.sh"
echo "create release artifacts, then press enter"
read

# set versions for dev version
sed -E -i.sedcopy "s|VERSION = .*|VERSION = 'v$NEXT_VERSION-dev'|" src/debbit.py
find . -name "*.sedcopy" -delete
git add src/debbit.py
git commit -m "set development version v$NEXT_VERSION-dev"

# upload files for release
echo ""
echo "Verify commits > push to GitHub > create release, then press enter"
read

# notify users of update available
echo $REL_VERSION_INT > docs/updates/latest.txt
git add docs/updates/latest.txt
git commit -m "Increment latest.txt version to notify users of available update"
echo ""
echo "Verify commits > push to GitHub"
