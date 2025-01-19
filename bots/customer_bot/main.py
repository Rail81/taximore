import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import os
from dotenv import load_dotenv
import sys
sys.path.append('../..')
from backend.models import db, Customer, Order, FareRule
from backend.services.geo import calculate_route
from backend.services.pricing import calculate_fare

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    keyboard = [
        [KeyboardButton("🚖 Заказать такси", request_location=True)],
        [KeyboardButton("📜 История поездок"), KeyboardButton("⭐️ Оставить отзыв")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Добро пожаловать в TaxiMore! Чем могу помочь?",
        reply_markup=reply_markup
    )

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle received location"""
    location = update.message.location
    context.user_data['pickup_location'] = {
        'lat': location.latitude,
        'lon': location.longitude
    }
    
    await update.message.reply_text(
        "Отлично! Теперь укажите адрес назначения или отправьте локацию.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📍 Отправить локацию", callback_data="send_destination_location")
        ]])
    )

async def destination_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle destination address"""
    destination = update.message.text
    pickup_location = context.user_data.get('pickup_location')
    
    # Calculate route and fare
    route = await calculate_route(pickup_location, destination)
    fare = await calculate_fare(route)
    
    context.user_data['route'] = route
    context.user_data['fare'] = fare
    
    # Show car classes
    car_classes = await FareRule.query.filter_by(is_active=True).all()
    keyboard = []
    for car_class in car_classes:
        price = fare * car_class.price_multiplier
        keyboard.append([InlineKeyboardButton(
            f"{car_class.name} - {price}₽",
            callback_data=f"select_car_class_{car_class.id}"
        )])
    
    await update.message.reply_text(
        "Выберите класс автомобиля:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def car_class_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle car class selection"""
    query = update.callback_query
    car_class_id = query.data.split('_')[-1]
    
    # Create order
    order = Order(
        customer_id=context.user_data['customer'].id,
        pickup_location_lat=context.user_data['pickup_location']['lat'],
        pickup_location_lon=context.user_data['pickup_location']['lon'],
        dropoff_location_lat=context.user_data['route']['destination']['lat'],
        dropoff_location_lon=context.user_data['route']['destination']['lon'],
        estimated_price=context.user_data['fare'],
        car_class=car_class_id,
        status='pending'
    )
    db.session.add(order)
    db.session.commit()
    
    await query.edit_message_text(
        "Заказ создан! Ищем водителя...\n"
        f"Номер заказа: {order.id}\n"
        f"Примерная стоимость: {order.estimated_price}₽"
    )

async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle history request"""
    customer = context.user_data.get('customer')
    if not customer:
        await update.message.reply_text("Пожалуйста, сначала закажите такси.")
        return
    
    orders = Order.query.filter_by(customer_id=customer.id).order_by(Order.created_at.desc()).limit(5).all()
    
    if not orders:
        await update.message.reply_text("У вас пока нет истории поездок.")
        return
    
    history_text = "Ваши последние поездки:\n\n"
    for order in orders:
        history_text += (
            f"📍 {order.pickup_address} → {order.dropoff_address}\n"
            f"💰 {order.final_price}₽\n"
            f"📅 {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"Status: {order.status}\n\n"
        )
    
    await update.message.reply_text(history_text)

def main():
    """Start the bot"""
    # Create application
    application = Application.builder().token(os.getenv('CUSTOMER_BOT_TOKEN')).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.LOCATION, location_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, destination_handler))
    application.add_handler(CallbackQueryHandler(car_class_handler, pattern="^select_car_class_"))
    application.add_handler(MessageHandler(filters.Regex("^📜 История поездок$"), history_handler))
    
    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()
