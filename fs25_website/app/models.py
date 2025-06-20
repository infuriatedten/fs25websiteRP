from app import db
from flask_login import UserMixin
from datetime import datetime

class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='player')  # player, dot_officer, supervisor, admin
    balance = db.Column(db.Float, default=0.0)
    login_time = db.Column(db.DateTime)
    logout_time = db.Column(db.DateTime)
    total_logged_hours = db.Column(db.Float, default=0.0)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))

    vehicles = db.relationship('Vehicle', backref='owner', lazy=True)
    permits = db.relationship('Permit', backref='owner', lazy=True)
    tickets = db.relationship('Ticket', backref='issued_to_user', lazy=True)

class Vehicle(db.Model):
    __tablename__ = 'vehicle'

    id = db.Column(db.Integer, primary_key=True)
    plate = db.Column(db.String(20), unique=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    inspections = db.relationship('Inspection', backref='vehicle', lazy=True)

class Company(db.Model):
    __tablename__ = 'company'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True)
    description = db.Column(db.Text)

    users = db.relationship('User', backref='company', lazy=True)
    tickets = db.relationship('Ticket', backref='company', lazy=True)

class Inspection(db.Model):
    __tablename__ = 'inspection'

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'))
    passed = db.Column(db.Boolean)
    notes = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Ticket(db.Model):
    __tablename__ = 'ticket'

    id = db.Column(db.Integer, primary_key=True)
    reason = db.Column(db.String(200))
    fine_amount = db.Column(db.Float, default=0.0)  # base fine if any
    issued_to = db.Column(db.Integer, db.ForeignKey('user.id'))  # user who pays the ticket
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    paid = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('TicketItem', backref='ticket', lazy=True)

    @property
    def total_price(self):
        return self.fine_amount + sum(item.total_price for item in self.items)

class TicketItem(db.Model):
    __tablename__ = 'ticket_item'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'))
    material_name = db.Column(db.String(100))
    quantity = db.Column(db.Integer)
    price_per_unit = db.Column(db.Float)

    @property
    def total_price(self):
        return self.quantity * self.price_per_unit

class Permit(db.Model):
    __tablename__ = 'permit'

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50))
    status = db.Column(db.String(20), default='pending')
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Order(db.Model):
    __tablename__ = 'order'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'))
    item_name = db.Column(db.String(100))
    quantity = db.Column(db.Integer)
    price_per_unit = db.Column(db.Float)

    @property
    def total_price(self):
        return self.quantity * self.price_per_unit
