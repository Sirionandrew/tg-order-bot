import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

# -------------------------------------------------------------------
# КОНФИГУРАЦИЯ (НАСТРОЙКИ)
# -------------------------------------------------------------------
BOT_TOKEN = "8863794029:AAFksCksSBjsxJvwHKElKV8yyf_mYT0C0Go"
ADMIN_CHAT_ID = 8733425033 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# База данных сохраненных реквизитов клиентов (в памяти бота)
USER_DOCS_DB = {}

# -------------------------------------------------------------------
# КАТАЛОГ ТОВАРОВ
# -------------------------------------------------------------------
CATALOG = {
    "prod_1": {"name": "Пробіотик для обличчя Sirion (50 мл)", "price": 450},
    "prod_2": {"name": "Пробіотичний гель для вмивання (200 мл)", "price": 380},
    "prod_3": {"name": "Захисний спрей з пробіотиками (150 мл)", "price": 420},
}

# -------------------------------------------------------------------
# СОСТОЯНИЯ ДИАЛОГА (FSM)
# -------------------------------------------------------------------
class OrderForm(StatesGroup):
    selecting_products = State()
    delivery_type = State()
    city = State()
    warehouse = State()       # Отделение / почтомат
    street_address = State()  # Адресная доставка
    full_name = State()
    phone = State()
    upload_docs = State()     # Загрузка документов/реквизитов
    confirm = State()


# -------------------------------------------------------------------
# ВСПОМОГАТЕЛЬНЫЕ КЛАВИАТУРЫ
# -------------------------------------------------------------------
def get_catalog_keyboard(cart: dict):
    buttons = []
    for code, item in CATALOG.items():
        count = cart.get(code, 0)
        count_text = f" ({count} шт.)" if count > 0 else ""
        btn_text = f"{item['name']} — {item['price']} грн{count_text}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"add_{code}")])
    
    if cart:
        buttons.append([InlineKeyboardButton(text="✅ Оформити замовлення", callback_data="checkout")])
        buttons.append([InlineKeyboardButton(text="🗑 Очистити кошик", callback_data="clear_cart")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_main_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🛒 Каталог товарів / Замовити")]],
        resize_keyboard=True,
    )


# -------------------------------------------------------------------
# ОБРАБОТЧИКИ КОМАНД И СООБЩЕНИЙ
# -------------------------------------------------------------------
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Вітаємо у нашому магазині! Натисніть кнопку нижче, щоб переглянути каталог та зробити замовлення.",
        reply_markup=get_main_menu_keyboard(),
    )


