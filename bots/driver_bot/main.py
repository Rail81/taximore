import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import os
from dotenv import load_dotenv
import sys
sys.path.append('../..')
from backend.models import db, Driver, Order, Subscription, SubscriptionPlan
from backend.services.subscription import check_subscription
from backend.services.geo import calculate_route
from datetime import datetime

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def check_active_subscription(driver_id: int) -> bool:
    """Check if driver has active subscription"""
    subscription = Subscription.query.filter_by(
        driver_id=driver_id,
        status='active'
    ).first()
    return bool(subscription and subscription.end_date > datetime.utcnow())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    driver = Driver.query.filter_by(telegram_id=str(update.effective_user.id)).first()
    
    if not driver:
        await update.message.reply_text(
            "Для начала работы необходимо зарегистрироваться в системе. "
            "Обратитесь к администратору."
        )
        return
    
    context.user_data['driver'] = driver
    
    if not await check_active_subscription(driver.id):
        # Show subscription plans
        plans = SubscriptionPlan.query.filter_by(is_active=True).all()
        keyboard = []
        for plan in plans:
            keyboard.append([InlineKeyboardButton(
                f"{plan.name} - {plan.price}₽/{plan.duration_days} дней",
                callback_data=f"subscribe_{plan.id}"
            )])
        
        await update.message.reply_text(
            "У вас нет активной подписки. Выберите тарифный план:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    keyboard = [
        [KeyboardButton("🚗 Начать смену"), KeyboardButton("🏁 Закончить смену")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("💰 Подписка")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Добро пожаловать! Выберите действие:",
        reply_markup=reply_markup
    )

async def start_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle shift start"""
    driver = context.user_data.get('driver')
    if not driver:
        await update.message.reply_text("Необходимо перезапустить бота командой /start")
        return
    
    if not await check_active_subscription(driver.id):
        await update.message.reply_text("Необходимо оформить подписку для работы.")
        return
    
    driver.status = 'online'
    db.session.commit()
    
    keyboard = [
        [KeyboardButton("📍 Отправить локацию", request_location=True)],
        [KeyboardButton("⏸ Перерыв"), KeyboardButton("🏁 Закончить смену")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Смена начата! Отправьте свою локацию для получения заказов.",
        reply_markup=reply_markup
    )

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle received location"""
    driver = context.user_data.get('driver')
    if not driver or driver.status != 'online':
        return
    
    location = update.message.location
    driver.current_location_lat = location.latitude
    driver.current_location_lon = location.longitude
    db.session.commit()
    
    # Check for nearby orders
    orders = Order.query.filter_by(
        status='pending',
        car_class=driver.car_class
    ).all()
    
    if not orders:
        await update.message.reply_text("В данный момент нет доступных заказов поблизости.")
        return
    
    # Show available orders
    for order in orders:
        route = await calculate_route(
            {'lat': driver.current_location_lat, 'lon': driver.current_location_lon},
            {'lat': order.pickup_location_lat, 'lon': order.pickup_location_lon}
        )
        
        keyboard = [[InlineKeyboardButton(
            "✅ Принять заказ",
            callback_data=f"accept_order_{order.id}"
        )]]
        
        await update.message.reply_text(
            f"Новый заказ #{order.id}\n"
            f"От: {order.pickup_address}\n"
            f"До: {order.dropoff_address}\n"
            f"Расстояние до клиента: {route['distance']}км\n"
            f"Стоимость: {order.estimated_price}₽",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def accept_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle order acceptance"""
    query = update.callback_query
    order_id = int(query.data.split('_')[-1])
    driver = context.user_data.get('driver')
    
    order = Order.query.get(order_id)
    if not order or order.status != 'pending':
        await query.edit_message_text("Заказ уже не доступен.")
        return
    
    order.driver_id = driver.id
    order.status = 'accepted'
    driver.status = 'busy'
    db.session.commit()
    
    keyboard = [[InlineKeyboardButton(
        "🚗 Начать поездку",
        callback_data=f"start_ride_{order.id}"
    )]]
    
    await query.edit_message_text(
        f"Заказ #{order.id} принят!\n"
        f"Следуйте к клиенту: {order.pickup_address}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def main():
    """Start the bot"""
    # Create application
    application = Application.builder().token(os.getenv('DRIVER_BOT_TOKEN')).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex("^🚗 Начать смену$"), start_shift))
    application.add_handler(MessageHandler(filters.LOCATION, location_handler))
    application.add_handler(CallbackQueryHandler(accept_order, pattern="^accept_order_"))
    
    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()
