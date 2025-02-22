import json
import logging
import os
import asyncio
import datetime
import traceback
import openai
from pydub import AudioSegment
from pydub.utils import make_chunks
from telegram import Update, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, CallbackContext


def define_logging(script_name):
    # set up logging to file - see previous section for more details
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
        datefmt="%d-%m-%Y %H:%M",
        filename=f"{script_name}" + ".log",
        filemode="w",
    )
    # define a Handler which writes INFO messages or higher to the sys.stderr
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    # set a format which is simpler for console use
    formatter = logging.Formatter("%(name)-12s: %(levelname)-8s %(message)s")
    # tell the handler to use this format
    console.setFormatter(formatter)
    # add the handler to the root logger
    logging.getLogger("").addHandler(console)
    # Now, we can log to the root logger, or any other logger. First the root...
    logging.info("logging defined")

LOCK = asyncio.Lock()
AUTHORIZED_USERS = []
USERS_CONTEXT = {}
CLIENT = None # is it thread safe? not sure

async def add_user_context(user_id: str, key: str, value: str):
    await LOCK.acquire()
    try:
        if user_id not in USERS_CONTEXT:
            USERS_CONTEXT[user_id] = {}
        USERS_CONTEXT[user_id][key] = value
    finally:
        LOCK.release()

async def get_user_context(user_id: str, key: str, default=None):
    await LOCK.acquire()
    try:
        if user_id in USERS_CONTEXT:
            return USERS_CONTEXT[user_id].get(key, default)
    finally:
        LOCK.release()
        return None

def is_authorized_user(user_id: str) -> bool:
    return user_id in AUTHORIZED_USERS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    is_authorized = "authorized" if is_authorized_user(str(update.message.from_user.id)) else "not authorized"
    response_text = f"Hi! I am your bot. Your telegram Id is: {update.message.from_user.id}. You are {is_authorized}."
    response_text += "\n\nSend me a voice message and I will transcribe it for you. Or send me a text message and I will respond to it. "
    response_text += "\nBeware, all your messages are logged and Skynet is watching you."
    await update.message.reply_text(response_text)

async def help_command(update: Update, context: CallbackContext) -> None:
    help_text = (
        "🤖 *Available Commands:*\n"
        "/start - Start the bot\n"
        "/help - Show this message\n"
        "/model <name> Choose model"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

def process_audio(audio_path: str):
    # Load the audio file format oga
    audio = AudioSegment.from_file(audio_path)

    # Split into chunks (e.g., 60 seconds each)
    chunk_length_ms = 60000  # 60 seconds
    chunks = make_chunks(audio, chunk_length_ms)

    # Process each chunk
    full_text = ""
    for i, chunk in enumerate(chunks):
        chunk_path = f"chunk_{i}.mp3"
        chunk.export(chunk_path, format="mp3")
        audio_file= open(chunk_path, "rb")
        transcription = CLIENT.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file
        )
        full_text += " " + transcription.text

    return full_text

async def check_authorized(update: Update):
    if not is_authorized_user(str(update.message.from_user.id)):
        await update.message.reply_text("You are not authorized to use this bot.")
        return False
    return True

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_authorized(update):
        return

    file = await context.bot.get_file(update.message.voice.file_id)
    file_path = await file.download_to_drive()

    print(f"Received voice message: {file_path}")

    try:
        text = process_audio(file_path)
        print(f"Transcribed text: {text}")
        await update.message.reply_text(text)
    except:
        traceback.print_exc()

        await update.message.reply_text("Could not understand the audio.")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE, txt_message: str = ''):
    if not await check_authorized(update):
        return
    
    if not txt_message:
        txt_message = update.message.text

    model = await get_user_context(update.message.from_user.id, "model", "gpt-3.5-turbo")

    logging.info(f"Received command: {txt_message}")
    response = CLIENT.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": txt_message}
        ]
    )

    logging.info(f"Received gpt response: {response.choices[0].message.content}")
    await update.message.reply_text(response.choices[0].message.content)

async def model_choise(update: Update, context: CallbackContext) -> None:
    if not await check_authorized(update):
        return
    
    available_models = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o", "o1-mini"]
    model_descriptions = {
        "gpt-3.5-turbo": "🍚 gpt-3.5-turbo",
        "gpt-4": "🍕 gpt-4",
        "gpt-4-turbo": "🍔 gpt-4-turbo",
        "gpt-4o": "🍣 gpt-4o",
        "o1-mini": "🥩 o1-mini"
    }

    def validate_model_choice(model_choice: str) -> bool:
        return model_choice in available_models
    
    # if model is provided with the command argument, set it
    if len(context.args) > 0:
        model_choice = context.args[0]
        logging.info(f"Model choice: {model_choice}")
        if not validate_model_choice(model_choice):
            await update.message.reply_text(f"❌ Invalid model choice: {model_choice}. Please choose from: {available_models}")
            return
        
        await add_user_context(update.message.from_user.id, "model", model_choice)
        await update.message.reply_text(f"✅ Model confirmed: {model_choice}!")
        return
    
    keyboard = [
        [InlineKeyboardButton(model_descriptions[model], callback_data=f"model_{model}") for model in available_models]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("What model would you like to use?", reply_markup=reply_markup)

async def on_button_clicked(update: Update, context: CallbackContext) -> None:
    logging.info(f"Button clicked: {update.callback_query.data}")
    query = update.callback_query
    await query.answer()
    
    model_choice = query.data.split("_")[1]  # Extract choice from callback_data
    await add_user_context(query.from_user.id, "model", model_choice)
    await query.edit_message_text(f"✅ Model confirmed: {model_choice}!")


def main():
    global CLIENT
    global AUTHORIZED_USERS

    script_dir = os.path.dirname(os.path.abspath(__file__))
    auth_users_path = os.path.join(script_dir, "authorized_users.json") 

    try:
        with open(auth_users_path, "r") as auth_users_file:
            AUTHORIZED_USERS = json.load(auth_users_file)
            print("✅ Authorized users loaded successfully!")
    except FileNotFoundError:
        print(f"❌ Error: {auth_users_path} not found!")
    except json.JSONDecodeError:
        print(f"❌ Error: Invalid JSON in {auth_users_path}!")

    openai_api_key = os.getenv('OPENAI_API_KEY')
    openai.api_key = openai_api_key
    CLIENT = openai.Client()

    telegram_bot_key = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not telegram_bot_key or not openai_api_key:
        raise ValueError("Please set the `TELEGRAM_BOT_TOKEN` and `OPENAI_API_KEY` environment variables.")

    application = ApplicationBuilder().token(telegram_bot_key).build()

    logging.info("Bot started. Authorized users: " + str(AUTHORIZED_USERS))

    try:
        # Handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("model", model_choise))
        application.add_handler(CallbackQueryHandler(on_button_clicked))
        application.add_handler(MessageHandler(filters.VOICE, handle_voice))
        application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_message))

        # Start the Bot
        application.run_polling()
    finally:
        application.shutdown()

if __name__ == '__main__':
    date = datetime.datetime.today().strftime('%d-%m-%Y-%H-%M-%S')
    define_logging("bot_" + date)
    main()