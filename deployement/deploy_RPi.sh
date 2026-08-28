#!/bin/bash
# HERITAGE — poussait vers le Pi 192.168.0.156, machine decommissionnee.
# Remplace par la chaine de livraison par tirage (spec 001).

ssh pi@192.168.0.156 << EOF
cd ~/climbcontest-core
git fetch -a
sudo systemctl stop climb_constest_server_app.service
git reset --hard origin/master
source venv/bin/activate
pip install -r deployement/requirements.txt
deactivate
sudo systemctl start climb_constest_server_app.service
EOF
