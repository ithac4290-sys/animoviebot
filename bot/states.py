from aiogram.fsm.state import State, StatesGroup


class AddAnimeState(StatesGroup):
    title = State()           # Anime nomi
    poster = State()          # Poster (Rasm)
    status = State()          # Holati (Davom etmoqda / Tugallangan)
    episodes_count = State()  # Qismlar soni
    genres = State()          # Janrlari
    channel = State()         # Asosiy kanal username'i (@QorakleverS2)
    post_channel = State()    # Post qilinadigan kanal


class AddEpisodeState(StatesGroup):
    anime_id = State()        # Anime ID
    episode_num = State()     # Qism raqami
    video = State()           # Video fayl


class AddChannelState(StatesGroup):
    channel_id = State()      # Kanal ID yoki @username
    title = State()           # Kanal nomi
    invite_link = State()     # Kanal havolasi


class GiveVipState(StatesGroup):
    user_id = State()         # Foydalanuvchi ID
    days = State()            # Necha kunga VIP berish


class BroadcastState(StatesGroup):
    message = State()         # Tarqatiladigan xabar


class DeleteAnimeState(StatesGroup):
    anime_id = State()        # O'chiriladigan anime ID yoki nomi


class SearchAnimeState(StatesGroup):
    query = State()           # Qidiruv so'zi


class UserSearchState(StatesGroup):
    by_name = State()         # Anime nomi orqali qidiruv
    by_code = State()         # Kod orqali qidiruv
    by_image = State()        # Rasm orqali qidiruv


class VipPaymentState(StatesGroup):
    receipt = State()         # To'lov cheki (rasm)
