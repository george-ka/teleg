import json
import logging
import os
import asyncio
import traceback
import openai
from pydub import AudioSegment
from pydub.utils import make_chunks
from telegram import Update, ForceReply
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

AUTHORIZED_USERS = [] # Replace with actual Telegram user IDs
AUTHORIZED_USERS = json.loads("authorized_users.json")
openai_api_key = os.getenv('OPENAI_API_KEY')
openai.api_key = openai_api_key
client = openai.Client()

def is_authorized_user(user_id: str) -> bool:
    return user_id in AUTHORIZED_USERS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    is_authorized = "authorized" if is_authorized_user(str(update.message.from_user.id)) else "not authorized"
    response_text = f"Hi! I am your bot. Your telegram Id is: {update.message.from_user.id}. You are {is_authorized}."
    response_text += "\n\nSend me an audio message and I will transcribe it for you. Or send me a message and I will respond to it."
    await update.message.reply_text(response_text)

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
        transcription = client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file
        )
        full_text += " " + transcription.text

    return full_text


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized_user(str(update.message.from_user.id)):
        await update.message.reply_text("You are not authorized to use this bot. " + str(update.message.from_user.id))
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

async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE, command: str = ''):
    if not is_authorized_user(str(update.message.from_user.id)):
        await update.message.reply_text("You are not authorized to use this bot.")
        return
    
    if not command:
        command = update.message.text

    print(f"Received command: {command}")
    # send a command to the OpenAI API
    response = client.chat.completions.create(
        model="gpt-4",  # or specify the exact model you are using
        #model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": command}
        ]
    )

    print(f"Received gpt response: {response.choices[0].message.content}")
    await update.message.reply_text(response.choices[0].message.content)

def main():
    telegram_bot_key = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not telegram_bot_key or not openai_api_key:
        raise ValueError("Please set the `TELEGRAM_BOT_TOKEN` and `OPENAI_API_KEY` environment variables.")

    application = ApplicationBuilder().token(telegram_bot_key).build()

    try:
        # Handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.VOICE, handle_voice))
        application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_command))

        # Start the Bot
        application.run_polling()
    finally:
        application.shutdown()

if __name__ == '__main__':
    main()