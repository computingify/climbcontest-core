from flask import Flask, request, jsonify
from src.models import db, Climber, Bloc
from src.google_sheets import GoogleSheet
from src.google_sheets_reader import populate_bloc, populate_climbers
from src.database_handler import DatabaseHandler
import threading


class RestApi:
    
    def __init__(self, config_name=None):
        self.google_sheet = GoogleSheet()
        self.handler = DatabaseHandler()
        
        self.app = Flask(__name__)
        print("config_name = ", config_name)
        if config_name == 'testing':
            self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
            self.app.testing = True
            print("====== Testing mode ========")
        else:
            self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
            print("====== Production mode ========")
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(app)
        with app.app_context():
            # Drop all tables and recreate the database
            print("Erasing database...")
            db.drop_all()
            db.create_all()
            print("Database recreated.")
            if not self.app.testing:
                self.sync_data_from_google_sheet()
        return self.app


    
    def sync_data_from_google_sheet(self):
        with self.app.app_context():
            populate_bloc(self.google_sheet)
            populate_climbers(self.google_sheet)
    
    @self.app.route('/')
    def index():
        print('Hello, World!')
        return 'Hello, World!'

    # Use to check if the climber bib is already registered in the database
    @app.route('/api/v2/contest/climber/name', methods=['POST'])
    def check_climber(self):
        data = request.get_json()
        climber_bib = data.get('id')
        
        if not (climber_bib):
            message = 'Missing data'
            print(message)
            return jsonify({'success': False, 'message': message}), 400
        
        try:
            try:
                climber = self.handler.get_climber_by_bib(climber_bib)
            except ValueError as message:
                print(f'climber_id = {climber_bib} not present in DB, try to refresh it')
                # In that case pull the google sheet again to check if it's added in the meantime
                populate_climbers(google_sheet)
                try:
                    climber = self.handler.get_climber_by_bib(climber_bib)
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
    def check_bloc_tag(self):
        data = request.get_json()
        bloc_tag = data.get('id')
        
        if not (bloc_tag):
            message = 'Missing data'
            print(message)
            return jsonify({'success': False, 'message': message}), 400
        
        print(f'Check bloc tag = {bloc_tag}')
        
        try:
            try:
                bloc = self.handler.get_bloc_by_tag(bloc_tag)
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
    def register_success(self):
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
                climber = self.handler.get_climber_by_bib(climber_bib)
                bloc = self.handler.get_bloc_by_tag(bloc_tag)
            except ValueError as message:
                print(message)
                return jsonify({'success': False, 'message': message}), 400
                
            print(f'===> Success climber: {climber.name} | {climber.bib} | {bloc_tag}')

            self.update_google_sheet(climber, bloc)
            
            self.handler.add_success(climber, bloc)
            
            return jsonify({
                'success': True,
                'message': 'Well done'
            }), 201
        
        except Exception as e:
            db.session.rollback()
            message = f'An error occurred: {e}'
            print(message)
            return jsonify({'success': False, 'message': 'An error occurred'}), 400

    def update_google_sheet(self, climber, bloc):
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
    
