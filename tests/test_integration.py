import unittest
from src.models import db, Climber, Bloc, Success
from src.main import create_app

class TestIntegration(unittest.TestCase):

    def setUp(self):
        """Set up test variables and initialize app."""
        self.app = create_app(config_name="testing")
        self.app.testing = True
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        # Initialize the database within the app context
        with self.app_context:
            db.create_all()
            
    def tearDown(self):
        """Tear down all initialized variables."""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_index_route(self):
        """Test the index route."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b'Hello, World!')

    def test_register_success_api(self):
        """Test the API for registering a success"""        
        # Create test data
        climber = Climber(
            name="Test Climber",
            bib=42,
            club="Test Club",
            category="U16 F"
        )
        bloc = Bloc(
            tag="Bloc A",
            number="001"
        )
        
        # Add initial data
        print("Adding initial data")
        db.session.add_all([climber, bloc])
        db.session.commit()
        
        # Prepare the request
        payload = {
            "bib": 42,
            "bloc": "Bloc A"
        }
        
        # Send POST request
        print("Sending POST request")
        with self.app_context:
            response = self.client.post(
                '/api/v2/contest/success',
                json=payload,
                content_type='application/json'
            )
        
        print(f"Request sent correctly, response: {response}")
        
        # Verify the response
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], 'Well done')
        
        # Verify in the database
        success = Success.query.filter_by(climber_id=climber.id, bloc_id=bloc.id).first()
        self.assertIsNotNone(success)
        self.assertEqual(success.climber_id, climber.id)
        self.assertEqual(success.bloc_id, bloc.id)

    def test_register_success_invalid_data(self):
        """Test the API with invalid data"""
        # Test with missing data
        response = self.client.post(
            '/api/v2/contest/success',
            json={},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        
        # Test with non-existent climber
        response = self.client.post(
            '/api/v2/contest/success',
            json={"bib": 999, "bloc": "Bloc A"},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        
        # Test with non-existent bloc
        climber = Climber(name="Test Climber", bib=42, club="Test Club", category="SNH")
        db.session.add(climber)
        db.session.commit()
        
        response = self.client.post(
            '/api/v2/contest/success',
            json={"bib": 42, "bloc": "INVALID"},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_register_success_duplicate_entry(self):
        """Test the API with a duplicate entry"""
        # Create test data
        climber = Climber(
            name="Test Climber",
            bib=42,
            club="Test Club",
            category="SNH"
        )
        bloc = Bloc(
            tag="Bloc A",
            number="99"
        )
        
        # Add initial data
        db.session.add_all([climber, bloc])
        db.session.commit()
        
        # Prepare the request
        payload = {
            "bib": 42,
            "bloc": "Bloc A"
        }
        
        # Send the first POST request
        response = self.client.post(
            '/api/v2/contest/success',
            json=payload,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        
        # Send the second POST request with the same data
        response = self.client.post(
            '/api/v2/contest/success',
            json=payload,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data['success'])
        self.assertEqual(data['message'], 'Duplicate entry')

    def test_register_success_missing_fields(self):
        """Test the API with missing fields"""
        # Test with missing 'bib' field
        response = self.client.post(
            '/api/v2/contest/success',
            json={"bloc": "Bloc A"},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        
        # Test with missing 'bloc' field
        response = self.client.post(
            '/api/v2/contest/success',
            json={"bib": 42},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

if __name__ == "__main__":
    unittest.main()