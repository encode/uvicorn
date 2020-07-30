#!/bin/bash
set -euo pipefail

rm -rfv ./uvicorn || true
mkdir ./uvicorn

# save current dir into var
CURDIR=${PWD}
# cd into base repo dir
cd ../../../.
# save base repo dir into var
REPODIR=${PWD}

# copy uvicorn skipping `contrib` dir
cp -r `ls -A $REPODIR | grep -v "contrib"` "${CURDIR}"/uvicorn

cd "${CURDIR}"
docker-compose up -d --build

echo "Waiting for uvicorn..."

for ((n=0;n<10;n++));
do
  if [[ $(docker-compose logs) == *" Uvicorn running on unix socket"* ]]; then
    echo "Uvicorn is ready, sending http request to nginx"
    STATUS=$(curl -m 3 -o /dev/null -s -w "%{http_code}\n" http://localhost:9000 || true)
    break
  else
    echo "Uvicorn not yet ready"; sleep 1s
  fi
done

if [[ "$STATUS" == 200 ]]; then
    echo "Success! Nginx responded with status code ${STATUS}"
    exit 0
  else
    echo "Error! Nginx responded with status code ${STATUS}"
    docker-compose logs -t
fi

docker-compose down -v
rm -rf ./uvicorn || true
exit 1
