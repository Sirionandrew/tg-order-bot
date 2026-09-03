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
# КОНФІГУРАЦІЯ (НАЛАШТУВАННЯ)
# -------------------------------------------------------------------
# ВСТАВ СВІЙ ТОКЕН ВІД BOTFATHER У МІЖ КУП'ЯТКИ НИЖЧЕ:
BOT_TOKEN = "8863794029:AAFksCksSBjsxJvwHKElKV8yyf_mYT0C0Go"

# ВСТАВ СВІЙ ЦИФРОВИЙ ID З USERINFOBOT (БЕЗ ДУЖОК ТА КУП'ЯТОК):
ADMIN_CHAT_ID = 8733425033 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# -------------------------------------------------------------------
# СТАНЫ ДІАЛОГУ (FSM)
# -------------------------------------------------------------------
class OrderForm(StatesGroup):
    delivery_type = State()
    city = State()
    warehouse = State()       # Якщо відділення / поштомат
    street_address = State()  # Якщо адресна доставка
    full_name = State()
    phone = State()
    payment_method = State()
    confirm = State()


# -------------------------------------------------------------------
# ОБРОБНИКИ КОМАНД ТА ПОВІДОМЛЕНЬ
# -------------------------------------------------------------------
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🛒 Оформити замовлення")]],
        resize_keyboard=True,
    )
    await message.answer(
        "Вітаємо! Натисніть кнопку нижче, щоб оформити замовлення.", reply_markup=kb
    )


@dp.message(F.text == "🛒 Оформити замовлення")
async def start_order(message: types.Message, state: FSMContext):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏢 Відділення / Поштомат", callback_data="del_warehouse"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Адресна доставка (кур'єром)",
                    callback_data="del_courier",
                )
            ],
        ]
    )
    await message.answer(
        "Оберіть спосіб доставки Новою Поштою:", reply_markup=kb
    )
    await state.set_state(OrderForm.delivery_type)


# Вибір типу доставки
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


# Введення міста
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


# Введення відділення
@dp.message(OrderForm.warehouse)
async def process_warehouse(message: types.Message, state: FSMContext):
    await state.update_data(address_details=f"Відділення/Поштомат: {message.text}")
    await message.answer("Введіть **ПІБ отримувача** (Прізвище та Ім'я повністю):")
    await state.set_state(OrderForm.full_name)


# Введення адреси курьєра
@dp.message(OrderForm.street_address)
async def process_street_address(message: types.Message, state: FSMContext):
    await state.update_data(address_details=f"Адреса кур'єра: {message.text}")
    await message.answer("Введіть **ПІБ отримувача** (Прізвище та Ім'я повністю):")
    await state.set_state(OrderForm.full_name)


# Введення ПІБ
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


# Введення телефону
@dp.message(OrderForm.phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else message.text
    await state.update_data(phone=phone)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Передоплата / На картку", callback_data="pay_card")],
            [InlineKeyboardButton(text="🚚 Післяплата (накладений платіж)", callback_data="pay_cod")],
        ]
    )
    await message.answer(
        "Оберіть **спосіб оплати**:", reply_markup=kb, reply_markup_type=ReplyKeyboardRemove()
    )
    await state.set_state(OrderForm.payment_method)


# Вибір оплати та підсумок
@dp.callback_query(OrderForm.payment_method, F.data.in_({"pay_card", "pay_cod"}))
async def process_payment(callback: types.CallbackQuery, state: FSMContext):
    payment = "Передоплата на картку" if callback.data == "pay_card" else "Післяплата"
    await state.update_data(payment=payment)

    data = await state.get_data()

    summary_text = (
        "📋 **Перевірте дані вашого замовлення:**\n\n"
        f"• **Доставка:** {data['delivery_type']}\n"
        f"• **Місто:** {data['city']}\n"
        f"• **Адреса/Відділення:** {data['address_details']}\n"
        f"• **Отримувач:** {data['full_name']}\n"
        f"• **Телефон:** {data['phone']}\n"
        f"• **Оплата:** {data['payment']}\n"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Підтвердити замовлення", callback_data="confirm_yes")],
            [InlineKeyboardButton(text="❌ Скасувати та почати знову", callback_data="confirm_no")],
        ]
    )

    await callback.message.edit_text(summary_text, parse_mode="Markdown", reply_markup=kb)
    await state.set_state(OrderForm.confirm)


# Фінальне підтвердження
@dp.callback_query(OrderForm.confirm, F.data == "confirm_yes")
async def order_confirmed(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = callback.from_user
    username = f"@{user.username}" if user.username else "Немає username"

    # Повідомлення ДЛЯ ВАС (Адміністратора)
    admin_text = (
        "🔔 **НАДІЙШЛО НОВЕ ЗАМОВЛЕННЯ!**\n\n"
        f"👤 **Покупець в TG:** {user.full_name} ({username})\n"
        f"🚚 **Тип доставки:** {data['delivery_type']}\n"
        f"🏙 **Місто:** {data['city']}\n"
        f"📍 **Деталі адреси:** {data['address_details']}\n"
        f"📛 **ПІБ:** {data['full_name']}\n"
        f"📞 **Тел:** {data['phone']}\n"
        f"💳 **Оплата:** {data['payment']}"
    )

    # Відправляємо вам у приватні повідомлення
    await bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_text, parse_mode="Markdown")

    # Відповідь клієнту
    await callback.message.edit_text(
        "🎉 **Дякуємо! Ваше замовлення прийнято.**\nМи зв'яжемося з вами найближчим часом для уточнення деталей."
    )
    await state.clear()


@dp.callback_query(OrderForm.confirm, F.data == "confirm_no")
async def order_cancelled(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Замовлення скасовано. Натисніть /start, щоб почати знову.")
    await state.clear()


# -------------------------------------------------------------------
# ЗАПУСК
# -------------------------------------------------------------------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