@dp.message(F.text == "🛒 Каталог товарів / Замовити")
async def show_catalog(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", {})
    await state.set_state(OrderForm.selecting_products)
    
    await message.answer(
        "Оберіть товари з каталогу (натискайте на товар, щоб додати його в кошик):",
        reply_markup=get_catalog_keyboard(cart),
    )


# Добавление товара в корзину
@dp.callback_query(OrderForm.selecting_products, F.data.startswith("add_"))
async def add_to_cart(callback: types.CallbackQuery, state: FSMContext):
    prod_code = callback.data.replace("add_", "")
    data = await state.get_data()
    cart = data.get("cart", {})
    
    cart[prod_code] = cart.get(prod_code, 0) + 1
    await state.update_data(cart=cart)
    
    total_sum = sum(CATALOG[code]["price"] * qty for code, qty in cart.items())
    
    await callback.message.edit_text(
        f"Товар додано! Поточна сума кошика: **{total_sum} грн**\n\nВиберіть ще товари або натисніть «Оформити замовлення»:",
        parse_mode="Markdown",
        reply_markup=get_catalog_keyboard(cart),
    )


# Очистка корзины
@dp.callback_query(OrderForm.selecting_products, F.data == "clear_cart")
async def clear_cart(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(cart={})
    await callback.message.edit_text(
        "Кошик очищено. Оберіть товари заново:",
        reply_markup=get_catalog_keyboard({}),
    )


# Переход к оформлению доставки
@dp.callback_query(OrderForm.selecting_products, F.data == "checkout")
async def start_checkout(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏢 Відділення / Поштомат", callback_data="del_warehouse")],
            [InlineKeyboardButton(text="🏠 Адресна доставка (кур'єром)", callback_data="del_courier")],
        ]
    )
    await callback.message.edit_text(
        "Оберіть спосіб доставки Новою Поштою:", reply_markup=kb
    )
    await state.set_state(OrderForm.delivery_type)


# Выбор типа доставки
@dp.callback_query(OrderForm.delivery_type, F.data.in_({"del_warehouse", "del_courier"}))
async def process_delivery_type(callback: types.CallbackQuery, state: FSMContext):
    delivery_type = (
        "Відділення / Поштомат"
        if callback.data == "del_warehouse"
        else "Адресна доставка (кур'єром)"
    )
    await state.update_data(delivery_type=delivery_type, delivery_code=callback.data)

    await callback.message.edit_text(
        f"Обрано: {delivery_type}\n\nВкажіть ваше **Місто / Населений пункт** (і область, якщо це не обласний центр):"
    )
    await state.set_state(OrderForm.city)


# Ввод города
@dp.message(OrderForm.city)
async def process_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    data = await state.get_data()

    if data["delivery_code"] == "del_warehouse":
        await message.answer("Вкажіть **номер відділення** або **поштомата** Нової Пошти:")
        await state.set_state(OrderForm.warehouse)
    else:
        await message.answer("Вкажіть **вулицю, номер будинку та квартири** для кур'єра:")
        await state.set_state(OrderForm.street_address)


# Ввод отделения
@dp.message(OrderForm.warehouse)
async def process_warehouse(message: types.Message, state: FSMContext):
    await state.update_data(address_details=f"Відділення/Поштомат: {message.text}")
    await message.answer("Введіть **ПІБ отримувача** (Прізвище та Ім'я повністю):")
    await state.set_state(OrderForm.full_name)


# Ввод адреса курьера
@dp.message(OrderForm.street_address)
async def process_street_address(message: types.Message, state: FSMContext):
    await state.update_data(address_details=f"Адреса кур'єра: {message.text}")
    await message.answer("Введіть **ПІБ отримувача** (Прізвище та Ім'я повністю):")
    await state.set_state(OrderForm.full_name)


# Ввод ФИО
@dp.message(OrderForm.full_name)
async def process_full_name(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Надіслати свій номер", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await message.answer(
        "Вкажіть ваш **номер телефону** (натисніть кнопку нижче або введіть вручну):",
        reply_markup=kb,
    )
    await state.set_state(OrderForm.phone)


# Ввод телефона и логика проверки сохраненных документов
@dp.message(OrderForm.phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else message.text
    await state.update_data(phone=phone)
    user_id = message.from_user.id

    # Проверяем, есть ли у нас сохраненные реквизиты/документы этого клиента
    if user_id in USER_DOCS_DB:
        saved_doc = USER_DOCS_DB[user_id]
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Використати збережені реквізити", callback_data="use_saved_docs")],
                [InlineKeyboardButton(text="🔄 Оновити реквізити / надіслати нові", callback_data="change_docs")],
            ]
        )
        await message.answer(
            f"📄 **Ваші реквізити збережено з попереднього замовлення:**\n`{saved_doc['doc_name']}`\n\nБажаєте використати їх чи завантажити нові?",
            parse_mode="Markdown",
            reply_markup=kb,
            reply_markup_type=ReplyKeyboardRemove(),
        )
        await state.set_state(OrderForm.upload_docs)
    else:
        # Если клиент первый раз
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⏭ Пропустити цей крок", callback_data="skip_docs")]
            ]
        )
        await message.answer(
            "📄 **Надішліть документи / реквізити для вистави рахунку:**\n\n"
            "Ви можете прикріпити фото або файл (виписка ФОП/ТОВ, реквізити) або вписати текстом ЄДРПОУ/ІПН.\n\n"
            "Якщо ви купуєте як приватна особа або надсилали реквізити раніше — натисніть «Пропустити цей крок»:",
            reply_markup=kb,
            reply_markup_type=ReplyKeyboardRemove(),
        )
        await state.set_state(OrderForm.upload_docs)


# Использование сохраненных реквизитов
@dp.callback_query(OrderForm.upload_docs, F.data == "use_saved_docs")
async def use_saved_docs_handler(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    saved_doc = USER_DOCS_DB.get(user_id, {})
    await state.update_data(
        doc_id=saved_doc.get("doc_id"),
        doc_type=saved_doc.get("doc_type"),
        doc_name=saved_doc.get("doc_name", "Збережені реквізити"),
    )
    await show_order_summary(callback, state)


# Запрос новых реквизитов при обновлении
@dp.callback_query(OrderForm.upload_docs, F.data == "change_docs")
async def change_docs_handler(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустити цей крок", callback_data="skip_docs")]
        ]
    )
    await callback.message.edit_text(
        "Будь ласка, надішліть нові **документи / реквізити** (файлом, фото або текстом):",
        reply_markup=kb,
    )


