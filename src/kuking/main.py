import sys
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, Header, HTTPException, status
from fastapi.responses import JSONResponse
from aiogram import Bot, Dispatcher, types

from kuking.config import settings
from kuking.db import init_db_pool
from kuking.graph import create_cooking_agent
from kuking.bot import router as bot_router

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        import uvicorn.loops.asyncio
        uvicorn.loops.asyncio.asyncio_loop_factory = lambda use_subprocess=False: asyncio.SelectorEventLoop
    except ImportError:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("kuking.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Memulai inisialisasi koneksi database & state machine LangGraph...")
    pool = await init_db_pool()
    agent, checkpointer_conn = await create_cooking_agent(pool)
    
    bot: Optional[Bot] = None
    dp: Optional[Dispatcher] = None

    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning(
            "TELEGRAM_BOT_TOKEN belum diset di environment (.env). "
            "Server HTTP tetap aktif, namun integrasi Telegram dinonaktifkan."
        )
    else:
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        dp = Dispatcher()
        dp.include_router(bot_router)
        dp.workflow_data["agent"] = agent

        if settings.WEBHOOK_URL:
            webhook_full_url = f"{settings.WEBHOOK_URL.rstrip('/')}{settings.WEBHOOK_PATH}"
            logger.info(f"Mendaftarkan webhook Telegram ke: {webhook_full_url}")
            try:
                await bot.set_webhook(
                    url=webhook_full_url,
                    secret_token=settings.WEBHOOK_SECRET,
                    drop_pending_updates=True,
                )
                logger.info("Webhook Telegram berhasil didaftarkan.")
            except Exception as e:
                logger.error(f"Gagal mendaftarkan webhook ke Telegram: {e}")
        else:
            logger.info("WEBHOOK_URL tidak ditentukan. Pendaftaran webhook otomatis dilewati.")

    app.state.pool = pool
    app.state.agent = agent
    app.state.checkpointer_conn = checkpointer_conn
    app.state.bot = bot
    app.state.dp = dp

    logger.info(f"Kuking Application siap beroperasi pada {settings.HOST}:{settings.PORT}")
    yield

    logger.info("Memulai proses graceful shutdown...")
    if bot:
        try:
            if settings.WEBHOOK_URL:
                logger.info("Menghapus webhook Telegram...")
                await bot.delete_webhook()
            await bot.session.close()
            logger.info("Sesi bot Telegram ditutup.")
        except Exception as e:
            logger.error(f"Error saat menutup sesi bot: {e}")

    try:
        await checkpointer_conn.close()
        logger.info("Koneksi checkpointer database ditutup.")
    except Exception as e:
        logger.error(f"Error saat menutup checkpointer: {e}")

    try:
        await pool.close()
        logger.info("Connection pool asyncpg ditutup.")
    except Exception as e:
        logger.error(f"Error saat menutup pool database: {e}")

app = FastAPI(
    title="Kuking - Cooking & Expense Assistant",
    version="0.1.0",
    lifespan=lifespan
)

@app.get("/health")
async def health_check():
    """Endpoint health check untuk Hugging Face Spaces & external keep-alive ping."""
    return {
        "status": "healthy",
        "app": "kuking",
        "version": "0.1.0"
    }

@app.post(settings.WEBHOOK_PATH)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None, alias="X-Telegram-Bot-Api-Secret-Token")
):
    """Endpoint penerima webhook dari Telegram Bot API."""
    bot: Optional[Bot] = getattr(request.app.state, "bot", None)
    dp: Optional[Dispatcher] = getattr(request.app.state, "dp", None)

    if not bot or not dp:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot Telegram belum terkonfigurasi pada server ini."
        )

    # Validasi secret 
    if settings.WEBHOOK_SECRET and x_telegram_bot_api_secret_token != settings.WEBHOOK_SECRET:
        logger.warning("Request webhook ditolak: secret token tidak cocok.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid secret token"
        )

    try:
        payload = await request.json()
        update = types.Update.model_validate(payload, context={"bot": bot})
        await dp.feed_update(bot, update)
        return {"ok": True}
    except Exception as e:
        logger.exception(f"Error saat memproses update webhook: {e}")
        return JSONResponse(status_code=status.HTTP_200_OK, content={"ok": False, "error": str(e)})

def run():
    """Fungsi pembantu untuk menjalankan server uvicorn."""
    import uvicorn
    loop_param = "asyncio:SelectorEventLoop" if sys.platform == "win32" else "auto"
    uvicorn.run(
        "kuking.main:app",
        host=settings.HOST,
        port=settings.PORT,
        loop=loop_param,
        reload=False
    )

if __name__ == "__main__":
    run()