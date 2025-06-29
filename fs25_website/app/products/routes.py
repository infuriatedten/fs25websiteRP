from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from . import bp
from app.models import Product, User
from app import db
from app.discord_utils import send_discord_webhook_message, create_product_embed
from .forms import ProductForm # Import ProductForm

@bp.route('/new', methods=['GET', 'POST'])
@login_required
def create_product():
    form = ProductForm()
    if form.validate_on_submit():
        product = Product(
            name=form.name.data,
            description=form.description.data,
            price=form.price.data,
            quantity_available=form.quantity_available.data,
            user_id=current_user.id,
            is_active=form.is_active.data # Usually true by default from form
        )
        db.session.add(product)
        db.session.commit()
        flash('Product listed successfully!', 'success')

        webhook_url = current_app.config.get('DISCORD_WEBHOOK_URL_PRODUCT_UPDATES')
        if webhook_url:
            try:
                product_to_notify = Product.query.get(product.id)
                if product_to_notify and product_to_notify.seller: # Ensure seller is loaded
                    embed = create_product_embed(product_to_notify, title_prefix="New Product Listed: ")
                    send_discord_webhook_message(webhook_url, embeds=[embed], username="E-commerce Bot")
                else:
                    current_app.logger.error(f"Failed to fetch product or seller for Discord notification: {product.id}")
            except Exception as e:
                current_app.logger.error(f"Error sending Discord new product notification: {e}")
        else:
            current_app.logger.warning("DISCORD_WEBHOOK_URL_PRODUCT_UPDATES not set for new product.")
        return redirect(url_for('products.my_products'))

    # For GET request or if form validation fails
    return render_template('products/create_edit_product.html', title="Create New Product", form=form)


@bp.route('/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if product.user_id != current_user.id and not current_user.role in ['admin', 'supervisor']: # Allow admin/supervisor to edit
        flash('You are not authorized to edit this product.', 'danger')
        return redirect(url_for('products.list_products'))

    form = ProductForm(obj=product) # Pre-populate form with existing product data

    if form.validate_on_submit():
        product.name = form.name.data
        product.description = form.description.data
        product.price = form.price.data
        product.quantity_available = form.quantity_available.data
        product.is_active = form.is_active.data
        db.session.commit()
        flash('Product updated successfully!', 'success')

        webhook_url = current_app.config.get('DISCORD_WEBHOOK_URL_PRODUCT_UPDATES')
        if webhook_url:
            try:
                product_to_notify = Product.query.get(product.id)
                if product_to_notify and product_to_notify.seller:
                    embed = create_product_embed(product_to_notify, title_prefix="Product Updated: ")
                    send_discord_webhook_message(webhook_url, embeds=[embed], username="E-commerce Bot")
                else:
                    current_app.logger.error(f"Failed to fetch product/seller for update notification: {product.id}")
            except Exception as e:
                current_app.logger.error(f"Error sending Discord product update notification: {e}")
        else:
            current_app.logger.warning("DISCORD_WEBHOOK_URL_PRODUCT_UPDATES not set for product update.")
        return redirect(url_for('products.my_products'))

    # For GET request or if form validation fails on POST
    return render_template('products/create_edit_product.html', title=f"Edit {product.name}", form=form, product=product)


@bp.route('/mine')
@login_required
def my_products():
    user_products = Product.query.filter_by(user_id=current_user.id).order_by(Product.date_posted.desc()).all()
    return render_template('products/my_products.html', products=user_products, title="My Listed Products")

@bp.route('/') # Marketplace view
def list_products():
    all_active_products = Product.query.filter_by(is_active=True).order_by(Product.date_posted.desc()).all()
    return render_template('products/list_products.html', products=all_active_products, title="Marketplace")

@bp.route('/<int:product_id>/deactivate', methods=['POST'])
@login_required
def deactivate_product(product_id):
    product = Product.query.get_or_404(product_id)
    if product.user_id != current_user.id and not current_user.role in ['admin', 'supervisor']:
        flash('You are not authorized to modify this product.', 'danger')
        return redirect(url_for('products.list_products'))

    product.is_active = False
    db.session.commit()
    flash(f"Product '{product.name}' has been deactivated.", 'success')
    # Optional: Send Discord notification
    return redirect(url_for('products.my_products'))

@bp.route('/<int:product_id>/activate', methods=['POST'])
@login_required
def activate_product(product_id):
    product = Product.query.get_or_404(product_id)
    if product.user_id != current_user.id and not current_user.role in ['admin', 'supervisor']:
        flash('You are not authorized to modify this product.', 'danger')
        return redirect(url_for('products.list_products'))

    product.is_active = True
    db.session.commit()
    flash(f"Product '{product.name}' has been activated.", 'success')
    # Optional: Send Discord notification
    return redirect(url_for('products.my_products'))
