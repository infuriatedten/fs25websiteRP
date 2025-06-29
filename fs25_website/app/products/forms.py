from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, FloatField, IntegerField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange

class ProductForm(FlaskForm):
    name = StringField('Product Name',
                       validators=[DataRequired(), Length(min=2, max=100)])
    description = TextAreaField('Description',
                                validators=[Length(max=5000)]) # Optional, but with length limit
    price = FloatField('Price ($)',
                       validators=[DataRequired(), NumberRange(min=0.01, message="Price must be positive.")])
    quantity_available = IntegerField('Quantity Available',
                                      validators=[DataRequired(), NumberRange(min=0, message="Quantity cannot be negative.")])
    is_active = BooleanField('Product is Active (visible in marketplace)', default=True) # Default to active for new products
    submit = SubmitField('Save Product')
