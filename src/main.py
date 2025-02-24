from flask import Flask, request, jsonify
from src.models import db, Climber, Bloc
from src.google_sheets import GoogleSheet
from src.google_sheets_reader import populate_bloc, populate_climbers
from src.database_handler import DatabaseHandler
import threading


google_sheet = GoogleSheet()
handler = DatabaseHandler()
    
def sync_data_from_google_sheet(app):
    with app.app_context():
        populate_bloc(google_sheet)
        populate_climbers(google_sheet)

def create_app(config_name=None):
    app = Flask(__name__)
    print("config_name = ", config_name)
    if config_name == 'testing':
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
        app.testing = True
        print("====== Testing mode ========")
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
        print("====== Production mode ========")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    with app.app_context():
        # Drop all tables and recreate the database
        print("Erasing database...")
        db.drop_all()
        db.create_all()
        print("Database recreated.")
        if not app.testing:
            sync_data_from_google_sheet(app)
    return app

app = create_app()
    
@app.route('/')
def index():
    print('Hello, World!')
    return 'Hello, World!'

# Use to check if the climber bib is already registered in the database
@app.route('/api/v2/contest/climber/name', methods=['POST'])
def check_climber():
    data = request.get_json()
    climber_bib = data.get('id')
    
    if not (climber_bib):
        message = 'Missing data'
        print(message)
        return jsonify({'success': False, 'message': message}), 400
    
    try:
        try:
            climber = handler.get_climber_by_bib(climber_bib)
        except ValueError as message:
            print(f'climber_id = {climber_bib} not present in DB, try to refresh it')
            # In that case pull the google sheet again to check if it's added in the meantime
            populate_climbers(google_sheet)
            try:
                climber = handler.get_climber_by_bib(climber_bib)
            except ValueError as message:
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
    
# Use to check if the bloc tag is already registered in the database
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
        try:
            bloc = handler.get_bloc_by_tag(bloc_tag)
        except ValueError as message:
            print(message)
            return jsonify({'success': False, 'message': message}), 400
        
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

# Use by application to register a success of a climber on a bloc (the only API that write)
@app.route('/api/v2/contest/success', methods=['POST'])
def register_success():
    print('###########################################################')
    data = request.get_json()
    climber_bib = data.get('bib')
    bloc_tag = data.get('bloc')
    
    print(f'===> Register success climber: {climber_bib} | bloc: {bloc_tag}')
    
    if not (climber_bib and bloc_tag):
        message = 'Missing data'
        print(message)
        return jsonify({'success': False, 'message': message}), 400
    
    try:
        try:
            climber = handler.get_climber_by_bib(climber_bib)
            bloc = handler.get_bloc_by_tag(bloc_tag)
        except ValueError as message:
            print(message)
            return jsonify({'success': False, 'message': message}), 400
            
        print(f'===> Success climber: {climber.name} | {climber.bib} | {bloc_tag}')

        update_google_sheet(climber, bloc)
        
        handler.add_success(climber, bloc)
        
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
    if not climber or not bloc or not climber.bib or not bloc.number:
        print('Error missing argument')
        
    # Update Google Sheet
    thread = threading.Thread(target=google_sheet.update_google_sheet, args=(climber.bib, int(bloc.number), climber.bib, bloc.number))
    thread.start()

# # Launch the application
# if __name__ == '__main__':
#     # Path to your SSL certificate and private key
#     ssl_context = ('security/cert.pem', 'security/key.pem')
#     app.config["DEBUG"] = True
#     use_reloader=False
#     app.run(host='0.0.0.0', port=5007, ssl_context=ssl_context)
    