# Обработка отправки файла/фото/текста с документами
@dp.message(OrderForm.upload_docs, F.document | F.photo | F.text)
async def process_docs_file(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if message.document:
        doc_id = message.document.file_id
        doc_type = "document"
        doc_name = f"Файл: {message.document.file_name}"
    elif message.photo:
        doc_id = message.photo[-1].file_id
        doc_type = "photo"
        doc_name = "Фото документа"
    else:
        doc_id = None
        doc_type = "text"
        doc_name = f"Текст: {message.text}"

    # Сохраняем в память для следующих заказов
    USER_DOCS_DB[user_id] = {"doc_id": doc_id, "doc_type": doc_type, "doc_name": doc_name}

    await state.update_data(doc_id=doc_id, doc_type=doc_type, doc_name=doc_name)
    await show_order_summary(message, state)


# Пропуск отправки документов
@dp.callback_query(OrderForm.upload_docs, F.data == "skip_docs")
async def process_docs_skip(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(doc_id=None, doc_type="skipped", doc_name="Не надано / Повторний клієнт")
    await show_order_summary(callback, state)


# Формирование и показ сводки
async def show_order_summary(message_or_callback, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", {})

    items_text = ""
    total_sum = 0
    for code, qty in cart.items():
        item = CATALOG[code]
        item_total = item["price"] * qty
        total_sum += item_total
        items_text += f"• {item['name']} x{qty} = {item_total} грн\n"

    summary_text = (
        "📋 **Перевірте дані вашого замовлення:**\n\n"
        f"📦 **Товари:**\n{items_text}\n"
        f"💰 **Загальна сума:** {total_sum} грн\n\n"
        f"• **Доставка:** {data['delivery_type']}\n"
        f"• **Місто:** {data['city']}\n"
        f"• **Адреса/Відділення:** {data['address_details']}\n"
        f"• **Отримувач:** {data['full_name']}\n"
        f"• **Телефон:** {data['phone']}\n"
        f"• **Реквізити:** {data.get('doc_name', 'Не вказано')}\n"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Підтвердити замовлення", callback_data="confirm_yes")],
            [InlineKeyboardButton(text="❌ Скасувати та почати знову", callback_data="confirm_no")],
        ]
    )

    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.edit_text(summary_text, parse_mode="Markdown", reply_markup=kb)
    else:
        await message_or_callback.answer(summary_text, parse_mode="Markdown", reply_markup=kb)

    await state.set_state(OrderForm.confirm)


# Финальное подтверждение
@dp.callback_query(OrderForm.confirm, F.data == "confirm_yes")
async def order_confirmed(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", {})
    user = callback.from_user
    username = f"@{user.username}" if user.username else "Немає username"

    items_text = ""
    total_sum = 0
    for code, qty in cart.items():
        item = CATALOG[code]
        item_total = item["price"] * qty
        total_sum += item_total
        items_text += f"• {item['name']} x{qty} = {item_total} грн\n"

    # Текст для администратора
    admin_text = (
        "🔔 **НАДІЙШЛО НОВЕ ЗАМОВЛЕННЯ!**\n\n"
        f"👤 **Покупець в TG:** {user.full_name} ({username})\n"
        f"🆔 **ID клієнта:** `{user.id}`\n\n"
        f"📦 **Товари:**\n{items_text}\n"
        f"💵 **СУМА ЗАМОВЛЕННЯ:** {total_sum} грн\n\n"
        f"🚚 **Тип доставки:** {data['delivery_type']}\n"
        f"🏙 **Місто:** {data['city']}\n"
        f"📍 **Деталі адреси:** {data['address_details']}\n"
        f"📛 **ПІБ:** {data['full_name']}\n"
        f"📞 **Тел:** {data['phone']}\n"
        f"📄 **Реквізити/Документи:** {data.get('doc_name', 'Не надіслано')}"
    )

    # Отправка администратору
    await bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_text, parse_mode="Markdown")

    # Пересылаем файл/фото документов администратору (даже если они сохраненные)
    doc_type = data.get("doc_type")
    doc_id = data.get("doc_id")
    if doc_type == "document" and doc_id:
        await bot.send_document(chat_id=ADMIN_CHAT_ID, document=doc_id, caption=f"📄 Документи від {user.full_name}")
    elif doc_type == "photo" and doc_id:
        await bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=doc_id, caption=f"📄 Фото документів від {user.full_name}")

    # Ответ клиенту
    await callback.message.edit_text(
        "🎉 **Дякуємо! Ваше замовлення прийнято.**\n\n"
        "📄 Наш менеджер перевірить наявність та надішле вам рахунок на оплату найближчим часом."
    )
    
    # Сбрасываем состояние и даем возможность сделать НОВЫЙ заказ
    await state.clear()
    await callback.message.answer(
        "Ви можете зробити ще одне замовлення у будь-який час:",
        reply_markup=get_main_menu_keyboard()
    )


@dp.callback_query(OrderForm.confirm, F.data == "confirm_no")
async def order_cancelled(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Замовлення скасовано.")
    await state.clear()
    await callback.message.answer(
        "Натисніть кнопку нижче, щоб почати знову:",
        reply_markup=get_main_menu_keyboard()
    )


# -------------------------------------------------------------------
# ЗАПУСК
# -------------------------------------------------------------------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
