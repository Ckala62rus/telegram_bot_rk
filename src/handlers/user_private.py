import logging
from datetime import datetime, timedelta
from time import strptime, strftime

import httpx
from aiogram import types, Router, F, Bot
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy.ext.asyncio import AsyncSession

from api.dto_api import DTORequest
from api.urls import apiUrls
from config.configuration import settings
from database.orm_query_user import get_user_by_telegram_id, add_user, \
    update_phone_user
from filters.chat_types import ChatTypeFilter
from handlers.admin_private import ADMIN_KB
from kbds import reply
from kbds.inline import get_callback_btns
from kbds.reply import get_keyboard

user_private_router = Router()
user_private_router.message.filter(ChatTypeFilter(['private']))

logger = logging.getLogger(__name__)


@user_private_router.message(CommandStart())
async def start_command(message: types.Message, db_session: AsyncSession):
    # await message.answer(text="This command '/start'")
    user = await get_user_by_telegram_id(db_session, message.from_user.id)

    if user is None:
        await add_user(db_session, {
            "username": message.from_user.username,
            "telegram_id": message.from_user.id,
        })

    await message.answer(
        text="This command '/start'",
        reply_markup=reply.start_kb
    )


@user_private_router.message(Command('menu'))
async def menu_command(message: types.Message, db_session: AsyncSession):
    logger.debug(f"command 'menu' : from {message.from_user.id} | {message.from_user.username} | {message.text}")
    try:
        print(2 / 0)
    except Exception as e:
        logger.exception(e)
    await message.answer(text="Вот меню")


@user_private_router.message(Command('about'))
async def about_command(message: types.Message):
    await message.answer(text="О нас")


@user_private_router.message(Command('payment'))
async def payment_command(message: types.Message):
    await message.answer(text="Оплата")


@user_private_router.message(Command('shipping'))
async def shipping_command(message: types.Message):
    await message.answer(text="Доставка")


# "^([0-9]{2,4})@([a-zA-Z]{0,5})$" => 1234@test
@user_private_router.message(F.text.regexp("^([0-9]{2,4})@([a-zA-Z]{0,5})$"))
async def some_command(message: types.Message):
    await message.answer(text=message.text)


@user_private_router.message(Command('phone'))
async def phone_command(message: types.Message):
    await message.answer(
        text="Отправьте свой номер телефона",
        reply_markup=reply.phone_kb
    )


