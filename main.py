import asyncio
import os
import random
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

# Твой токен и ID администратора
BOT_TOKEN = "8863794029:AAFksCksSBjsxJvwHKElKV8yyf_mYT0C0Go"
ADMIN_ID = 8733425033

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Корзины пользователей
users_cart = {}

# Каталог из прайса (Стоматологія та інші товари)
CATALOG = {
    "stomat": {
        "title": "🦷 Стоматологія та догляд",
        "items": [
            {"id": "s1", "name": "Amal` ополіскувач з пробіотиками, 200 мл", "price": 173.33},
            {"id": "s2", "name": "Зубна паста з Пробіотиками Amal' daily", "price": 178.67},
            {"id": "s3", "name": "Зубна паста з Пробіотиками Amal' kids", "price": 146.0},
            {"id": "s4", "name": "Зубна паста з Пробіотиками Amal' sensitive", "price": 176.67},
            {"id": "s5", "name": "Ремедіум Детокс, гель у стіках 7г №21", "price": 455.0},
            {"id": "s6", "name": "Ремедіум Сінерджі, порошок у стіках 3г №28", "price": 510.0},
            {"id": "s7", "name": "ZONET® засіб для слизових носа, 15 мл", "price": 160.0},
            {"id": "s8", "name": "ZONET® засіб для слизових губ, 10 мл", "price": 125.33},
            {"id": "s9", "name": "Спрей ProbioLor для горла з хлорофіліптом", "price": 90.0},
            {"id": "s10", "name": "Спрей ProbioLor для горла та носа", "price": 82.0}
        ]
    },
    "other": {
        "title": "📦 Інші товари",
        "items": [
            {"id": "o1", "name": "Аредерма спрей з пробіотиками", "price": 230.0},
            {"id": "o2", "name": "Аредерма засіб антисептичний пінка", "price": 150.0},
            {"id": "o3", "name": "Аредерма засіб антисептичний гель", "price": 380.0},
            {"id": "o4", "name": "Аредерма пантенол аерозоль, 130 г", "price": 194.67},
            {"id": "o5", "name": "Набір дорожній Travel ProbioBox", "price": 176.67},
            {"id": "o6", "name": "AREDERMA® ATOPIC гель для душу, 250 мл", "price": 186.0},
            {"id": "o7", "name": "AREDERMA® ATOPIC крем для тіла, 250 мл", "price": 264.67},
            {"id": "o8", "name": "UnicaUro® MAX гель для інтимної гігієни, 250 мл", "price": 206.67},
            {"id": "o9", "name": "Дієтична добавка морський колаген AREDERMA®", "price": 1332.0},
            {"id": "o10", "name": "Аредерма крем для обличчя Soft Serum SPF 50", "price": 286.67}
        ]
    }
}

# Машина станів для замовлення
class OrderState(StatesGroup):
    waiting_for_city = State()
    waiting_for_address = State()
    waiting_for_phone = State()
    waiting_for_fop = State()
    waiting_for_custom_qty = State()

# Головне меню (не зникає)
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛒 Обрати товари")],
        [KeyboardButton(text="🗑 Кошик"), KeyboardButton(text="📋 Прайс")]
    ],
    resize_keyboard=True,
    is_persistent=True
)

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    users_cart[message.from_user.id] = []
    await message.answer("Вітаємо! Оберіть дію в меню нижче:", reply_markup=main_menu)

@dp.message(F.text == "🛒 Обрати товари")
async def show_categories(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🦷 Стоматологія та догляд", callback_data="cat_stomat")],
        [InlineKeyboardButton(text="📦 Інші товари (Аредерма, Гелі, Спреї)", callback_data="cat_other")]
    ])
    await message.answer("Оберіть категорію товарів:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("cat_"))
async def show_products(callback: CallbackQuery):
    cat_id = callback.data.split("_")[1]
    category = CATALOG[cat_id]
    
    for item in category["items"]:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Додати в кошик", callback_data=f"item_{cat_id}_{item['id']}")]
        ])
        await callback.message.answer(
            f"🔹 <b>{item['name']}</b>\nЦіна: {item['price']} грн",
            reply_markup=kb, parse_mode="HTML"
        )
    await callback.answer()

