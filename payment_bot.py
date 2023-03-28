# import logging
import time
import stripe
import os
from dotenv import load_dotenv
import asyncio
from telegram.constants import ParseMode
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler,
                          ConversationHandler, CallbackContext)

# logging.basicConfig(
#     format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
# )
# logger = logging.getLogger(__name__)


class Cart:
    def __init__(self):
        self.items = {}
        self.lock = asyncio.Lock()

    async def add_item(self, user_id, product_name, quantity, price):
        async with self.lock:
            try:
                self.items[user_id][product_name] = quantity, price
            except:
                self.items[user_id] = {}
                self.items[user_id][product_name] = quantity, price

    async def dump_cart(self, user_id):
        async with self.lock:
            self.items[user_id] = {}

    async def get_items(self, user_id):
        async with self.lock:
            return self.items[user_id]


(ENTRY_STATE, QUESTION_STATE,) = range(2)
cart = Cart()


async def start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    kb = [[KeyboardButton(text="🏰 Меню 🏰"), KeyboardButton(text="🧺 Корзина 🧺")]]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await update.message.reply_text('Добро пожаловать в нашу <b>кондитерскую</b>!\n'
                                    'Для выбора сладостей нажмите <b>Меню</b>.\n\n'
                                    'Просто добавьте желаемое в корзину и вскоре оно появится у вас дома 😉',
                                    reply_markup=keyboard, parse_mode=ParseMode.HTML)
    return ENTRY_STATE


async def choose_products(update: Update, context: CallbackContext) -> None:
    query = update.callback_query if update.callback_query else update.message
    if query == update.message:
        keyword_1 = [[InlineKeyboardButton(text='Торты', callback_data='Cakes')],
                     [InlineKeyboardButton(text='Печенье', callback_data='Cookies')],
                     [InlineKeyboardButton(text='Желе', callback_data='Jelly')]]
        r_markup = InlineKeyboardMarkup(inline_keyboard=keyword_1)
        await query.reply_text('Выберите раздел, чтобы вывести список товаров', reply_markup=r_markup)

    elif query == update.callback_query:
        if query.data == 'Cakes' or query.data == 'Cookies' or query.data == 'Jelly':
            kb = [[KeyboardButton(text="🏰 Меню 🏰"), KeyboardButton(text="🧺 Корзина 🧺")],
                  [KeyboardButton(text="↩️ Назад ↩️")]]
            keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
            await query.message.reply_text(f'Список имеющихся {query.data} в вашем распоряжении:', reply_markup=keyboard)
            keyword = [[InlineKeyboardButton(text='+1', callback_data='+1'),
                        InlineKeyboardButton(text='-1', callback_data='-1')],
                       [InlineKeyboardButton(text=f'В корзине: 0', callback_data='cart')]]
            r_markup = InlineKeyboardMarkup(inline_keyboard=keyword)
            product_list = [item for item in stripe.Product.list()['data'] if item['statement_descriptor'] == query.data]
            for product in product_list:
                price = stripe.Price.retrieve(product['default_price'])
                await cart.add_item(query.from_user.id, product['name'], 0, price['unit_amount'])
                await query.message.reply_photo(
                    photo=product["images"][0],
                    caption=f"{product['name']}\n{product['description']}\n{price['unit_amount']/100} UAH - шт.",
                    reply_markup=r_markup
                )
        elif query.data == '+1':
            price = float(query.message.caption.split('\n')[2].split(' ')[0])
            product_name = query.message.caption.split('\n')[0]
            items = await cart.get_items(query.message.chat_id)
            quantity = items[product_name][0] + 1
            await cart.add_item(query.message.chat_id, product_name, quantity, price)
            keyword = [[InlineKeyboardButton(text='+1', callback_data='+1'),
                        InlineKeyboardButton(text='-1', callback_data='-1')],
                       [InlineKeyboardButton(text=f'В корзине: {quantity}', callback_data='cart')]]
            r_markup = InlineKeyboardMarkup(inline_keyboard=keyword)
            await query.message.edit_reply_markup(reply_markup=r_markup)
        elif query.data == 'cart':
            product_name = query.message.caption.split('\n')[0]
            items = await cart.get_items(query.message.chat_id)
            quantity = items[product_name][0]
            await query.message.reply_text(f'В корзине {quantity} {product_name}')
        elif query.data == '-1':
            price = float(query.message.caption.split('\n')[2].split(' ')[0])
            product_name = query.message.caption.split('\n')[0]
            items = await cart.get_items(query.message.chat_id)
            quantity = items[product_name][0] - 1 if items[product_name][0] > 0 else items[product_name][0]
            if quantity:
                await cart.add_item(query.message.chat_id, product_name, quantity, price)
                keyword = [[InlineKeyboardButton(text='+1', callback_data='+1'),
                            InlineKeyboardButton(text='-1', callback_data='-1')],
                           [InlineKeyboardButton(text=f'В корзине: {quantity}', callback_data='cart')]]
                r_markup = InlineKeyboardMarkup(inline_keyboard=keyword)
                await update.callback_query.message.edit_reply_markup(reply_markup=r_markup)
    else:
        print('Wrong Update request\n', update)


