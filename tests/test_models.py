import unittest
from datetime import datetime
from src.models import db, Climber, Bloc, Success
from src.main import create_app
import os

class TestModels(unittest.TestCase):
    def setUp(self):
        """Test environnement configuration"""
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        """Unit test cleanup after test method is executed"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        # Supprime le fichier de la base de données de test
        if os.path.exists('test.db'):
            os.remove('test.db')

    def test_create_climber(self):
        """Add climber in the database"""
        # Création d'un nouveau grimpeur
        climber = Climber(
            name="John Doe",
            bib=1,
            club="Club A",
            category="SNH"
        )

        # Ajout et validation dans la base de données
        db.session.add(climber)
        db.session.commit()

        # Récupération du grimpeur depuis la base de données
        saved_climber = Climber.query.filter_by(name="John Doe").first()

        # Vérifications
        self.assertIsNotNone(saved_climber)
        self.assertEqual(saved_climber.name, "John Doe")
        self.assertEqual(saved_climber.bib, 1)
        self.assertEqual(saved_climber.club, "Club A")
        self.assertEqual(saved_climber.category, "SNH")
        
    def test_create_bloc(self):
        """Add bloc in the database"""
        # Création d'un nouveau bloc
        bloc = Bloc(
            tag="Bloc A",
            number="001"
        )

        # Ajout et validation dans la base de données
        db.session.add(bloc)
        db.session.commit()

        # Récupération du bloc depuis la base de données
        saved_bloc = Bloc.query.filter_by(tag="Bloc A").first()

        # Vérifications
        self.assertIsNotNone(saved_bloc)
        self.assertEqual(saved_bloc.tag, "Bloc A")
        self.assertEqual(saved_bloc.number, "001")
        
    def test_create_success(self):
        """Add success in the database"""
        climber = Climber(
            name="Steve Doe",
            bib=2,
            club="Club B",
            category="U16"
        )
        
        bloc = Bloc(
            tag="Bloc B",
            number="A2"
        )
        
        db.session.add_all([climber, bloc])
        db.session.commit()
        
        # Création d'un nouveau succès
        success = Success(
            climber_id=1,
            bloc_id=1,
            timestamp=datetime.now()
        )
        
        # Ajout et validation dans la base de données
        db.session.add(success)
        db.session.commit()
        
        # Récupération du succès depuis la base de données
        saved_success = Success.query.filter_by(climber_id=1).first()
        
        # Vérifications
        self.assertIsNotNone(saved_success)
        self.assertEqual(saved_success.climber_id, 1)
        self.assertEqual(saved_success.bloc_id, 1)
        self.assertIsNotNone(saved_success.timestamp)
        
    def test_2_success(self):
        """Add success in the database"""
        climber = Climber(
            name="Steve Doe",
            bib=2,
            club="Club B",
            category="U16"
        )
        
        bloc1 = Bloc(
            tag="A1",
            number="1"
        )
        bloc2 = Bloc(
            tag="B2",
            number="2"
        )
        
        db.session.add_all([climber, bloc1, bloc2])
        db.session.commit()
        
        # Création d'un nouveau succès
        success1 = Success(
            climber_id=1,
            bloc_id=1,
            timestamp=datetime.now()
        )
        success2 = Success(
            climber_id=1,
            bloc_id=2,
            timestamp=datetime.now()
        )
        
        # Ajout et validation dans la base de données
        db.session.add_all([success1, success2])
        db.session.commit()
        
        # Récupération du succès depuis la base de données
        saved_success = Success.query.filter_by(climber_id=1).all()
        
        # Vérifications
        self.assertIsNotNone(saved_success[0])
        self.assertEqual(saved_success[0].climber_id, 1)
        self.assertEqual(saved_success[0].bloc_id, 1)
        self.assertIsNotNone(saved_success[0].timestamp)
        self.assertIsNotNone(saved_success[1])
        self.assertEqual(saved_success[1].climber_id, 1)
        self.assertEqual(saved_success[1].bloc_id, 2)
        self.assertIsNotNone(saved_success[1].timestamp)
        
    def test_climber_successes(self):
        """Test a climber succeeding on multiple blocs and retrieving all successes"""
        climber = Climber(
            name="Alice Smith",
            bib=3,
            club="Club C",
            category="U18"
        )
        
        bloc1 = Bloc(
            tag="C1",
            number="3"
        )
        bloc2 = Bloc(
            tag="D2",
            number="4"
        )
        
        db.session.add_all([climber, bloc1, bloc2])
        db.session.commit()
        
        # Création de nouveaux succès
        success1 = Success(
            climber_id=climber.id,
            bloc_id=bloc1.id,
            timestamp=datetime.now()
        )
        success2 = Success(
            climber_id=climber.id,
            bloc_id=bloc2.id,
            timestamp=datetime.now()
        )
        
        # Ajout et validation dans la base de données
        db.session.add_all([success1, success2])
        db.session.commit()
        
        # Récupération des succès depuis la base de données
        saved_climber = Climber.query.filter_by(name="Alice Smith").first()
        saved_successes = saved_climber.successes
        
        # Vérifications
        self.assertEqual(len(saved_successes), 2)
        self.assertEqual(saved_successes[0].bloc_id, bloc1.id)
        self.assertEqual(saved_successes[1].bloc_id, bloc2.id)
        self.assertIsNotNone(saved_successes[0].timestamp)
        self.assertIsNotNone(saved_successes[1].timestamp)

if __name__ == '__main__':
    unittest.main()