@dp.callback_query(F.data.startswith("item_"))
async def select_quantity(callback: CallbackQuery, state: FSMContext):
    _, cat_id, item_id = callback.data.split("_")
    
    buttons = []
    row = []
    for i in range(1, 11):
        row.append(InlineKeyboardButton(text=str(i), callback_data=f"add_{cat_id}_{item_id}_{i}"))
        if len(row) == 5:
            buttons.append(row)
            row = []
    buttons.append([InlineKeyboardButton(text="✍️ Ввести свою кількість", callback_data=f"customqty_{cat_id}_{item_id}")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("Оберіть необхідну кількість:", reply_markup=kb)

@dp.callback_query(F.data.startswith("add_"))
async def add_to_cart(callback: CallbackQuery):
    parts = callback.data.split("_")
    cat_id, item_id, qty = parts[1], parts[2], int(parts[3])
    
    item_data = next(i for i in CATALOG[cat_id]["items"] if i["id"] == item_id)
    
    user_id = callback.from_user.id
    if user_id not in users_cart:
        users_cart[user_id] = []
        
    users_cart[user_id].append({
        "name": item_data["name"], 
        "price": item_data["price"], 
        "qty": qty
    })
    
    await callback.message.edit_text(f"✅ Додано в кошик: {item_data['name']} — {qty} шт.")
    await callback.answer()

@dp.callback_query(F.data.startswith("customqty_"))
async def custom_qty_prompt(callback: CallbackQuery, state: FSMContext):
    _, cat_id, item_id = callback.data.split("_")
    await state.update_data(current_cat=cat_id, current_item=item_id)
    await callback.message.edit_text("Напишіть цифрою бажану кількість:")
    await state.set_state(OrderState.waiting_for_custom_qty)

@dp.message(OrderState.waiting_for_custom_qty)
async def process_custom_qty(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Будь ласка, введіть тільки число (наприклад, 15).")
        return
        
    qty = int(message.text)
    data = await state.get_data()
    item_data = next(i for i in CATALOG[data["current_cat"]]["items"] if i["id"] == data["current_item"])
    
    user_id = message.from_user.id
    if user_id not in users_cart:
        users_cart[user_id] = []
        
    users_cart[user_id].append({"name": item_data["name"], "price": item_data["price"], "qty": qty})
    
    await message.answer(f"✅ Додано в кошик: {item_data['name']} — {qty} шт.")
    await state.clear()

@dp.message(F.text == "🗑 Кошик")
async def view_cart_summary(message: Message):
    user_id = message.from_user.id
    cart = users_cart.get(user_id, [])
    
    if not cart:
        await message.answer("Ваш кошик порожній.", reply_markup=main_menu)
        return
        
    total_sum = sum(item['price'] * item['qty'] for item in cart)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👁 Переглянути всі товари", callback_data="view_all_cart")],
        [InlineKeyboardButton(text="➖ Прибрати останній товар", callback_data="remove_last")],
        [InlineKeyboardButton(text="✅ Оформити замовлення", callback_data="start_checkout")]
    ])
    
    await message.answer(f"🛒 У кошику {len(cart)} позицій.\nЗагальна сума: <b>{total_sum} грн</b>", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "view_all_cart")
async def view_all_cart_items(callback: CallbackQuery):
    cart = users_cart.get(callback.from_user.id, [])
    if not cart:
        await callback.answer("Кошик порожній", show_alert=True)
        return
        
    text = "<b>Ваше замовлення:</b>\n\n"
    for idx, item in enumerate(cart, 1):
        sum_price = item['price'] * item['qty']
        text += f"<b>{idx}.</b> {item['name']}\nК-ть: {item['qty']} шт. | Сума: {sum_price} грн\n\n"
        
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "remove_last")
async def remove_last_item(callback: CallbackQuery):
    cart = users_cart.get(callback.from_user.id, [])
    if cart:
        removed = cart.pop()
        await callback.message.edit_text(f"❌ Видалено останній товар: {removed['name']}")
    else:
        await callback.answer("Кошик порожній", show_alert=True)

