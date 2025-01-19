from yookassa import Configuration, Payment as YooPayment
from flask import current_app, url_for
from ..models import db, Payment, Subscription
import uuid
import logging

logger = logging.getLogger(__name__)

def init_payment_system():
    """Initialize YooKassa configuration"""
    Configuration.account_id = current_app.config['YOOKASSA_SHOP_ID']
    Configuration.secret_key = current_app.config['YOOKASSA_SECRET_KEY']

async def create_payment(amount, description, payment_type='bank_card', subscription_id=None, order_id=None):
    """Create payment in YooKassa"""
    try:
        idempotence_key = str(uuid.uuid4())
        
        payment_data = {
            "amount": {
                "value": str(amount),
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": url_for('payment.callback', _external=True)
            },
            "capture": True,
            "description": description
        }
        
        # Create payment in YooKassa
        yoo_payment = YooPayment.create(payment_data, idempotence_key)
        
        # Create payment record in database
        payment = Payment(
            amount=amount,
            status='pending',
            payment_method=payment_type,
            transaction_id=yoo_payment.id
        )
        
        if subscription_id:
            payment.subscription_id = subscription_id
        if order_id:
            payment.order_id = order_id
        
        db.session.add(payment)
        db.session.commit()
        
        return {
            'payment_id': payment.id,
            'confirmation_url': yoo_payment.confirmation.confirmation_url
        }
        
    except Exception as e:
        logger.error(f"Error creating payment: {str(e)}")
        db.session.rollback()
        raise

async def process_payment_callback(payment_data):
    """Process payment callback from YooKassa"""
    try:
        payment = Payment.query.filter_by(transaction_id=payment_data['object']['id']).first()
        if not payment:
            logger.error(f"Payment not found: {payment_data['object']['id']}")
            return False
        
        # Update payment status
        payment.status = payment_data['object']['status']
        
        if payment.status == 'succeeded':
            # If payment is for subscription
            if payment.subscription_id:
                subscription = Subscription.query.get(payment.subscription_id)
                if subscription:
                    subscription.status = 'active'
            
            # If payment is for order
            if payment.order_id:
                order = Order.query.get(payment.order_id)
                if order:
                    order.payment_status = 'paid'
        
        db.session.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error processing payment callback: {str(e)}")
        db.session.rollback()
        return False

async def refund_payment(payment_id, amount=None, reason=None):
    """Refund payment"""
    try:
        payment = Payment.query.get(payment_id)
        if not payment or payment.status != 'succeeded':
            raise ValueError("Invalid payment or payment not succeeded")
        
        idempotence_key = str(uuid.uuid4())
        
        refund_data = {
            "amount": {
                "value": str(amount if amount else payment.amount),
                "currency": "RUB"
            },
            "payment_id": payment.transaction_id
        }
        
        if reason:
            refund_data["description"] = reason
        
        # Create refund in YooKassa
        refund = Refund.create(refund_data, idempotence_key)
        
        # Update payment status
        payment.status = 'refunded'
        db.session.commit()
        
        return True
        
    except Exception as e:
        logger.error(f"Error refunding payment: {str(e)}")
        db.session.rollback()
        return False
