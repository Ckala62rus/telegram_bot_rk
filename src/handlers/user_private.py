import logging
from datetime import datetime, timedelta
from enum import StrEnum

import httpx
from aiogram import types, Router, F
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
from kbds import reply
from kbds.inline import get_callback_btns
from kbds.reply import get_keyboard

user_private_router = Router()
user_private_router.message.filter(ChatTypeFilter(['private']))

logger = logging.getLogger(__name__)


class FindPartyTypes(StrEnum):
    SIMPLE = "искать партию",
    WITH_COLOR = "искать партию с цветом",
    WITH_FIO = "искать с фио",
    CANCEL = "отмена",
    STEP_BACK = "шаг назад"


@user_private_router.message(CommandStart())
async def start_command(message: types.Message, db_session: AsyncSession):
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


@user_private_router.message(Command('phone'))
async def phone_command(message: types.Message):
    await message.answer(
        text="Отправьте свой номер телефона для регистрации",
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


class LookingForParty(StatesGroup):
    part_number = State()
    year = State()
    more_information = State()

    texts = {
        'LookingForParty:part_number': "Введите номер партии заново",
        'LookingForParty:year': "Выбирите год заново",
        'LookingForParty:more_information': "Выбирете дополнительную информацию заново",
    }


@user_private_router.message(StateFilter('*'), Command(str(FindPartyTypes.STEP_BACK)))
@user_private_router.message(StateFilter('*'), F.text.casefold() == str(FindPartyTypes.STEP_BACK))
async def back_to_find_party(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()

    if current_state is None:
        return

    if current_state == LookingForParty.year:
        await message.answer(
            text=LookingForParty.texts['LookingForParty:part_number'],
            reply_markup=get_keyboard(str(FindPartyTypes.CANCEL))
        )
        await state.set_state(LookingForParty.part_number)

    # if year was entered
    if current_state == LookingForParty.more_information:
        await message.answer(
            text=LookingForParty.texts['LookingForParty:year'],
            reply_markup=get_keyboard(
                "24",
                "25",
                str(FindPartyTypes.CANCEL),
                str(FindPartyTypes.STEP_BACK)
            )
        )

        await state.set_state(LookingForParty.year)

    return


@user_private_router.message(StateFilter('*'), F.text.casefold() == str(FindPartyTypes.CANCEL))
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
        reply_markup=get_keyboard(str(FindPartyTypes.CANCEL))
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
        str(FindPartyTypes.CANCEL),
        str(FindPartyTypes.STEP_BACK)
    ]

    await message.answer(
        text="Выберете год или введите две цифры нужного",
        reply_markup=get_keyboard(*inline_years)
    )
    await state.set_state(LookingForParty.year)


@user_private_router.message(LookingForParty.year, F.text)
async def send_request_find_party(message: types.Message, state: FSMContext):
    await state.update_data(year=message.text)
    await message.answer(
        text="Нужна дополнительная информация к партии (запрос займет немного больше времени)?",
        reply_markup=get_keyboard(*[
            str(FindPartyTypes.SIMPLE),
            str(FindPartyTypes.WITH_COLOR),
            str(FindPartyTypes.WITH_FIO),
            str(FindPartyTypes.CANCEL),
            str(FindPartyTypes.STEP_BACK)
        ], sizes=(1, 2))
    )
    await state.set_state(LookingForParty.more_information)


@user_private_router.message(LookingForParty.more_information, F.text.casefold() == str(FindPartyTypes.SIMPLE))
async def cancel_handler_find_party(message: types.Message, state: FSMContext) -> None:
    current_state: dict | LookingForParty = await state.get_data()
    code = f"{current_state["year"]}%{current_state["part_number"]}"
    await find_party(message, state, code)


@user_private_router.message(LookingForParty.more_information, F.text.casefold() == str(FindPartyTypes.WITH_COLOR))
async def find_party_with_color(message: types.Message, state: FSMContext) -> None:
    current_state: dict | LookingForParty = await state.get_data()
    code = f"{current_state["year"]}%{current_state["part_number"]}*"
    await find_party(message, state, code)


@user_private_router.message(LookingForParty.more_information, F.text.casefold() == str(FindPartyTypes.WITH_FIO))
async def find_party_with_fio(message: types.Message, state: FSMContext) -> None:
    current_state: dict | LookingForParty = await state.get_data()
    code = f"{current_state["year"]}%{current_state["part_number"]}@"
    await find_party(message, state, code)


async def find_party(message: types.Message, state: FSMContext, code: str) -> None:
    await message.answer(
        "Поиск партии...",
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
                timeout=30.0
            )
    except Exception as e:
        logger.exception(e)

    await state.clear()
