import requests
from flask import current_app, url_for # Added url_for for potential future use in embeds
from datetime import datetime # Added datetime for fallback timestamps

def send_discord_webhook_message(webhook_url, content=None, embeds=None, username=None, avatar_url=None):
    """
    Sends a message to a Discord webhook.
    Args:
        webhook_url (str): The URL of the Discord webhook.
        content (str, optional): The main text content of the message.
        embeds (list, optional): A list of Discord embed objects (dicts).
        username (str, optional): Override the default webhook username.
        avatar_url (str, optional): Override the default webhook avatar.
    Returns:
        bool: True if the message was sent successfully (status 2xx), False otherwise.
    """
    if not webhook_url:
        current_app.logger.error("Discord webhook URL is not configured.")
        return False

    payload = {}
    if content:
        payload['content'] = content
    if embeds:
        payload['embeds'] = embeds
    if username:
        payload['username'] = username
    if avatar_url:
        payload['avatar_url'] = avatar_url

    if not payload.get('content') and not payload.get('embeds'):
        current_app.logger.error("Discord message must have content or embeds.")
        return False

    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        current_app.logger.info(f"Discord webhook message sent successfully to {webhook_url[:50]}...")
        return True
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Error sending Discord webhook message to {webhook_url[:50]}...: {e}")
        if hasattr(e, 'response') and e.response is not None:
            current_app.logger.error(f"Discord webhook response content: {e.response.text}")
        return False

def create_product_embed(product, title_prefix=""):
    """Helper to create a Discord embed for a product."""
    # Ensure product.seller is loaded or available.
    # If product.seller is a relationship, it should be loaded before calling this.
    # For 'New Product Listed', product.seller is current_user.
    seller_username = "N/A"
    if product.seller:
        seller_username = product.seller.username
    elif hasattr(product, 'user_id') and product.user_id == current_user.id: # Fallback if relationship not loaded
        seller_username = current_user.username


    embed = {
        "title": f"{title_prefix}{product.name}",
        "description": product.description[:200] + "..." if product.description and len(product.description) > 200 else product.description,
        "color": 0x00AAFF, # Blue
        "fields": [
            {"name": "Price", "value": f"${product.price:.2f}", "inline": True},
            {"name": "Quantity Available", "value": str(product.quantity_available), "inline": True},
            {"name": "Seller", "value": seller_username, "inline": True}
        ],
        # Example of adding a URL to the product page if it exists
        # "url": url_for('products.view_product', product_id=product.id, _external=True),
        "footer": {"text": f"Product ID: {product.id}"},
        "timestamp": (product.date_posted.isoformat() if product.date_posted else datetime.utcnow().isoformat())
    }
    return embed

def create_sale_embed(product, buyer, seller, order, quantity_sold=1):
    """Helper to create a Discord embed for a product sale."""
    embed = {
        "title": f"🎉 Product Sold: {product.name}",
        "description": f"**{product.name}** has been purchased by **{buyer.username}** from **{seller.username}**.",
        "color": 0x00FF00, # Green for sale
        "fields": [
            {"name": "Product Name", "value": product.name, "inline": True},
            {"name": "Sale Price", "value": f"${order.total_amount:.2f}", "inline": True}, # Use order total amount
            {"name": "Quantity Sold", "value": str(quantity_sold), "inline": True},
            {"name": "Buyer", "value": buyer.username, "inline": True},
            {"name": "Seller", "value": seller.username, "inline": True},
            {"name": "Stock Remaining", "value": str(product.quantity_available), "inline": True},
        ],
        "footer": {"text": f"Order ID: {order.id} | Product ID: {product.id}"},
        "timestamp": (order.order_date.isoformat() if order.order_date else datetime.utcnow().isoformat())
    }
    return embed
