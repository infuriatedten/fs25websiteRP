from app import db
from flask_login import UserMixin
from datetime import datetime

# Constants for Ticket statuses
TICKET_STATUS_UNPAID = "unpaid"
TICKET_STATUS_PAID = "paid"
TICKET_STATUS_DISPUTED = "disputed"
TICKET_STATUS_WARNING = "warning_issued"
TICKET_STATUS_COMPLIANCE_PENDING = "compliance_pending"
TICKET_STATUS_RESOLVED = "resolved"

DISPUTE_STATUS_NONE = "none"
DISPUTE_STATUS_PENDING = "pending_review"
DISPUTE_STATUS_APPROVED = "review_approved"
DISPUTE_STATUS_REJECTED = "review_rejected"


class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=True)
    role = db.Column(db.String(20), default='player')
    balance = db.Column(db.Float, default=0.0)
    discord_user_id = db.Column(db.String(50), unique=True, nullable=True)
    login_time = db.Column(db.DateTime, nullable=True)
    logout_time = db.Column(db.DateTime, nullable=True)
    total_logged_hours = db.Column(db.Float, default=0.0)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True)

    vehicles = db.relationship('Vehicle', backref='owner', lazy='dynamic', cascade="all, delete-orphan")
    permits = db.relationship('Permit', backref='owner', lazy='dynamic', cascade="all, delete-orphan")
    tickets_received = db.relationship('Ticket', foreign_keys='Ticket.issued_to', backref='recipient_user', lazy='dynamic')
    # tickets_issued = db.relationship('Ticket', foreign_keys='Ticket.issuer_id', backref='issuing_officer', lazy='dynamic') # Already have issuer on Ticket

class Vehicle(db.Model):
    __tablename__ = 'vehicle'
    id = db.Column(db.Integer, primary_key=True)
    plate = db.Column(db.String(20), unique=True, nullable=False)
    make = db.Column(db.String(50), nullable=True)
    model = db.Column(db.String(50), nullable=True)
    year = db.Column(db.Integer, nullable=True)
    color = db.Column(db.String(30), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    inspections = db.relationship('Inspection', backref='vehicle', lazy='dynamic', cascade="all, delete-orphan")
    def __repr__(self): return f'<Vehicle {self.plate} ({self.make} {self.model})>'

class Company(db.Model):
    __tablename__ = 'company'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    employees = db.relationship('User', backref='employer_company', lazy='dynamic')
    tickets_issued_to_company = db.relationship('Ticket', foreign_keys='Ticket.company_id', backref='recipient_company', lazy='dynamic')

class Inspection(db.Model):
    __tablename__ = 'inspection'
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=False)
    passed = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text, nullable=True) # General notes for inspection
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    inspector_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    inspector = db.relationship('User', foreign_keys=[inspector_id])

class Ticket(db.Model):
    __tablename__ = 'ticket'
    id = db.Column(db.Integer, primary_key=True)
    reason = db.Column(db.String(200), nullable=False) # Offense type/code
    notes = db.Column(db.Text, nullable=True) # Additional notes by issuer
    fine_amount = db.Column(db.Float, default=0.0) # Can be 0 for warnings

    status = db.Column(db.String(50), default=TICKET_STATUS_UNPAID, nullable=False) # Replaces 'paid'

    dispute_reason = db.Column(db.Text, nullable=True) # User's reason for disputing
    dispute_status = db.Column(db.String(50), default=DISPUTE_STATUS_NONE, nullable=True) # Admin's status on the dispute

    issued_to = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=True)
    issuer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) # Track updates

    items = db.relationship('TicketItem', backref='ticket', lazy='dynamic', cascade="all, delete-orphan")
    linked_vehicle = db.relationship('Vehicle', backref='tickets', lazy='joined')
    # issuer relationship already defined in User model via backref if needed, or can be explicit:
    issuer = db.relationship('User', foreign_keys=[issuer_id], backref='issued_tickets')

    @property
    def total_price(self): # This likely refers to fine_amount + items, if items are billable
        return (self.fine_amount or 0) + sum(item.total_price for item in self.items if item)

class TicketItem(db.Model):
    __tablename__ = 'ticket_item'
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False)
    material_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    price_per_unit = db.Column(db.Float, default=0.0)
    @property
    def total_price(self): return (self.quantity or 0) * (self.price_per_unit or 0)

class Permit(db.Model):
    __tablename__ = 'permit'
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='pending')
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=True)
    issue_date = db.Column(db.DateTime, nullable=True)
    expiry_date = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    vehicle_link = db.relationship('Vehicle', backref='permits', lazy='joined')

class Order(db.Model): # This is the original Order model, for ticket materials
    __tablename__ = 'order'
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=True)
    item_name = db.Column(db.String(100))
    quantity = db.Column(db.Integer)
    price_per_unit = db.Column(db.Float)
    @property
    def total_price(self): return (self.quantity or 0) * (self.price_per_unit or 0)

# --- E-commerce Models ---
class Product(db.Model): # ... (content unchanged) ...
    __tablename__ = 'product'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    quantity_available = db.Column(db.Integer, nullable=False, default=1)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    seller = db.relationship('User', backref=db.backref('products_for_sale', lazy='dynamic'))
    def __repr__(self): return f"<Product {self.name}>"

class ProductOrder(db.Model): # E-commerce orders
    __tablename__ = 'product_order'
    id = db.Column(db.Integer, primary_key=True)
    buyer_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    order_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(50), nullable=False, default='pending_payment')
    buyer = db.relationship('User', backref=db.backref('product_orders', lazy='dynamic'))
    items = db.relationship('ProductOrderItem', backref='product_order', lazy='dynamic', cascade="all, delete-orphan")
    def __repr__(self): return f"<ProductOrder {self.id}>"

class ProductOrderItem(db.Model):
    __tablename__ = 'product_order_item'
    id = db.Column(db.Integer, primary_key=True)
    product_order_id = db.Column(db.Integer, db.ForeignKey('product_order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity_ordered = db.Column(db.Integer, nullable=False)
    price_at_purchase = db.Column(db.Float, nullable=False)
    product = db.relationship('Product', lazy='joined')
    def __repr__(self): return f"<ProductOrderItem Order {self.product_order_id} Product {self.product_id}>"

class Transaction(db.Model):
    __tablename__ = 'transaction'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    description = db.Column(db.String(255), nullable=True)
    related_product_order_id = db.Column(db.Integer, db.ForeignKey('product_order.id'), nullable=True)
    user = db.relationship('User', backref=db.backref('transactions', lazy='dynamic'))
    related_ecommerce_order = db.relationship('ProductOrder', backref=db.backref('transaction_records', lazy='dynamic'))
    def __repr__(self): return f"<Transaction {self.id} User {self.user_id} Type {self.type} Amount {self.amount}>"
