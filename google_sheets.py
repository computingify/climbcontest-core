from sqlite3 import DataError
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import os
import base64
from io import BytesIO

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
# SPREADSHEET_ID = '1lOWe3j-4KG62wcKCsBd7T0Yj4iduFzH5QB76wS7dc9M' # 2024 edition
# SPREADSHEET_ID = '1ilQ2-ogmTfpgYa_oz4ogO9SN_jJvSTL9BogcmHxHtEo' # U11 U17 Nov 2025 edition ON Annony Escalade drive
SPREADSHEET_ID = '1h3e8QUSXnCJLSYSFyB8X92cppDubeDx0yi8mn3NSh5s' # Dec 2025
IMPORT = 'Import'

class GoogleSheet:
    def __init__(self):
        self.creds = self.authenticate_google()
        self.service = build('sheets', 'v4', credentials=self.creds)
        self.sheet = self.service.spreadsheets()

    def authenticate_google(self):
        """Authenticate with Google Sheets API."""
        creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        elif os.path.exists('token.base64'):
            # Load the Base64-encoded token
            with open("token.base64", "r") as f:  # The file with the Base64 content
                base64_data = f.read()

            # Decode the Base64 back to binary
            binary_data = base64.b64decode(base64_data)

            # Use BytesIO to simulate a file-like object
            token_stream = BytesIO(binary_data)
            creds = pickle.load(token_stream)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)

            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        return creds

    def update_google_sheet(self, items):
        """Update the Google Sheet with multiple climber and bloc information in a single request.
        
        Args:
            items: List of tuples (climber_id, bloc_id) to update
        """
        try:
            # Ensure items is a list (for backward compatibility)
            if not isinstance(items, list):
                items = [items]
            
            # Build the data to update: list of ranges and values
            data = []
            for climber_id, bloc_id in items:
                climber_row = climber_id + 3
                bloc_row = bloc_id + 1
                
                # Translate the Bloc ID to a column letter
                column_letter = self.number_to_excel_column(climber_row)
                score_range = f'{IMPORT}!{column_letter}{bloc_row}'
                
                data.append({
                    'range': score_range,
                    'values': [['A']]
                })
            
            # Make a single batch update request
            result = self.sheet.values().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={'data': data, 'valueInputOption': 'RAW'}
            ).execute()

            return result, True

        except Exception as error:
            print(f"An error occurred: {error}")
            return error, False
    
    def get_google_sheet_data(self, range_, sheet_name):
        """Retrieve data from a specific range in the Google Sheet."""
        try:
            result = self.sheet.values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{sheet_name}!{range_}"
            ).execute()

            values = result.get('values', [])
            return values, True
        except Exception as error:
            print(f"An error occurred: {error}")
            return None, False

    def number_to_excel_column(self, num):
        """Convert a number to an Excel column letter."""
        column = ""
        while num > 0:
            num -= 1
            column = chr(num % 26 + 65) + column
            num //= 26
        return column