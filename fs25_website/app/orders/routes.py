from flask import render_template, redirect, url_for, flash, request, current_app # Added current_app
from flask_login import login_required, current_user
from . import bp
from app.models import Product, User, ProductOrder, ProductOrderItem, Transaction
from app import db
from sqlalchemy import exc
from app.discord_utils import send_discord_webhook_message, create_sale_embed # Import Discord utils

@bp.route('/confirm_purchase/<int:product_id>', methods=['GET'])
@login_required
def confirm_purchase(product_id):
    product = Product.query.get_or_404(product_id)
    if not product.is_active:
        flash('This product is no longer available.', 'warning')
        return redirect(url_for('products.list_products'))
    if product.quantity_available <= 0:
        flash('This product is out of stock.', 'warning')
        return redirect(url_for('products.list_products'))
    if product.user_id == current_user.id:
        flash('You cannot purchase your own product.', 'warning')
        return redirect(url_for('products.list_products'))

    return render_template('orders/confirm_purchase.html', product=product, title="Confirm Your Purchase")

@bp.route('/execute_purchase/<int:product_id>', methods=['POST'])
@login_required
def execute_purchase(product_id):
    product = Product.query.get_or_404(product_id)
    # Ensure seller relationship is loaded for the notification embed later
    # One way is to use joinedload if this becomes an issue, or access product.seller early.
    # For now, User.query.get() is explicit.
    seller = User.query.get(product.user_id)

    if not seller:
        flash('Seller not found for this product. This should not happen.', 'danger')
        current_app.logger.error(f"Critical: Seller not found for product ID {product.id} during purchase by user {current_user.id}")
        return redirect(url_for('products.list_products'))

    # --- Pre-condition checks ---
    if not product.is_active:
        flash('This product is no longer available.', 'warning')
        return redirect(url_for('products.list_products'))
    if product.quantity_available <= 0:
        flash('This product is out of stock.', 'warning')
        return redirect(url_for('products.list_products'))
    if product.user_id == current_user.id: # Buyer is the seller
        flash('You cannot purchase your own product.', 'warning')
        return redirect(url_for('products.list_products'))
    if current_user.balance < product.price:
        flash(f'Insufficient funds. You need ${product.price:.2f}, but you only have ${current_user.balance:.2f}.', 'danger')
        return redirect(url_for('orders.confirm_purchase', product_id=product.id))

    try:
        # --- Create Order and OrderItem ---
        order = ProductOrder(
            buyer_user_id=current_user.id,
            total_amount=product.price
        )
        db.session.add(order)
        db.session.flush() # Get order.id for foreign keys and notifications

        order_item = ProductOrderItem(
            product_order_id=order.id,
            product_id=product.id,
            quantity_ordered=1,
            price_at_purchase=product.price
        )
        db.session.add(order_item)

        # --- Update Product Quantity ---
        product.quantity_available -= 1
        # if product.quantity_available == 0:
        # product.is_active = False # Optional: auto-deactivate if out of stock

        # --- Update Balances ---
        current_user.balance -= product.price
        seller.balance += product.price

        # --- Create Transactions ---
        buyer_transaction = Transaction(
            user_id=current_user.id, type='product_purchase_debit', amount=-product.price,
            description=f'Purchased: {product.name} (Order: {order.id})', related_product_order_id=order.id
        )
        seller_transaction = Transaction(
            user_id=seller.id, type='product_sale_credit', amount=product.price,
            description=f'Sold: {product.name} (Order: {order.id})', related_product_order_id=order.id
        )
        db.session.add_all([buyer_transaction, seller_transaction])

        db.session.commit() # All database changes are committed here

        flash(f'Successfully purchased {product.name}!', 'success')

        # Send Discord notification for sale
        webhook_url = current_app.config.get('DISCORD_WEBHOOK_URL_SALES')
        if webhook_url:
            try:
                # Product object has updated quantity_available here.
                # current_user is the buyer. Seller object is 'seller'. Order object is 'order'.
                embed = create_sale_embed(product, current_user, seller, order, quantity_sold=1)
                send_discord_webhook_message(webhook_url, embeds=[embed], username="E-commerce Bot (Sales)")
            except Exception as e:
                current_app.logger.error(f"Error sending Discord sale notification: {e}")
        else:
            current_app.logger.warning("DISCORD_WEBHOOK_URL_SALES not set. Skipping notification.")

        return redirect(url_for('products.list_products')) # Or an order history page

    except exc.SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"SQLAlchemyError during purchase of product {product_id} by user {current_user.id}: {e}")
        flash('A database error occurred while processing your order. Please try again.', 'danger')
        return redirect(url_for('orders.confirm_purchase', product_id=product.id))
    except Exception as e: # Catch any other unexpected errors
        db.session.rollback()
        current_app.logger.error(f"Unexpected error during purchase of product {product_id} by user {current_user.id}: {e}")
        flash('An unexpected error occurred while processing your order. Please try again.', 'danger')
        return redirect(url_for('orders.confirm_purchase', product_id=product.id))
