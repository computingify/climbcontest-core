from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Climber table to store climber details
class Climber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    bib = db.Column(db.Integer, unique=True, nullable=False)
    club = db.Column(db.String(50))
    category = db.Column(db.String(5))
    successes = db.relationship('Success', backref='climber', lazy=True)

class Success(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    climber_id = db.Column(db.Integer, db.ForeignKey('climber.id'), nullable=False)
    bloc_id = db.Column(db.Integer, db.ForeignKey('bloc.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    
class Bloc(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.String(5), unique=True, nullable=False)
    number = db.Column(db.String(10), unique=True, nullable=False)
    level = db.Column(db.String(15))
    
class BlocCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bloc_id = db.Column(db.Integer, db.ForeignKey('bloc.id'), nullable=False)
    category = db.Column(db.String(5), nullable=False)
    db.UniqueConstraint('bloc_id', 'category', name='unique_bloc_category')
    bloc = db.relationship('Bloc', backref=db.backref('bloc_categories', lazy=True))