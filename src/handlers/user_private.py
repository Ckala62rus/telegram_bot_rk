import json
import logging
import os

import httpx
from aiogram import types, Router, F, Bot
from aiogram.filters import CommandStart, Command
from sqlalchemy.ext.asyncio import AsyncSession
from database.orm_query_user import get_user_by_telegram_id, add_user, \
    update_phone_user
from filters.chat_types import ChatTypeFilter
from kbds import reply
from kbds.inline import get_callback_btns

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


# @user_private_router.message(F.text)
# async def start_command(message: types.Message):
#     await message.answer(text="Это магический фильтр")


LARAVEL_API_URL = os.getenv('LARAVEL_API_URL')


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