@user_private_router.message(F.contact)
async def contact_command(message: types.Message, db_session: AsyncSession):
    await update_phone_user(
        db_session,
        message.from_user.id,
        message.contact.phone_number
    )

    await message.answer(
        text=f"Вот твой номер: {message.contact.phone_number}",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await message.answer(str(message.contact))


@user_private_router.message(F.location)
async def location_command(message: types.Message):
    await message.answer(text="Ваша локация")
    await message.answer(str(message.location))


@user_private_router.message(Command('about_me'))
async def about_me_command(message: types.Message, db_session: AsyncSession):
    user = await get_user_by_telegram_id(db_session, message.from_user.id)

    text = """
        *** Информация обо мне: ***
        Ник: {username}
        Телефонный номер: {phone}
        Телеграм id: {telegram_id}
    """.format(
        username=user.username,
        phone="Номер не указан" if user.phone_number is None else user.phone_number,
        telegram_id=user.telegram_id,
    )

    await message.answer(
        text=text,
    )


@user_private_router.message(Command("products"))
async def start_command(message: types.Message):
    await message.answer(
        text="Какой то продукт с кнопками",
        reply_markup=get_callback_btns(
            btns={
                "Характеристики": "product_info_1",
                "Удалить товар": "product_delete_1",
            }
        )
    )


@user_private_router.callback_query(F.data.startswith("product_info_"))
async def start_command(callback: types.CallbackQuery):
    id = callback.data.split("product_info_")[-1]
    await callback.answer(text=f"Информация о товаре с идентификатором id: {id}")


@user_private_router.callback_query(F.data.startswith("product_delete_1"))
async def start_command(callback: types.CallbackQuery):
    id = callback.data.split("product_delete_")[-1]
    await callback.answer(text=f"Удалить товар с идентификатором id: {id}")


class LookingForParty(StatesGroup):
    part_number = State()
    year = State()
    more_information = State()

    texts = {
        'LookingForParty:part_number': "Введите номер партии заново",
        'LookingForParty:year': "Выбирите год заново",
        'LookingForParty:more_information': "Выбирете дополнительную информацию заново",
    }


@user_private_router.message(StateFilter('*'), Command("шаг назад"))
@user_private_router.message(StateFilter('*'), F.text.casefold() == "шаг назад")
async def back_to_find_party(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()

    if current_state is None:
        return

    if current_state == LookingForParty.year:
        await message.answer(
            text=LookingForParty.texts['LookingForParty:part_number'],
            reply_markup=get_keyboard("отмена")
        )
        await state.set_state(LookingForParty.part_number)

    # if year was entered
    if current_state == LookingForParty.more_information:
        await message.answer(
            text=LookingForParty.texts['LookingForParty:year'],
            reply_markup=get_keyboard(
                "24",
                "25",
                "отмена",
                "шаг назад"
            )
        )

        await state.set_state(LookingForParty.year)

    return


@user_private_router.message(StateFilter('*'), Command("отмена"))
@user_private_router.message(StateFilter('*'), F.text.casefold() == "отмена")
async def cancel_handler_find_party(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    await message.answer(
        "Действия отменены",
        reply_markup=types.ReplyKeyboardRemove()
    )


@user_private_router.message(StateFilter(None), Command('looking_for'))
async def set_part_number(message: types.Message, state: FSMContext):
    await message.answer(
        text="Введите номер партии для поиска",
        reply_markup=get_keyboard("отмена")
    )
    await state.set_state(LookingForParty.part_number)


@user_private_router.message(LookingForParty.part_number, F.text)
async def set_year_for_find_party(message: types.Message, state: FSMContext):
    await state.update_data(part_number=message.text)

    current_date = datetime.now()
    prev_year = current_date - timedelta(days=1 * 365)

    inline_years = [
        prev_year.strftime('%y'),
        current_date.strftime('%y'),
        "отмена",
        "шаг назад"
    ]

    await message.answer(
        text="Выберете год",
        reply_markup=get_keyboard(*inline_years)
    )
    await state.set_state(LookingForParty.year)


@user_private_router.message(LookingForParty.year, F.text)
async def send_request_find_party(message: types.Message, state: FSMContext):
    await state.update_data(year=message.text)

    await message.answer(
        text="Нужна дополнительная информация к партии (запрос займет немного больше времени)?",
        reply_markup=get_keyboard(*[
            "искать партию",
            "искать партию с цветом",
            "искать партию с ФИО",
            "отмена",
            "шаг назад"
        ], sizes=(1, 2))
    )
    await state.set_state(LookingForParty.more_information)


@user_private_router.message(StateFilter('*'), Command("искать партию"))
@user_private_router.message(StateFilter('*'), F.text.casefold() == "искать партию")
async def cancel_handler_find_party(message: types.Message, state: FSMContext) -> None:
    current_state: dict | LookingForParty = await state.get_data()

    code = f"{current_state["year"]}%{current_state["part_number"]}"

    await find_party(message, state, code)

    # await message.answer(
    #     "Ищу партию",
    #     reply_markup=types.ReplyKeyboardRemove()
    # )
    # try:
    #     async with httpx.AsyncClient() as client:
    #         await client.get(
    #             settings.LARAVEL_API_URL + apiUrls.executeCommand,
    #             params=DTORequest(
    #                 message=message,
    #                 part_number=code
    #             ).__dict__,
    #             timeout=10.0
    #         )
    # except Exception as e:
    #     logger.exception(e)
    #
    # await state.clear()


@user_private_router.message(StateFilter('*'), Command("искать партию с цветом"))
@user_private_router.message(StateFilter('*'), F.text.casefold() == "искать партию с цветом")
async def cancel_handler_find_party(message: types.Message, state: FSMContext) -> None:
    current_state: dict | LookingForParty = await state.get_data()
    code = f"{current_state["year"]}%{current_state["part_number"]}*"
    await find_party(message, state, code)


@user_private_router.message(StateFilter('*'), Command("искать партию с ФИО"))
@user_private_router.message(StateFilter('*'), F.text.casefold() == "искать партию с ФИО")
async def cancel_handler_find_party(message: types.Message, state: FSMContext) -> None:
    current_state: dict | LookingForParty = await state.get_data()
    code = f"{current_state["year"]}%{current_state["part_number"]}@"
    await find_party(message, state, code)


async def find_party(message: types.Message, state: FSMContext, code: str) -> None:
    await message.answer(
        "Ищу партию",
        reply_markup=types.ReplyKeyboardRemove()
    )
    try:
        async with httpx.AsyncClient() as client:
            await client.get(
                settings.LARAVEL_API_URL + apiUrls.executeCommand,
                params=DTORequest(
                    message=message,
                    part_number=code
                ).__dict__,
                timeout=10.0
            )
    except Exception as e:
        logger.exception(e)

    await state.clear()


# @user_private_router.message(F.text)
# async def start_command(message: types.Message):
#     try:
#         # response = requests.get(settings.LARAVEL_API_URL + apiUrls.executeCommand, DTORequest(message).__dict__)
#
#         async with httpx.AsyncClient() as client:
#             await client.get(
#                 settings.LARAVEL_API_URL + apiUrls.executeCommand, params=DTORequest(message).__dict__
#             )
#
#         # response = httpx.get(
#         #     settings.LARAVEL_API_URL + apiUrls.executeCommand,
#         #     params=DTORequest(message).__dict__
#         # )
#
#         # status_code = response.status_code
#     except Exception as e:
#         logger.critical(e)
#     await message.answer(text="Это магический фильтр")

# LARAVEL_API_URL = os.getenv('LARAVEL_API_URL')


# @user_private_router.message()
# async def echo(message: types.Message, bot: Bot):
#     if message.photo is not None:
#         if message.content_type == 'photo':
#             file_id = message.photo[2].file_id
#             photo_file = await bot.get_file(file_id)
#             # await send_message_to_service(LARAVEL_API_URL + "upload-photo",
#             #     payload={
#             #       "file": photo_file.file_path,
#             #     }
#             # )
#             async with httpx.AsyncClient() as client:
#                 response = await client.post("http://127.0.0.1:85/api/upload-photo", data={
#                   "file": photo_file.file_path,
#                 })
#         await message.answer("Фото загружено")
#         return
#     if message.document is not None:
#         if message.content_type == 'document':
#             await send_message_to_service("http://127.0.0.1:85/api/upload-document",
#                 payload={
#                     "file_id": message.document.file_id,
#                     "mime_type": message.document.mime_type,
#                 }
#             )
#         await message.answer("Документ загружен")
#         return
#     if message.contact is not None:
#         await message.answer(message.contact.phone_number)
#     else:
#         await message.answer(message.text)
#
#
# async def send_message_to_service(url: str, payload: dict):
#     async with httpx.AsyncClient() as client:
#         response = await client.post(url, data=payload)
#
#         return True
