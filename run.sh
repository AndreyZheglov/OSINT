#!/bin/bash

/home/tgbot_server/telegram-bot-api/bin/telegram-bot-api --api_id="5289743701" --api-hash="AAHakRDehtSxxEY5zIMDLlFHyPlJ6qYhmmU"

program=/home/tgbot_server/OSINT
cd $program
source env/Scripts/activate
python3 main.py

while true
do
    ps aux | grep python3 main.py > /dev/null
    if [ $? -ne 0 ]; then
        python3 main.py
    fi
done