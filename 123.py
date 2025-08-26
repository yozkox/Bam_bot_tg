import asyncio
from aiogram import Bot

API_TOKEN = "8322452158:AAEozxy0qOBLILevYtTWQ4aER7LFA5_7s0Q"
bot = Bot(token=API_TOKEN)

async def main():
    # Попробуем отправить сообщение в канал
    # Используем @username канала
    msg = await bot.send_message(chat_id="@my_channel_username", text="Привет! Проверка ID")
    print("Chat ID канала:", msg.chat.id)

if __name__ == "__main__":
    asyncio.run(main())