# Оформлення замовлення
@dp.callback_query(F.data == "start_checkout")
async def checkout_city(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Відмінити", callback_data="cancel_order")]])
    await callback.message.answer("Введіть назву міста (працюємо з клініками у містах):", reply_markup=kb)
    await state.set_state(OrderState.waiting_for_city)
    await callback.answer()

@dp.message(OrderState.waiting_for_city)
async def checkout_address(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад до міста", callback_data="start_checkout")]])
    await message.answer("Введіть адресу відділення Нової Пошти (або клініки):", reply_markup=kb)
    await state.set_state(OrderState.waiting_for_address)

@dp.message(OrderState.waiting_for_address)
async def checkout_phone(message: Message, state: FSMContext):
    await state.update_data(address=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад до адреси", callback_data="back_to_address")]])
    await message.answer("Введіть контактний номер телефону отримувача (хто буде забирати вантаж):", reply_markup=kb)
    await state.set_state(OrderState.waiting_for_phone)

@dp.message(OrderState.waiting_for_phone)
async def checkout_fop(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад до телефону", callback_data="back_to_phone")]])
    await message.answer("Введіть дані вашого ФОП або ТОВ (назва, ЄДРПОУ):", reply_markup=kb)
    await state.set_state(OrderState.waiting_for_fop)

@dp.message(OrderState.waiting_for_fop)
async def checkout_confirm(message: Message, state: FSMContext):
    await state.update_data(fop=message.text)
    data = await state.get_data()
    cart = users_cart.get(message.from_user.id, [])
    total_sum = sum(item['price'] * item['qty'] for item in cart)
    
    order_text = "<b>Перевірте дані вашого замовлення:</b>\n\n"
    for idx, item in enumerate(cart, 1):
        order_text += f"▫️ {idx}. {item['name']} — {item['qty']} шт.\n"
    
    order_text += f"\n<b>Загальна сума:</b> {total_sum} грн\n\n"
    order_text += f"<b>Місто:</b> {data['city']}\n"
    order_text += f"<b>Адреса:</b> {data['address']}\n"
    order_text += f"<b>Телефон отримувача:</b> {data['phone']}\n"
    order_text += f"<b>Дані ФОП/ТОВ:</b> {data['fop']}\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ПІДТВЕРДИТИ ЗАМОВЛЕННЯ", callback_data="finish_order")],
        [InlineKeyboardButton(text="🔙 Змінити дані ФОП/ТОВ", callback_data="back_to_fop")]
    ])
    
    await message.answer(order_text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "finish_order")
async def finish_order(callback: CallbackQuery, state: FSMContext):
    order_number = f"SRN-{random.randint(10000, 99999)}"
    
    # Отправка уведомления администратору (тебе)
    try:
        data = await state.get_data()
        cart = users_cart.get(callback.from_user.id, [])
        total_sum = sum(item['price'] * item['qty'] for item in cart)
        
        admin_text = f"🚨 <b>НОВЕ ЗАМОВЛЕННЯ №{order_number}</b>\n\n"
        for idx, item in enumerate(cart, 1):
            admin_text += f"▫️ {idx}. {item['name']} — {item['qty']} шт.\n"
        admin_text += f"\n<b>Сума:</b> {total_sum} грн\n"
        admin_text += f"<b>Місто:</b> {data.get('city')}\n"
        admin_text += f"<b>Адреса:</b> {data.get('address')}\n"
        admin_text += f"<b>Телефон:</b> {data.get('phone')}\n"
        admin_text += f"<b>ФОП/ТОВ:</b> {data.get('fop')}\n"
        admin_text += f"<b>Клієнт ID:</b> {callback.from_user.id}"
        
        await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
    except Exception as e:
        print(f"Не удалось отправить уведомление админу: {e}")

    await callback.message.edit_text(
        f"Дякуємо за довіру до команди Sirion!\n\n"
        f"Ваше замовлення <b>№{order_number}</b> успішно прийнято.\n"
        f"Наш менеджер надішле вам рахунок в особисті повідомлення.",
        parse_mode="HTML"
    )
    users_cart[callback.from_user.id] = []
    await state.clear()

@dp.callback_query(F.data == "back_to_address")
async def back_addr(callback: CallbackQuery, state: FSMContext):
    await checkout_address(callback.message, state)

@dp.callback_query(F.data == "back_to_phone")
async def back_phone(callback: CallbackQuery, state: FSMContext):
    await checkout_phone(callback.message, state)

@dp.callback_query(F.data == "back_to_fop")
async def back_fop(callback: CallbackQuery, state: FSMContext):
    await checkout_fop(callback.message, state)

@dp.callback_query(F.data == "cancel_order")
async def cancel_order(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Оформлення відмінено.")

@dp.message(F.text == "📋 Прайс")
async def send_price(message: Message):
    await message.answer("Актуальний прайс можна переглянути на нашому сайті або уточнити у менеджера.")


# Веб-сервер для тримання бота онлайн 24/7 (Render)
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def start_bot(app):
    asyncio.create_task(dp.start_polling(bot))

def main():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.on_startup.append(start_bot)
    
    port = int(os.environ.get("PORT", 10000))
    web.run_app(app, host='0.0.0.0', port=port)

if __name__ == "__main__":
    main()
