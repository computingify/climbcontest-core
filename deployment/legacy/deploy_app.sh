#!/bin/bash
# HERITAGE — deploiement Raspberry Pi, plus utilise depuis la migration Proxmox.
# Remplace par deployment/install.sh (spec 001). Conserve pour reference.

# Define variables
APP_DIR="/home/pi/climbcontest-core"
SYSTEMD_APP_NAME="climb_constest_server_app"
APP_PORT="5007"
REPO_URL="https://github.com/computingify/climbcontest-core.git"  # Replace with your Git repository URL
FLASK_APP="main.py"
FLASK_ENV="production"
ETH_IP=$(ip -o -4 addr list eth0 | awk '{print $4}' | cut -d/ -f1) # The IP address of the device where we are

# Step 1: Update system and install dependencies
echo "Updating system and installing dependencies..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git curl certbot python3-certbot-nginx

# Step 2: Clone the repository if it doesn't exist
if [ ! -d "$APP_DIR" ]; then
    echo "Cloning the repository..."
    git clone "$REPO_URL" "$APP_DIR"
fi

# Step 3: Set up a Python virtual environment
echo "Setting up a Python virtual environment..."
cd "$APP_DIR"
python3 -m venv venv
source venv/bin/activate

# Step 4: Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r deployement/requirements.txt

# Step 5: Set up the Flask application
echo "Setting up the Flask application..."
export FLASK_APP=$FLASK_APP
export FLASK_ENV=$FLASK_ENV
export APP_PORT=$APP_PORT
export ETH_IP=$ETH_IP

# Step 9: Create a systemd service file for the Flask app
echo "Creating a systemd service for the Flask app..."
sudo tee /etc/systemd/system/$SYSTEMD_APP_NAME.service <<EOF
[Unit]
Description=Gunicorn instance to serve climb contest server
After=network.target

[Service]
User=pi
Group=www-data
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/gunicorn -w 6 -b 0.0.0.0:$APP_PORT \
  -c $APP_DIR/gunicorn_config.py \
  --certfile=security/cert.pem \
  --keyfile=security/key.pem \
  main:app \
  --capture-output \
  --enable-stdio-inheritance \
  --access-logfile - \
  --error-logfile -

# Logging configuration
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Step 10: Start and enable the systemd service
echo "Starting and enabling the Flask app service..."
sudo systemctl start $SYSTEMD_APP_NAME
sudo systemctl enable $SYSTEMD_APP_NAME

# Step 11: Set up automatic certificate renewal with systemd timer
echo "Setting up Certbot renewal with systemd timer..."
sudo tee /etc/systemd/system/certbot-renew.service <<EOF
[Unit]
Description=Certbot Renewal Service

[Service]
Type=oneshot
ExecStart=/usr/bin/certbot renew --quiet --deploy-hook "systemctl reload nginx"
EOF

sudo tee /etc/systemd/system/certbot-renew.timer <<EOF
[Unit]
Description=Run Certbot renewal twice daily

[Timer]
OnCalendar=*-*-* 00/12:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Display final message with app URL
echo "Deployment completed! Your app should now be accessible at https://$ETH_IP:$APP_PORT"
