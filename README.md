# climbcontest-core

Dépôt **pivot** du projet ClimbContest — l'outil de gestion des compétitions de
bloc du club d'escalade d'Annonay.

Il porte le backend **et** la documentation et les specs de tout le projet, y
compris celles qui concernent l'application juge Android (dépôt
[`computingify/ClimbContest`](https://github.com/computingify/ClimbContest)).
Même modèle que `sowel-core`.

| Pour savoir… | Lire |
| --- | --- |
| Par où commencer (agents IA compris) | [`CLAUDE.md`](CLAUDE.md) |
| Ce qui existe et ce qui est cassé | [`docs/etat-des-lieux.md`](docs/etat-des-lieux.md) |
| La mécanique du classeur et l'algorithme de classement | [`docs/technical/classeur-google.md`](docs/technical/classeur-google.md) |
| Ce que le terrain impose | [`docs/contraintes-metier.md`](docs/contraintes-metier.md) |
| Les specs | [`docs/specs-index.md`](docs/specs-index.md) |
| Revenir à la version 2025-2026 | [`docs/plan-de-repli.md`](docs/plan-de-repli.md) |

> ⚠️ Ce dépôt est **public**. Aucun secret ne doit y être committé : un garde-fou
> `gitleaks` refuse les commits qui en contiennent (`scripts/hooks/install.sh`).

---


## Installation
clone the deploy file:
<code>
wget https://raw.githubusercontent.com/computingify/climbcontest-core/master/deployement/deploy_app.sh
</code>

enable executable
<code>
chmod +x /home/pi/deployement/deploy_app.sh
</code>

install
<code>
/home/pi/deployement/deploy_app.sh
</code>

### Certificates injection
In case of using headless machine, we need to made the first google sheet connection from a machine with embedded browser to obtain the token.pickle.
So copy all certificates from another machine to rapsi one:
From my Mac machine:
<code>
scp security/* token.pickle pi@<PI ADDRESS>:~/climbcontestserver/
</code>
be sure to have the *.pem files inside security folder

There Are 2 type of certificates:
- 1 for Android application https protocol
- 1 to connect to google sheet

## Update
From an host machine
<code>
chmod +x /home/pi/deployement/deploy_RPi.sh
./home/pi/deployement/deploy_RPi.sh
</code>

## Advance
### Start python virtual environnement
source venv/bin/activate

### Instalation
just install requirements.txt:
<code>
pip install -r requirements.txt
</code>

### Launch server side:
<code>
flask --app main.py --debug run
</code>

### Manually modify database
Use sqllitebrowser tool: https://sqlitebrowser.org
if the database is on ssh remote FS, follow this tuto: https://www.petergirnus.com/blog/how-to-use-sshfs-on-macosyes

# Here we are
To made it work follow this instruction to enable google sheet access:
https://developers.google.com/sheets/api/quickstart/go?hl=fr

Then you need to create a googlesheet and update the SPREADSHEET_ID inside google_sheets.py if you want to change the sheet.
Becareful to get the correct information from googlesheet fresh created:
The SPREADSHEET_ID you're using is set to 'contest'. However, the SPREADSHEET_ID should be the actual ID of your Google Spreadsheet, not the name.
Find the correct Spreadsheet ID:
Open your Google Sheets document.
In the URL, you will find something like this:
https://docs.google.com/spreadsheets/d/1aBcD_XYZ1234aBcD_XYZ5678/edit#gid=0
The part after /d/ and before /edit is your Spreadsheet ID:
1aBcD_XYZ1234aBcD_XYZ5678
Update your SPREADSHEET_ID:
SPREADSHEET_ID = '1aBcD_XYZ1234aBcD_XYZ5678'  # Replace with your actual Spreadsheet ID

After that you shoud be able to send the correct information to googlesheet by simulate API request using postman

# HTTPS

for developpement create a self signed certificat:
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

Flask itself can serve HTTPS, but it's not suitable for production (use a WSGI server like gunicorn or uWSGI for production). For simplicity, here's how you can use Flask's built-in SSL support.
Shall do for the production:
Use gunicorn with HTTPS:
gunicorn --certfile cert.pem --keyfile key.pem -w 4 -b 0.0.0.0:5007 main:app

# Render start command
gunicorn main:app --capture-output --enable-stdio-inheritance --access-logfile - --error-logfile -

# DEBUG

sudo systemctl restart climb_contest_server_app.service
sudo journalctl -fu climb_contest_server_app.service

# Use to deploy on hosted server
Store the token into base64 to use it on deployment server:
base64 -i token.pickle | pbcopy

# Googlesheet access
## 1st possibility
To be able to use the google sheet, the only way I find is to copy the Etienne's google sheet in ADN-Dev one. By the way, I can access to it in write mode.

## 2nd possibility (the best one)
Add adrien.jouve@adn-dev.fr as writer in shared options.
If it doesn't work, open writer mode to someone have the link.