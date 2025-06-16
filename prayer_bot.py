import os
import logging
from datetime import datetime
import requests
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from dotenv import load_dotenv
from geopy.geocoders import Nominatim

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Debug: Print token (first 4 chars for security)
token = os.getenv('TELEGRAM_TOKEN')
if token:
    logger.info(f"Bot token loaded successfully. First 4 chars: {token[:4]}")
else:
    logger.error("No TELEGRAM_TOKEN found in environment variables!")

# States for conversation handler
LOCATION = 0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send a message when the command /start is issued."""
    logger.info(f"Start command received from user {update.effective_user.id}")
    keyboard = [[{"text": "Share Location", "request_location": True}]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    await update.message.reply_text(
        'Welcome to Prayer Times Bot! 🌙\n\n'
        'I will send you prayer times based on your location.\n'
        'You can either:\n'
        '1. Share your current location using the button below\n'
        '2. Type any city name (e.g., "New York", "London", "Tokyo")\n'
        '3. Type city and country (e.g., "Paris, France", "Dubai, UAE")',
        reply_markup=reply_markup
    )
    return LOCATION

async def get_prayer_times(latitude: float, longitude: float) -> dict:
    """Get prayer times from the API."""
    url = f"http://api.aladhan.com/v1/timings/{datetime.now().timestamp()}"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "method": 2  # Islamic Society of North America (ISNA) method
    }
    
    try:
        logger.info(f"Fetching prayer times for coordinates: {latitude}, {longitude}")
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data["data"]["timings"]
    except Exception as e:
        logger.error(f"Error fetching prayer times: {e}")
        return None

async def get_location_coordinates(location_name: str) -> tuple:
    """Get coordinates for a location name."""
    try:
        geolocator = Nominatim(user_agent="prayer_bot")
        location = geolocator.geocode(location_name)
        if location:
            return location.latitude, location.longitude, location.address
        return None, None, None
    except Exception as e:
        logger.error(f"Error getting coordinates: {e}")
        return None, None, None

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the location message."""
    if update.message.location:
        # Handle shared location
        location = update.message.location
        latitude, longitude = location.latitude, location.longitude
        geolocator = Nominatim(user_agent="prayer_bot")
        location_info = geolocator.reverse(f"{latitude}, {longitude}")
        city = location_info.raw.get('address', {}).get('city', 'Unknown City')
        full_address = location_info.address
    else:
        # Handle text input
        text = update.message.text.strip()
        if not text:
            await update.message.reply_text("Please enter a valid location name or share your location.")
            return LOCATION
            
        latitude, longitude, full_address = await get_location_coordinates(text)
        if not latitude or not longitude:
            await update.message.reply_text(
                "Sorry, I couldn't find that location. Please try:\n"
                "1. A more specific location (e.g., 'New York, USA' instead of just 'New York')\n"
                "2. Share your current location using the button"
            )
            return LOCATION
        city = text

    # Get prayer times
    prayer_times = await get_prayer_times(latitude, longitude)
    
    if prayer_times:
        message = f"Prayer Times for {full_address or city}:\n\n"
        for prayer, time in prayer_times.items():
            if prayer in ['Fajr', 'Sunrise', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']:
                message += f"{prayer}: {time}\n"
        
        await update.message.reply_text(message, reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text("Sorry, I couldn't fetch the prayer times. Please try again later.")
    
    # Ask for location again
    keyboard = [[{"text": "Share Location", "request_location": True}]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text(
        "To get prayer times for another location:\n"
        "1. Type any city name (e.g., 'New York', 'London')\n"
        "2. Type city and country (e.g., 'Paris, France')\n"
        "3. Share your current location using the button",
        reply_markup=reply_markup
    )
    return LOCATION

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    logger.info(f"Help command received from user {update.effective_user.id}")
    await update.message.reply_text(
        'Available commands:\n'
        '/start - Start the bot and enter a location\n'
        '/help - Show this help message\n\n'
        'You can get prayer times by:\n'
        '1. Typing any city name (e.g., "New York", "London")\n'
        '2. Typing city and country (e.g., "Paris, France")\n'
        '3. Sharing your current location'
    )

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()

    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LOCATION: [
                MessageHandler(filters.LOCATION, location_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, location_handler)
            ],
        },
        fallbacks=[CommandHandler('help', help_command)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', help_command))

    logger.info("Bot is starting...")
    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 