async def show_bucket(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.message
    kb = [[KeyboardButton(text="🏰 Меню 🏰")], [KeyboardButton(text="↩️ Назад ↩️")]]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    try:
        items = await cart.get_items(query.chat_id)
        if query.text == '🧺 Корзина 🧺':
            kb = [[KeyboardButton(text="💲 Оплатить 💲")],
                  [KeyboardButton(text="🏰 Меню 🏰"), KeyboardButton(text="🧹 Очистить корзину 🧹")]]
            keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
            output, total_amount = "", 0

            total_amount += sum(
                int(price) * quantity for product_name, (quantity, price) in items.items() if quantity)
            output += '\n\n'.join(
                f"{product_name}! Кол-во: {quantity}.\nСтоимость: {int(price) * quantity} UAH - шт." for
                product_name, (quantity, price) in items.items() if quantity)

            output += f"\n\nОбщая стоимость: {total_amount} UAH"
            await query.reply_text("Корзина:\n\n" + output, reply_markup=keyboard)

        elif query.text == '🧹 Очистить корзину 🧹':
            await cart.dump_cart(query.chat_id)
            await query.reply_text(f"Корзина очищена", reply_markup=keyboard)
    except KeyError:
        await query.reply_text(f"Корзина пуста", reply_markup=keyboard)


async def payment_processing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '💲 Оплатить 💲':
        total_amount = 0
        items = await cart.get_items(update.message.chat_id)
        total_amount += sum(
            int(price) * quantity for product_name, (quantity, price) in items.items() if quantity)
        if total_amount > 17:
            line_items = [
                {'price_data': {'currency': 'UAH', 'product_data': {'name': product_name}, 'unit_amount': int(price) * 100},
                 'quantity': quantity} for product_name, (quantity, price) in items.items() if quantity
            ]
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                success_url='https://t.me/damn_quiz_bot',
                cancel_url='https://t.me/damn_quiz_bot',
                expires_at=int(time.time()) + 2100
            )
            button = InlineKeyboardButton(text='Оплатить', url=session.url)
            keyboard = InlineKeyboardMarkup([[button]])
            await update.message.reply_text(
                'Для оплаты нажмите кнопку "Оплатить" ☺️'
                '\n\n(время ожидания оплаты 35 минут)',
                reply_markup=keyboard)

            asyncio.create_task(my_while(update, session))
        else:
            await update.message.reply_text(
                'Просим прощения, но минимальная сумма оплаты 17 грн')


async def my_while(update, session):
    while session.status == "open":
        await asyncio.sleep(30)
        session = stripe.checkout.Session.retrieve(session.id)

    if session.status == "complete":
        await update.message.reply_text(f"Оплата прошла успешно!")
    elif session.status == "expired":
        kb = [[KeyboardButton(text="💲 Оплатить 💲")],
              [KeyboardButton(text="🏰 Меню 🏰"), KeyboardButton(text="🧺 Корзина 🧺")]]
        keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
        await update.message.reply_text(
            f'Что-то пошло не так. Попробуйте снова нажав на кнопку "Оплатить" или обратитесь а администратору.', reply_markup=keyboard)


async def stop_polling(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.stop()


def main():
    """Run the bot."""
    load_dotenv()
    stripe.api_key = os.environ["SRTIPE_KEY"]
    application = Application.builder().token(os.environ["TG_TOKEN"]).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_callback)],
        states={
            ENTRY_STATE: [
                MessageHandler(filters.Regex('🏰 Меню 🏰'), choose_products),
                MessageHandler(filters.Regex('↩️ Назад ↩️'), choose_products),
                CallbackQueryHandler(choose_products),
                MessageHandler(filters.Regex('🧺 Корзина 🧺'), show_bucket),
                MessageHandler(filters.Regex('🧹 Очистить корзину 🧹'), show_bucket),
                MessageHandler(filters.Regex('💲 Оплатить 💲'), payment_processing)
            ],
            QUESTION_STATE: [
            ],
        },
        fallbacks=[CommandHandler("stop", stop_polling)],
    )
    application.add_handler(conv_handler)
    print("Bot is running ...")
    application.run_polling()


if __name__ == "__main__":
    main()
