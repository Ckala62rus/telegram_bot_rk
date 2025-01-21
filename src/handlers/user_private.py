import logging
from datetime import datetime, timedelta

import httpx
from aiogram import types, Router, F
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy.ext.asyncio import AsyncSession

from api.dto_api import DTORequest
from api.urls import apiUrls
from bot_enums.admin_enums import AdminEnums
from bot_enums.user_enums import FindPartyText, FindPartyTypes
from config.configuration import settings
from database.models.models import User
from database.orm_query_user import get_user_by_telegram_id, add_user
from filters.chat_types import ChatTypeFilter, IsStuff
from kbds import reply
from kbds.reply import get_keyboard

user_private_router = Router()
user_private_router.message.filter(ChatTypeFilter(['private']), IsStuff())

logger = logging.getLogger(__name__)


@user_private_router.message(Command('about_me'))
async def about_me_command(message: types.Message, db_session: AsyncSession):
    user = await get_user_by_telegram_id(db_session, message.from_user.id)

    text = """
        *** Информация обо мне: ***
        Ник: {username}
        Телефонный номер: {phone}
        Телеграм id: {telegram_id}
        Уникальный номер id: {id}
    """.format(
        username=user.username,
        phone="Номер не указан" if user.phone_number is None else user.phone_number,
        telegram_id=user.telegram_id,
        id=user.id,
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
        current_date = datetime.now()
        prev_year = current_date - timedelta(days=1 * 365)

        await message.answer(
            text=LookingForParty.texts['LookingForParty:year'],
            reply_markup=get_keyboard(
                prev_year.strftime('%y'),
                current_date.strftime('%y'),
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
        str(FindPartyText.ACTIONS_CANCELED),
        reply_markup=types.ReplyKeyboardRemove()
    )


@user_private_router.message(StateFilter(None), Command('looking_for'))
@user_private_router.message(StateFilter(None), F.text.casefold() == str(FindPartyTypes.LOOKING_FOR))
async def set_part_number(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    await message.answer(
        text=str(FindPartyText.PLEASE_ENTER_PART_NUMBER),
        reply_markup=get_keyboard(str(FindPartyTypes.CANCEL))
    )
    await state.set_state(LookingForParty.part_number)


@user_private_router.message(LookingForParty.part_number, F.text)
async def set_year_for_find_party(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
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
        text=str(FindPartyText.CHOOSE_YEAR),
        reply_markup=get_keyboard(*inline_years)
    )
    await state.set_state(LookingForParty.year)


@user_private_router.message(LookingForParty.year, F.text)
async def send_request_find_party(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    await state.update_data(year=message.text)
    await message.answer(
        text=str(FindPartyText.ADDITION_INFORMATION),
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
    current_state = await state.get_state()
    current_state: dict | LookingForParty = await state.get_data()
    code = f"{current_state["year"]}%{current_state["part_number"]}"
    await find_party(message, state, code)


@user_private_router.message(LookingForParty.more_information, F.text.casefold() == str(FindPartyTypes.WITH_COLOR))
async def find_party_with_color(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    current_state: dict | LookingForParty = await state.get_data()
    code = f"{current_state["year"]}%{current_state["part_number"]}*"
    await find_party(message, state, code)


@user_private_router.message(LookingForParty.more_information, F.text.casefold() == str(FindPartyTypes.WITH_FIO))
async def find_party_with_fio(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    current_state: dict | LookingForParty = await state.get_data()
    code = f"{current_state["year"]}%{current_state["part_number"]}@"
    await find_party(message, state, code)


async def find_party(message: types.Message, state: FSMContext, code: str) -> None:
    await message.answer(
        str(FindPartyText.LOOKING_PARTY),
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


@user_private_router.message(Command("menu"))
async def admin_panel(
    message: types.Message,
    db_session: AsyncSession
):
    telegram_user_id = message.from_user.id
    buttons = [str(FindPartyTypes.LOOKING_FOR)]
    user: User = await get_user_by_telegram_id(db_session, telegram_user_id)

    if user.is_admin:
        buttons.append(str(AdminEnums.ADMIN_MENU))

    await message.answer("Меню", reply_markup=get_keyboard(*buttons))


# @user_private_router.message(F.text)
# async def start_command(message: types.Message):
#     await message.answer(text="Неизвестная команда")
