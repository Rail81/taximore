from datetime import datetime, timedelta
from ..models import db, Subscription, SubscriptionPlan, Payment
from flask import current_app
import logging

logger = logging.getLogger(__name__)

async def send_subscription_notification(driver_id, notification_type, **kwargs):
    """Send notification to driver about subscription status"""
    from ..services.notification import send_notification  # Avoid circular import
    
    templates = {
        'expiring_soon': 'Ваша подписка истекает через {days} дней. Продлите подписку, чтобы продолжить пользоваться сервисом.',
        'expired': 'Ваша подписка истекла. Для продолжения работы необходимо продлить подписку.',
        'auto_renewal_failed': 'Не удалось автоматически продлить подписку. Пожалуйста, проверьте способ оплаты.',
        'auto_renewal_success': 'Ваша подписка была автоматически продлена до {end_date}.'
    }
    
    message = templates[notification_type].format(**kwargs)
    await send_notification(driver_id, message)
    logger.info(f"Sent {notification_type} notification to driver {driver_id}")

async def check_subscription(driver_id):
    """Check if driver has active subscription"""
    subscription = Subscription.query.filter_by(
        driver_id=driver_id,
        status='active'
    ).first()
    
    if not subscription:
        return False
    
    # Check if subscription has expired
    if subscription.end_date <= datetime.utcnow():
        subscription.status = 'expired'
        db.session.commit()
        await send_subscription_notification(driver_id, 'expired')
        return False
    
    # Check if subscription is about to expire
    days_until_expiry = (subscription.end_date - datetime.utcnow()).days
    if days_until_expiry <= 3:
        await send_subscription_notification(
            driver_id, 
            'expiring_soon',
            days=days_until_expiry
        )
        
        # Try auto-renewal if enabled
        if subscription.auto_renew:
            await attempt_auto_renewal(subscription)
    
    return True

async def attempt_auto_renewal(subscription):
    """Attempt to automatically renew subscription"""
    from ..services.payment import create_payment
    
    try:
        # Get the current plan
        plan = SubscriptionPlan.query.get(subscription.plan_id)
        if not plan:
            logger.error(f"Plan {subscription.plan_id} not found for subscription {subscription.id}")
            return False
            
        # Create new payment
        payment_result = await create_payment(
            amount=plan.price,
            description=f"Автопродление подписки {plan.name}",
            payment_type=subscription.last_payment_method,
            subscription_id=subscription.id
        )
        
        if payment_result.get('status') == 'succeeded':
            # Update subscription dates
            subscription.start_date = subscription.end_date
            subscription.end_date = subscription.end_date + timedelta(days=plan.duration_days)
            db.session.commit()
            
            await send_subscription_notification(
                subscription.driver_id,
                'auto_renewal_success',
                end_date=subscription.end_date.strftime('%d.%m.%Y')
            )
            return True
        else:
            await send_subscription_notification(
                subscription.driver_id,
                'auto_renewal_failed'
            )
            return False
            
    except Exception as e:
        logger.error(f"Auto-renewal failed for subscription {subscription.id}: {str(e)}")
        await send_subscription_notification(
            subscription.driver_id,
            'auto_renewal_failed'
        )
        return False

async def create_subscription(driver_id, plan_id, payment_method='card'):
    """Create new subscription"""
    plan = SubscriptionPlan.query.get(plan_id)
    if not plan:
        raise ValueError("Invalid subscription plan")
    
    # Create payment
    payment = Payment(
        amount=plan.price,
        status='pending',
        payment_method=payment_method
    )
    db.session.add(payment)
    
    # Create subscription
    subscription = Subscription(
        driver_id=driver_id,
        plan_id=plan_id,
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=plan.duration_days),
        status='pending',
        auto_renew=True
    )
    db.session.add(subscription)
    
    try:
        db.session.commit()
        return subscription
    except Exception as e:
        logger.error(f"Error creating subscription: {str(e)}")
        db.session.rollback()
        raise

async def process_payment(payment_id, transaction_data):
    """Process payment for subscription"""
    payment = Payment.query.get(payment_id)
    if not payment:
        raise ValueError("Invalid payment ID")
    
    try:
        # Update payment status
        payment.status = 'completed'
        payment.transaction_id = transaction_data.get('transaction_id')
        
        # Activate subscription if payment is for subscription
        if payment.subscription_id:
            subscription = Subscription.query.get(payment.subscription_id)
            if subscription:
                subscription.status = 'active'
        
        db.session.commit()
        return True
    except Exception as e:
        logger.error(f"Error processing payment: {str(e)}")
        db.session.rollback()
        return False

async def cancel_subscription(subscription_id):
    """Cancel subscription"""
    subscription = Subscription.query.get(subscription_id)
    if not subscription:
        raise ValueError("Invalid subscription ID")
    
    subscription.status = 'cancelled'
    subscription.auto_renew = False
    
    try:
        db.session.commit()
        return True
    except Exception as e:
        logger.error(f"Error cancelling subscription: {str(e)}")
        db.session.rollback()
        return False

async def process_auto_renewals():
    """Process automatic subscription renewals"""
    # Find subscriptions due for renewal
    subscriptions = Subscription.query.filter(
        Subscription.status == 'active',
        Subscription.auto_renew == True,
        Subscription.end_date <= datetime.utcnow() + timedelta(days=1)
    ).all()
    
    for subscription in subscriptions:
        try:
            # Create new payment
            payment = Payment(
                subscription_id=subscription.id,
                amount=subscription.plan.price,
                status='pending',
                payment_method='auto'
            )
            db.session.add(payment)
            
            # Update subscription dates
            subscription.start_date = subscription.end_date
            subscription.end_date = subscription.end_date + timedelta(days=subscription.plan.duration_days)
            
            db.session.commit()
            
            # TODO: Process payment through payment system
            # TODO: Send notification to driver
            
        except Exception as e:
            logger.error(f"Error processing auto-renewal for subscription {subscription.id}: {str(e)}")
            db.session.rollback()
