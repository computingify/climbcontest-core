"""Extensions Flask, isolées pour éviter les imports circulaires."""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
