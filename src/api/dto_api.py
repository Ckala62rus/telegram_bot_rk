from aiogram import types


class DTORequest:
    def __init__(self, message: types.Message):
        self.code_for_looking = message.text
        self.telegram_user_id = message.from_user.id
