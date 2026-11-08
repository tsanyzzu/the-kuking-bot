import logging
from typing import Any
from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.enums import ChatAction
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

router = Router(name="kuking_bot_router")

START_HELP_TEXT = (
    "*Halo! Saya Kuking, Asisten Dapur & Belanja Anda.*\n\n"
    "Berikut beberapa hal yang bisa saya bantu:\n\n"
    "*Pencatatan Belanja:*\n"
    "Kirim daftar belanjaan pasar/supermarket Anda dalam kalimat santai.\n"
    "_Contoh: \"Tadi beli dada ayam 25rb setengah kilo, tempe 5rb, sama sawi 3rb\"_\n"
    "Bahan makanan akan otomatis dicatat ke isi kulkas Anda!\n\n"
    "*Cek Kulkas (Pantry):*\n"
    "Tanyakan bahan apa yang tersedia, atau ketik /pantry.\n"
    "_Contoh: \"Di kulkas ada bahan apa aja?\"_\n\n"
    "*Rekomendasi Resep:*\n"
    "Minta ide masakan dari bahan yang ada di kulkas Anda.\n"
    "_Contoh: \"Kasih ide masakan berkuah dari bahan di kulkas tadi dong\"_\n"
)

@router.message(CommandStart())
async def handle_start(message: types.Message):
    await message.answer(START_HELP_TEXT, parse_mode="Markdown")

@router.message(Command("help"))
async def handle_help(message: types.Message):
    await message.answer(START_HELP_TEXT, parse_mode="Markdown")

@router.message(Command("pantry"))
async def handle_pantry_command(message: types.Message, agent: Any):
    user_id = message.from_user.id if message.from_user else message.chat.id
    await process_user_query(message, agent, "Kira-kira di kulkas saya ada bahan apa aja ya sekarang?", user_id)

@router.message(F.text)
async def handle_user_text(message: types.Message, agent: Any):
    user_id = message.from_user.id if message.from_user else message.chat.id
    user_text = message.text.strip() if message.text else ""
    if not user_text:
        return
    await process_user_query(message, agent, user_text, user_id)

async def process_user_query(message: types.Message, agent: Any, user_query: str, user_id: int):
    try:
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    except Exception as e:
        logger.warning(f"Gagal mengirim chat action typing: {e}")

    try:
        config = {"configurable": {"thread_id": str(user_id)}}
        result = await agent.ainvoke(
            {
                "messages": [HumanMessage(content=user_query)],
                "telegram_user_id": user_id,
            },
            config=config,
        )

        bot_reply = result["messages"][-1].content
        
        # try to reply with md, fallback to plain text
        try:
            await message.answer(bot_reply, parse_mode="Markdown")
        except Exception:
            await message.answer(bot_reply)

    except Exception as e:
        logger.exception(f"Error saat memproses query dari user {user_id}: {e}")
        await message.answer(
            "⚠️ *Maaf, terjadi kendala saat memproses permintaan Anda.*\n"
            "Silakan coba beberapa saat lagi.",
            parse_mode="Markdown"
        )