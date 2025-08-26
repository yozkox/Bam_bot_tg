import asyncio
import logging
import json
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
import os
from aiogram.types import BotCommand

# ------------------- Настройки -------------------
API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_RELEASE_ID = int(os.getenv("CHANNEL_RELEASE_ID"))
CHANNEL_RESERVE_ID = int(os.getenv("CHANNEL_RESERVE_ID"))

TEMPLATES_FILE = "templates.json"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

@dp.message(Command("help"))
async def show_help(message: Message):
    help_text = (
        "Доступні команди бота:\n\n"
        "/templates - Меню шаблонів (створити або змінити шаблон)\n"
        "/help - Показати цей список команд\n\n"
        "Щоб відправити відео:\n"
        "1. Надішліть відео боту\n"
        "2. Виберіть серіал\n"
        "3. Введіть номер серії\n"
        "Бот автоматично відправить серію в канали."
    )
    await message.answer(help_text)


# ------------------- FSM состояния -------------------
class UploadStates(StatesGroup):
    waiting_video = State()
    waiting_series_choice = State()
    waiting_episode_number = State()

class TemplateStates(StatesGroup):
    waiting_name = State()
    waiting_release_text = State()
    waiting_reserve_text = State()
    editing_choice = State()  # для изменения существующего шаблона

# ------------------- Загрузка шаблонов -------------------
try:
    with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
        SERIES_TEMPLATES = json.load(f)
except FileNotFoundError:
    SERIES_TEMPLATES = {}

# ------------------- Главное меню шаблонов -------------------
def main_template_keyboard():
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Створити шаблон", callback_data="create_template")],
            [InlineKeyboardButton(text="Змінити шаблон", callback_data="edit_template")]
        ]
    )
    return kb

# ------------------- Клавиатура для выбора сериала -------------------
def series_keyboard():
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"series:{name}")]
            for name in SERIES_TEMPLATES.keys()
        ]
    )
    return kb

# ------------------- Стартовое меню -------------------
@dp.message(Command("templates"))
async def show_template_menu(message: Message):
    await message.answer("Виберіть дію:", reply_markup=main_template_keyboard())

# ------------------- Создание нового шаблона -------------------
@dp.callback_query(F.data == "create_template")
async def create_template(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введіть назву нового серіалу:")
    await state.set_state(TemplateStates.waiting_name)
    await callback.answer()

@dp.message(TemplateStates.waiting_name)
async def template_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введіть текст для релізного поста (використайте {episode} для номера серії):")
    await state.set_state(TemplateStates.waiting_release_text)

@dp.message(TemplateStates.waiting_release_text)
async def template_release(message: Message, state: FSMContext):
    await state.update_data(release_text=message.text)
    await message.answer("Введіть текст для резервного поста (використайте {episode} для номера серії):")
    await state.set_state(TemplateStates.waiting_reserve_text)

@dp.message(TemplateStates.waiting_reserve_text)
async def template_reserve(message: Message, state: FSMContext):
    data = await state.get_data()
    name = data["name"]
    release_text = data["release_text"]
    reserve_text = message.text

    SERIES_TEMPLATES[name] = {
        "release": release_text,
        "reserve": reserve_text
    }

    with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
        json.dump(SERIES_TEMPLATES, f, ensure_ascii=False, indent=4)

    await message.answer(f"✅ Шаблон для серіалу '{name}' збережено!")
    await state.clear()

# ------------------- Изменение существующего шаблона -------------------
@dp.callback_query(F.data == "edit_template")
async def edit_template(callback: CallbackQuery, state: FSMContext):
    if not SERIES_TEMPLATES:
        await callback.message.answer("Немає жодного шаблону для редагування.")
        await callback.answer()
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"edit:{name}")]
            for name in SERIES_TEMPLATES.keys()
        ]
    )
    await callback.message.answer("Оберіть шаблон для редагування:", reply_markup=kb)
    await state.set_state(TemplateStates.editing_choice)
    await callback.answer()

@dp.callback_query(F.data.startswith("edit:"))
async def edit_selected_template(callback: CallbackQuery, state: FSMContext):
    series_name = callback.data.split("edit:")[1]
    await state.update_data(name=series_name)
    await callback.message.answer(
        f"Редагуємо шаблон '{series_name}'.\nВведіть новий текст для релізного поста (або надішліть старий, щоб залишити без змін):"
    )
    await state.set_state(TemplateStates.waiting_release_text)
    await callback.answer()

# ------------------- Обработка видео -------------------
@dp.message(F.video)
async def handle_video(message: Message, state: FSMContext):
    await state.update_data(video_id=message.video.file_id)
    if SERIES_TEMPLATES:
        await message.answer("Виберіть серіал:", reply_markup=series_keyboard())
        await state.set_state(UploadStates.waiting_series_choice)
    else:
        await message.answer("Поки немає жодного шаблону серіалу. Створіть його через /templates")

# ------------------- Обработка выбора сериала -------------------
@dp.callback_query(F.data.startswith("series:"))
async def choose_series(callback: CallbackQuery, state: FSMContext):
    series_name = callback.data.split("series:")[1]
    await state.update_data(series_name=series_name)
    await callback.message.edit_text(f"Серіал обрано: {series_name}\nВведіть номер серії (наприклад: 25)")
    await state.set_state(UploadStates.waiting_episode_number)
    await callback.answer()

# ------------------- Получение номера серии -------------------
@dp.message(UploadStates.waiting_episode_number)
async def get_episode(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введіть тільки номер серії (наприклад: 25)")
        return

    episode_number = message.text
    data = await state.get_data()
    video_id = data["video_id"]
    series_name = data["series_name"]

    release_caption = SERIES_TEMPLATES[series_name]["release"].format(episode=episode_number)
    reserve_caption = SERIES_TEMPLATES[series_name]["reserve"].format(episode=episode_number)

    await bot.send_video(chat_id=CHANNEL_RELEASE_ID, video=video_id, caption=release_caption, parse_mode="HTML")
    await bot.send_video(chat_id=CHANNEL_RESERVE_ID, video=video_id, caption=reserve_caption, parse_mode="HTML")

    await message.answer(f"✅ Серія {episode_number} серіалу '{series_name}' відправлена в канали")
    await state.clear()
    
async def set_commands():
    commands = [
        BotCommand(command="/templates", description="Меню шаблонів"),
        BotCommand(command="/help", description="Список команд")
    ]
    await bot.set_my_commands(commands)
# ------------------- Запуск бота -------------------
async def main():
    # Устанавливаем команды Telegram
    await set_commands()

    # Запускаем polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
