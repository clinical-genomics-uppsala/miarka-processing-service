#!/usr/bin/env bash
# A script to start CGU services on miarka if containers/processes are not currently running.
# Run for example every 5 minuntes via cron

### Miarka processing service ###
cd /proj/ngi2024001/nobackup/bin/miarka-processing-service/miarka-processing-service/

#Check if service is up
if ! ps aux | grep miarka-processing-service | grep 11010 > /dev/null
then
    source /proj/ngi2024001/nobackup/bin/miarka-processing-service/miarka-processing-service/env/bin/activate
    nohup miarka-processing-service --config config/ --port 11010 --debug &
fi
