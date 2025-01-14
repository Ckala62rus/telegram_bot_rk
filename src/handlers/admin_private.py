import logging
from dataclasses import dataclass

from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query_user import get_user_by_phone_number, \
    set_admin_for_user
from filters.chat_types import ChatTypeFilter, IsAdmin, IsAdminFromDatabase, InlineButtonExpired
from kbds.inline import get_callback_btns
from kbds.reply import get_keyboard
from utils.time_utils import DateHelper

logger = logging.getLogger(__name__)

admin_router = Router()
admin_router.message.filter(ChatTypeFilter(['private']), IsAdminFromDatabase())

ADMIN_KB = get_keyboard(
    "Добавить товар",
    "Изменить товар",
    "Удалить товар",
    "Я так, просто посмотреть зашел",
    "Назначить админа",
    placeholder="Выберите действие",
    sizes=(2, 1, 1)
)

CANCEL_BT = get_keyboard(
    "отмена",
)

#######################
## Paginate Testing   #
#######################

PRODUCTS = []


class Pagination(CallbackData, prefix="pag"):
    page: int


async def get_paginated_kb(page: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for i in range(1, 20):
        PRODUCTS.append(Category(id=i, name=f"Продукт_{i}"))

    products: list[Category] = PRODUCTS
    start_offset = page * 5
    end_offset = start_offset + 5

    for product in products[start_offset:end_offset]:
        builder.row(InlineKeyboardButton(text=product.name, callback_data=f"page_{product.id}"))

    buttons_row = []
    if page > 0:
        buttons_row.append(
            InlineKeyboardButton(
                text="⬅️",
                # callback_data=Pagination(page=page - 1).pack(),
                callback_data=f"page_{page - 1}",
            )
        )
    if end_offset < len(PRODUCTS):
        buttons_row.append(
            InlineKeyboardButton(
                text="➡️",
                # callback_data=Pagination(page=page + 1).pack(),
                callback_data=f"page_{page + 1}",
            )
        )
    builder.row(*buttons_row)

    return builder.as_markup()


@admin_router.message(Command(commands=["paginate"]))
async def send_products_handler(message: types.Message):
    await message.answer(
        text="Список товаров:",
        reply_markup=await get_paginated_kb(),
    )


@admin_router.callback_query(F.data.startswith("page_"))
async def products_pagination_callback(callback: types.CallbackQuery):
    page = callback.data.split("page_")[1]
    await callback.message.edit_reply_markup(
        reply_markup=await get_paginated_kb(page=int(page))
    )


#######################
## End Paginate Block #
#######################


@dataclass
class Category:
    id: int
    name: str


CATEGORIES = []


@admin_router.message(Command("categories_init"))
async def categories_init(message: types.Message):
    # try:
    for i in range(1, 5):
        CATEGORIES.append(Category(id=i, name=f"Категория_{i}"))
    await message.answer("Категории созданы")
    # except Exception as e:
    # logger.error(e)


class CategoryCallbackFactory(CallbackData, prefix="category_by_id"):
    id: int
    name: str
    inline_button_expired: str


@admin_router.message(Command("categories"))
async def categories(message: types.Message):
    if len(CATEGORIES) == 0:
        return await message.answer("Список категорий пуст")

    inline_categories = {}

    for category in CATEGORIES:
        # inline_categories[category.name] = f"category_{category.id}"

        date_now = DateHelper.get_current_date()

        inline_categories[category.name] = CategoryCallbackFactory(
            id=category.id,
            name=category.name,
            inline_button_expired=DateHelper.date_to_string(date_now)
        ).pack()

    await message.answer(
        "Список категорий",
        parse_mode="HTML",
        reply_markup=get_callback_btns(
            btns=inline_categories,
            size=(1,),
            btns_last={
                "❌ Удалить категорию": f"delete_categories_list"
            },
        )
    )


@admin_router.callback_query(CategoryCallbackFactory.filter())
async def category_class_callback(callback: CallbackQuery, callback_data: CategoryCallbackFactory):
    await callback.answer()

    is_expired = DateHelper.date_was_expired(callback_data.inline_button_expired)

    if is_expired:
        await callback.message.answer("Кнопка просрочена")
        logger.debug("check inline button expired")
    logger.debug(callback_data.model_dump_json(indent=4,))


@admin_router.callback_query(F.data.startswith("delete_categories_list"))
async def delete_categories_list(callback: types.CallbackQuery, db_session: AsyncSession):
    await callback.answer()

    if len(CATEGORIES) == 0:
        return await callback.message.answer("Список категорий пуст")

    inline_categories = {}

    for category in CATEGORIES:
        inline_categories["❌ " + category.name] = f"delete_category_{category.id}"

    await callback.message.edit_text(
        "Какую категорию удалить?",
        parse_mode="HTML",
        reply_markup=get_callback_btns(
            btns=inline_categories,
            size=(1,),
            btns_last={
                "↩ Отмена": f"return_categories_list"
            },
        )
    )


@admin_router.callback_query(F.data.startswith("return_categories_list"))
async def return_categories_list(callback: types.CallbackQuery, db_session: AsyncSession):
    inline_categories = {}

    for category in CATEGORIES:
        inline_categories[category.name] = f"category_{category.id}"

    await callback.message.edit_text(
        "Список категорий",
        parse_mode="HTML",
        reply_markup=get_callback_btns(
            btns=inline_categories,
            size=(1,),
            btns_last={
                "❌ Удалить категорию": f"delete_categories_list"
            },
        )
    )


@admin_router.callback_query(F.data.startswith("delete_category_"))
async def delete_category_by_id(callback: types.CallbackQuery, db_session: AsyncSession):
    category_id = callback.data.split("delete_category_")[1]

    for index, category in enumerate(CATEGORIES):
        if category.id == int(category_id):
            del CATEGORIES[index]

    if len(CATEGORIES) == 0:
        return await callback.message.edit_text("Список категорий пуст")

    inline_categories = {}

    for category in CATEGORIES:
        inline_categories["❌ " + category.name] = f"delete_category_{category.id}"

    await callback.message.edit_text(
        "Какую категорию удалить?",
        parse_mode="HTML",
        reply_markup=get_callback_btns(
            btns=inline_categories,
            size=(1,),
            btns_last={
                "↩ Отмена": f"return_categories_list"
            },
        )
    )


@admin_router.callback_query(F.data.startswith("category_"))
async def category_by_id(callback: types.CallbackQuery, db_session: AsyncSession):
    try:
        category_id = callback.data.split("category_")[1]
        if len(CATEGORIES) <= 0:
            await callback.answer()
            return await callback.message.answer("Список категорий пуст")
        for category in CATEGORIES:
            if category.id == int(category_id):
                await callback.answer(f"{category.name} с идентификатором {category.id}")
    except Exception as e:
        logger.exception(e)


@admin_router.message(Command("admin"))
async def admin_panel(message: types.Message):
    await message.answer("Что хотите сделать?", reply_markup=ADMIN_KB)


@admin_router.message(F.text == "Я так, просто посмотреть зашел")
async def starting_at_product(message: types.Message):
    logger.debug("DEBUG показ инлайн сообщения с кнопками")
    logger.info("INFO показ инлайн сообщения с кнопками")
    logger.warning("WARNING показ инлайн сообщения с кнопками")
    logger.error("ERROR показ инлайн сообщения с кнопками")
    logger.critical("CRITICAL показ инлайн сообщения с кнопками")

    await message.answer("какой то товар", reply_markup=get_callback_btns(btns={
        "Удалить": f"delete_product_{1}",
        "Измменить": f"update_product{1}",
    }))

    await message.answer(
        "ОК, вот список товаров",
    )


# Пример CallbackQuery
@admin_router.callback_query(F.data.startswith("delete_product_"))
async def delete_product(callback: types.CallbackQuery, db_session: AsyncSession):
    await callback.answer()
    product_id = callback.data.split("delete_product_")[1]
    old_text = callback.message.text
    await callback.message.edit_text(
        old_text + '\n \n' + f"Был удален товар с id: {product_id}",
        reply_markup=get_callback_btns(btns={
            "Удалить": f"delete_product_{1}",
            "Измменить": f"update_product{1}",
        }))
    # print("test")


@admin_router.message(F.text == "Изменить товар")
async def change_product(message: types.Message):
    await message.answer("ОК, вот список товаров")


@admin_router.message(F.text == "Удалить товар")
async def delete_product(message: types.Message):
    await message.answer("Выберите товар(ы) для удаления")


# Код ниже для машины состояний (FSM)

class AddProduct(StatesGroup):
    name = State()
    description = State()
    price = State()
    image = State()

    texts = {
        'AddProduct:name': 'Введите название заново:',
        'AddProduct:description': 'Введите описание заново:',
        'AddProduct:price': 'Введите стоимость заново:',
        'AddProduct:image': 'Этот стейт последний, поэтому...',
    }


@admin_router.message(StateFilter(None), F.text == "Добавить товар")
async def add_product(message: types.Message, state: FSMContext):
    await message.answer(
        "Введите название товара", reply_markup=CANCEL_BT
    )
    # await message.answer("Д", reply_markup=CANCEL_BT)
    await state.set_state(AddProduct.name)


@admin_router.message(StateFilter('*'), Command("отмена"))
@admin_router.message(StateFilter('*'), F.text.casefold() == "отмена")
async def cancel_handler(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    await message.answer("Действия отменены", reply_markup=ADMIN_KB)


@admin_router.message(StateFilter('*'), Command("clear"))
async def cancel_handler(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    await message.answer("Все действия по созданию товара отменены")


@admin_router.message(Command("назад"))
@admin_router.message(F.text.casefold() == "назад")
async def cancel_handler(message: types.Message, state: FSMContext) -> None:
    await message.answer(f"ок, вы вернулись к прошлому шагу")


@admin_router.message(AddProduct.name, F.text)
async def add_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите описание товара. " +
                         "Для отмены всех действий введите команду /clear")
    await state.set_state(AddProduct.description)


@admin_router.message(AddProduct.description, F.text)
async def add_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Введите стоимость товара. " +
                         "Для отмены всех действий введите команду /clear")
    await state.set_state(AddProduct.price)


@admin_router.message(AddProduct.price, F.text)
async def add_price(message: types.Message, state: FSMContext):
    try:
        float(message.text)
    except ValueError:
        await message.answer("Введите корректное значение цены")
        return

    await state.update_data(price=float(message.text))
    await message.answer("Загрузите изображение товара. " +
                         "Для отмены всех действий введите команду /clear")
    await state.set_state(AddProduct.image)


@admin_router.message(AddProduct.image, F.photo)
async def add_image(message: types.Message, state: FSMContext):
    await state.update_data(image=message.photo[-1].file_id)
    await message.answer("Товар добавлен", reply_markup=ADMIN_KB)
    data = await state.get_data()
    await message.answer(str(data))
    await state.clear()


# Admin add (назначаем админа через состояние)
class AddAdmin(StatesGroup):
    phone = State()
    confirm = State()

    texts = {
        'AddProduct:phone': 'Введите телефон заново для поиска пользователя:',
    }


@admin_router.message(StateFilter(None), F.text == "Назначить админа")
async def find_user_for_set_admin(message: types.Message, state: FSMContext):
    await message.answer(
        "Введите номер телефон для поиска",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(AddAdmin.phone)


@admin_router.message(AddAdmin.phone, F.text)
async def set_phone_for_set_admin(
        message: types.Message,
        state: FSMContext,
        db_session: AsyncSession
):
    await state.update_data(phone=message.text)

    user = await get_user_by_phone_number(db_session, message.text)

    text = """
        *** Информация о пользователе ***
    ID: {id}
    Username: {username}
    Telegram ID: {telegram_id}
    Phone number: {phone}
    Created at: {created_at}
    """.format(
        id=user.id,
        username=user.username,
        telegram_id=user.telegram_id,
        phone=user.phone_number,
        created_at=user.created_at,
    )

    await message.answer(text=text)

    await message.answer("Что бы дать админа, введите 'да' " +
                         "Для отмены всех действий введите команду /clear")
    await state.set_state(AddAdmin.confirm)


@admin_router.message(AddAdmin.confirm, F.text)
async def confirm_admin_create(
        message: types.Message,
        state: FSMContext,
        db_session: AsyncSession
):
    if message.text == "да":
        await state.update_data(confirm=message.text)
        data = await state.get_data()
        await message.answer("Права администратора добавлены")
        await set_admin_for_user(db_session, data["phone"], True)
        await state.clear()
    else:
        await message.answer("Введите 'да' для подтверждения " +
                             "Для отмены всех действий введите команду /clear")


# @admin_router.message(F.text)
# async def start_command(message: types.Message):
#     await message.answer(text="Это магический фильтр из админской ветки")
