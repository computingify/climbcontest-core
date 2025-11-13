from flask import Flask, request, jsonify
from models import db, Climber, Bloc
from google_sheets import GoogleSheet
from google_sheets_reader import populate_bloc, populate_climbers
import threading


google_sheet = GoogleSheet()
    
def sync_data_from_google_sheet():
    with app.app_context():
        populate_bloc(google_sheet)
        populate_climbers(google_sheet)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
with app.app_context():
    # Drop all tables and recreate the database
    print("Erasing database...")
    db.drop_all()
    db.create_all()
    print("Database recreated.")
    sync_data_from_google_sheet()
    
@app.route('/api/v2/contest/climber/name', methods=['POST'])
def check_climber():
    data = request.get_json()
    climber_bib = data.get('id')
    
    if not (climber_bib):
        message = 'Missing data'
        print(message)
        return jsonify({'success': False, 'message': message}), 400
    
    try:
        climber = Climber.query.filter_by(bib=climber_bib).first()
        if not climber:
            print(f'climber_id = {climber_bib} not present in DB, try to refresh it')
            # In that case pull the google sheet again to check if it's added in the meantime
            populate_climbers(google_sheet)
            
            climber = Climber.query.filter_by(bib=climber_bib).first()
            if not climber:
                message = 'Unregistered climber bib'
                print(message)
                return jsonify({'success': False, 'message': message}), 400
            
        print(f'Check climber bib = {climber.bib}, name = {climber.name}')
            
        return jsonify({
            'success': True,
            'message': 'Climber registered successfully',
            'id': climber.name
        }), 201
        
    except Exception as e:
        print(f"An error occurred: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'An error occurred'}), 400
    
@app.route('/api/v2/contest/bloc/name', methods=['POST'])
def check_bloc_tag():
    data = request.get_json()
    bloc_tag = data.get('id')
    
    if not (bloc_tag):
        message = 'Missing data'
        print(message)
        return jsonify({'success': False, 'message': message}), 400
    
    print(f'Check bloc tag = {bloc_tag}')
    
    try:
        bloc = Bloc.query.filter_by(tag=bloc_tag).first()
        # if not bloc or not bloc.tag:
        #     message = 'Unregistered bloc tag'
        #     print(message)
        #     return jsonify({'success': False, 'message': message}), 400
        
        return jsonify({
            'success': True,
            'message': 'Bloc registered successfully',
            'id': bloc.tag
            }), 201

    except Exception as e:
        db.session.rollback()
        message = "An error occurred: {e}"
        print(message)
        return jsonify({'success': False, 'message': 'An error occurred'}), 400

@app.route('/api/v2/contest/success', methods=['POST'])
def register_success():
    data = request.get_json()
    climber_bib = data.get('bib')
    bloc_tag = data.get('bloc')
    
    if not (climber_bib and bloc_tag):
        message = 'Missing data'
        print(message)
        return jsonify({'success': False, 'message': message}), 400
    
    try:
        climber = Climber.query.filter_by(bib=climber_bib).first()
        if not climber or not climber.name:
            if(not climber):
                message = f'Climber bib = {climber_bib} not present in DB'
            else:
                message = f'Climber bib = {climber_bib} Doesn\'t have setted name'
            print(message)
            return jsonify({'success': False, 'message': message}), 400
        
        bloc = Bloc.query.filter_by(tag=bloc_tag).first()
        # if not bloc or not bloc.tag:
        #     message = f'Unregistered bloc tag = {bloc_tag}'
        #     print(message)
        #     return jsonify({'success': False, 'message': message}), 400
        
        print(f'===> Success climber: {climber.name} | {climber.bib} | {bloc_tag}')

        update_google_sheet(climber, bloc)
        
        return jsonify({
            'success': True,
            'message': 'Well done'
        }), 201
    
    except Exception as e:
        db.session.rollback()
        message = f'An error occurred: {e}'
        print(message)
        return jsonify({'success': False, 'message': 'An error occurred'}), 400

def update_google_sheet(climber, bloc):
    # if not climber or not bloc or not climber.bib or not bloc.number:
    #     print('Error missing argument')
    bloc.number = 6
    # Update Google Sheet
    thread = threading.Thread(target=google_sheet.update_google_sheet, args=(climber.bib, int(bloc.number), climber.bib, bloc.number))
    thread.start()

# Launch the application
if __name__ == '__main__':
    
    # Path to your SSL certificate and private key
    ssl_context = ('security/cert.pem', 'security/key.pem')
    app.config["DEBUG"] = True
    use_reloader=False
    app.run(host='0.0.0.0', port=5007, ssl_context=ssl_context)