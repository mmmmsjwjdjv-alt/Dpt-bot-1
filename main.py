import asyncio
import os
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
)


# =========================================================
# CONFIG
# =========================================================

TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN = int(os.environ.get("ADMIN_ID", "0") or 0)

MAX_IN = 50 * 1024 * 1024
MAX_OUT = 50 * 1024 * 1024

# 6 hours
TIMEOUT = 6 * 60 * 60

# Official DPT location inside Docker
DPT_JAR = "/opt/dpt.jar"
SHELL_FILES = "/opt/shell-files"

DB = Path("/tmp/maxo.db")
ROOT = Path("/tmp/maxo_jobs")

ROOT.mkdir(parents=True, exist_ok=True)

# Only one DPT job at a time
SEM = asyncio.Semaphore(1)

enabled = True

# Users who pressed upload
upload_users = set()


# =========================================================
# DATABASE
# =========================================================

def db():
    conn = sqlite3.connect(DB)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            first TEXT,
            username TEXT,
            seen INTEGER
        )
        """
    )

    conn.commit()
    return conn


def add_user(user):
    if not user:
        return

    conn = db()

    conn.execute(
        """
        INSERT INTO users(
            id,
            first,
            username,
            seen
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT(id) DO UPDATE SET
            first=excluded.first,
            username=excluded.username,
            seen=excluded.seen
        """,
        (
            user.id,
            user.first_name or "",
            user.username or "",
            int(time.time()),
        ),
    )

    conn.commit()
    conn.close()


# =========================================================
# KEYBOARDS
# =========================================================

def main_keyboard(is_admin=False):
    rows = [
        [
            KeyboardButton(
                "🔴 آپلود فایل",
                style="danger"
            )
        ]
    ]

    if is_admin:
        rows.append(
            [
                KeyboardButton(
                    "🔴 مدیریت",
                    style="danger"
                )
            ]
        )

    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        is_persistent=True
    )


def admin_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔴 روشن / خاموش",
                    callback_data="toggle"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔴 کاربران",
                    callback_data="users"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔴 آمار",
                    callback_data="stats"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔴 پیام همگانی",
                    callback_data="broadcast"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔴 بستن",
                    callback_data="close"
                )
            ],
        ]
    )


# =========================================================
# OUTPUT
# =========================================================

def output_name():
    return "✧ 𝐂𝐑𝐄𝐀𝐓𝐄 𝐁𝐘 𝐌𝐀𝐗𝐎 ✧.apk"


# =========================================================
# FIND APK
# =========================================================

def find_apk(directory):
    directory = Path(directory)

    files = [
        p
        for p in directory.rglob("*.apk")
        if p.is_file() and p.stat().st_size > 0
    ]

    if not files:
        return None

    return max(
        files,
        key=lambda p: p.stat().st_mtime
    )


# =========================================================
# /START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    add_user(user)

    text = (
        "╭────────────────────╮\n"
        "        <b>MAXO DPT</b>\n"
        "╰────────────────────╯\n\n"
        "<b>محافظت حرفه‌ای APK با DPT Shell</b>\n\n"
        "فقط فایل <b>APK</b> را ارسال کنید.\n"
        "ZIP و 7Z پشتیبانی نمی‌شوند.\n\n"
        "برای شروع، روی دکمه <b>آپلود فایل</b> بزنید\n"
        "یا یک APK را ریپلای کرده و <code>/dpt</code> را ارسال کنید."
    )

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(
            user.id == ADMIN
        )
    )


# =========================================================
# ADMIN
# =========================================================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if user.id != ADMIN:
        return

    await update.message.reply_text(
        "<b>MAXO DPT — مدیریت</b>\n\n"
        "وضعیت سرویس را کنترل کنید:",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_keyboard()
    )


# =========================================================
# ADMIN CALLBACK
# =========================================================

async def callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    global enabled

    query = update.callback_query

    await query.answer()

    if query.from_user.id != ADMIN:
        return

    if query.data == "toggle":

        enabled = not enabled

        status = "فعال" if enabled else "خاموش"

        await query.edit_message_text(
            "<b>MAXO DPT</b>\n\n"
            f"وضعیت: <b>{status}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_keyboard()
        )

    elif query.data == "users":

        conn = db()

        count = conn.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        conn.close()

        await query.edit_message_text(
            f"<b>کاربران ثبت‌شده:</b> {count}",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_keyboard()
        )

    elif query.data == "stats":

        status = "فعال" if enabled else "خاموش"

        await query.edit_message_text(
            "<b>MAXO DPT</b>\n\n"
            f"<b>وضعیت:</b> {status}\n"
            "<b>حداکثر ورودی:</b> 50 MB\n"
            "<b>حداکثر خروجی:</b> 50 MB\n"
            "<b>پردازش همزمان:</b> 1",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_keyboard()
        )

    elif query.data == "broadcast":

        context.user_data["broadcast"] = True

        await query.edit_message_text(
            "<b>پیام همگانی</b>\n\n"
            "متن پیام را ارسال کنید.\n"
            "برای لغو: /cancel",
            parse_mode=ParseMode.HTML
        )

    elif query.data == "close":

        await query.delete_message()


# =========================================================
# TEXT
# =========================================================

async def text_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user

    add_user(user)

    text = update.message.text or ""

    # Broadcast
    if (
        user.id == ADMIN
        and context.user_data.pop("broadcast", False)
    ):

        conn = db()

        ids = [
            row[0]
            for row in conn.execute(
                "SELECT id FROM users"
            )
        ]

        conn.close()

        success = 0

        for uid in ids:

            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=text
                )

                success += 1

            except Exception:
                pass

            await asyncio.sleep(0.04)

        await update.message.reply_text(
            f"<b>پیام ارسال شد:</b> {success}",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard(True)
        )

        return

    # Upload button
    if text == "🔴 آپلود فایل":

        upload_users.add(user.id)

        await update.message.reply_text(
            "<b>فایل APK را ارسال کنید.</b>\n\n"
            "فقط APK قابل پردازش است.\n"
            "ZIP و 7Z پشتیبانی نمی‌شوند.",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard(
                user.id == ADMIN
            )
        )

        return

    # Admin button
    if (
        text == "🔴 مدیریت"
        and user.id == ADMIN
    ):

        await admin(update, context)


# =========================================================
# /DPT
# =========================================================

async def dpt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user

    add_user(user)

    if user.id != ADMIN:
        return

    replied = update.message.reply_to_message

    if (
        not replied
        or not replied.document
        or not (
            replied.document.file_name or ""
        ).lower().endswith(".apk")
    ):

        await update.message.reply_text(
            "روی یک فایل <b>APK</b> ریپلای کنید "
            "و <code>/dpt</code> را بزنید.",
            parse_mode=ParseMode.HTML
        )

        return

    await process(
        update,
        context,
        replied.document.file_id,
        replied.document.file_name
    )


# =========================================================
# DOCUMENT
# =========================================================

async def document(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user

    add_user(user)

    document = update.message.document

    name = document.file_name or "app.apk"

    # Only APK
    if not name.lower().endswith(".apk"):

        await update.message.reply_text(
            "فقط فایل <b>APK</b> قبول می‌شود.\n\n"
            "ZIP و 7Z پشتیبانی نمی‌شوند.",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard(
                user.id == ADMIN
            )
        )

        return

    # Normal users need upload button first
    if (
        user.id != ADMIN
        and user.id not in upload_users
    ):
        return

    upload_users.discard(user.id)

    await process(
        update,
        context,
        document.file_id,
        name
    )


# =========================================================
# PROCESS
# =========================================================

async def process(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    file_id,
    original_name
):
    global enabled

    if not enabled:

        await update.effective_message.reply_text(
            "سرویس DPT موقتاً خاموش است."
        )

        return

    # Check DPT installation
    if not os.path.isfile(DPT_JAR):

        await update.effective_message.reply_text(
            "خطای سرور: فایل DPT پیدا نشد."
        )

        if ADMIN:

            try:
                await context.bot.send_message(
                    ADMIN,
                    "<b>MAXO DPT ERROR</b>\n\n"
                    "dpt.jar پیدا نشد.",
                    parse_mode=ParseMode.HTML
                )

            except Exception:
                pass

        return

    # Check shell-files
    if not os.path.isdir(SHELL_FILES):

        await update.effective_message.reply_text(
            "خطای سرور: پوشه shell-files پیدا نشد."
        )

        if ADMIN:

            try:
                await context.bot.send_message(
                    ADMIN,
                    "<b>MAXO DPT ERROR</b>\n\n"
                    "/opt/shell-files پیدا نشد.",
                    parse_mode=ParseMode.HTML
                )

            except Exception:
                pass

        return

    msg = await update.effective_message.reply_text(
        "⏳ <b>MAXO DPT</b>\n\n"
        "در حال دریافت و آماده‌سازی APK...",
        parse_mode=ParseMode.HTML
    )

    job = Path(
        tempfile.mkdtemp(
            prefix="maxo_",
            dir=ROOT
        )
    )

    inp = job / "input.apk"
    out = job / "out"

    out.mkdir(parents=True, exist_ok=True)

    try:

        # =================================================
        # DOWNLOAD
        # =================================================

        telegram_file = await context.bot.get_file(
            file_id
        )

        await telegram_file.download_to_drive(
            inp
        )

        if not inp.exists():

            raise RuntimeError(
                "دانلود APK انجام نشد."
            )

        input_size = inp.stat().st_size

        if input_size > MAX_IN:

            raise RuntimeError(
                "حجم فایل بیشتر از 50MB است."
            )

        # =================================================
        # DPT
        # =================================================

        await msg.edit_text(
            "⚙️ <b>MAXO DPT</b>\n\n"
            "در حال اجرای DPT Shell...\n"
            "لطفاً تا پایان پردازش صبر کنید.",
            parse_mode=ParseMode.HTML
        )

        async with SEM:

            process = await asyncio.create_subprocess_exec(
                "java",
                "-jar",
                DPT_JAR,
                "-f",
                str(inp),
                "-o",
                str(out),

                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,

                cwd="/opt"
            )

            try:

                output, _ = await asyncio.wait_for(
                    process.communicate(),
                    timeout=TIMEOUT
                )

            except asyncio.TimeoutError:

                try:
                    process.kill()
                except Exception:
                    pass

                try:
                    await process.wait()
                except Exception:
                    pass

                raise RuntimeError(
                    "پردازش DPT بیش از زمان مجاز "
                    "طول کشید."
                )

        # =================================================
        # LOG
        # =================================================

        log = ""

        if output:

            try:
                log = output.decode(
                    "utf-8",
                    errors="replace"
                )
            except Exception:
                log = str(output)

        # =================================================
        # FIND OUTPUT
        # =================================================

        apk = find_apk(out)

        if not apk:

            error_log = log[-3000:]

            raise RuntimeError(
                "DPT خروجی APK تولید نکرد.\n\n"
                f"Exit code: {process.returncode}\n\n"
                f"{error_log}"
            )

        # =================================================
        # OUTPUT SIZE
        # =================================================

        output_size = apk.stat().st_size

        if output_size > MAX_OUT:

            raise RuntimeError(
                "حجم خروجی بیشتر از 50MB است."
            )

        if output_size <= 0:

            raise RuntimeError(
                "فایل خروجی APK خالی است."
            )

        # =================================================
        # SEND
        # =================================================

        await msg.edit_text(
            "✅ <b>پردازش با موفقیت انجام شد.</b>\n\n"
            "در حال ارسال فایل...",
            parse_mode=ParseMode.HTML
        )

        with apk.open("rb") as file:

            await update.effective_message.reply_document(
                document=file,
                filename=output_name(),
                caption="CREATE BY MAXO\n@Pv_MAXO"
            )

        try:
            await msg.delete()
        except Exception:
            pass

    except Exception as error:

        error_text = str(error)

        if not error_text:
            error_text = "خطای نامشخص"

        await msg.edit_text(
            "❌ <b>پردازش ناموفق بود.</b>\n\n"
            "<code>"
            + error_text[:3500]
            + "</code>",
            parse_mode=ParseMode.HTML
        )

        # Admin log
        if ADMIN:

            try:

                admin_log = (
                    "⚠️ <b>MAXO DPT ERROR</b>\n\n"
                    f"<b>User:</b> {update.effective_user.id}\n"
                    f"<b>File:</b> {original_name}\n\n"
                    f"<code>{error_text[:3500]}</code>"
                )

                await context.bot.send_message(
                    ADMIN,
                    admin_log,
                    parse_mode=ParseMode.HTML
                )

            except Exception:
                pass

    finally:

        # Always delete job files
        try:
            shutil.rmtree(
                job,
                ignore_errors=True
            )
        except Exception:
            pass


# =========================================================
# CANCEL
# =========================================================

async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    context.user_data.pop(
        "broadcast",
        None
    )

    await update.message.reply_text(
        "لغو شد.",
        reply_markup=main_keyboard(
            update.effective_user.id == ADMIN
        )
    )


# =========================================================
# MAIN
# =========================================================

def main():

    if not TOKEN:

        raise SystemExit(
            "BOT_TOKEN در Railway Variables تنظیم نشده است."
        )

    if not ADMIN:

        raise SystemExit(
            "ADMIN_ID در Railway Variables تنظیم نشده است."
        )

    # Initialize database
    db().close()

    # Verify DPT files during startup
    print("========================================")
    print("MAXO DPT")
    print("========================================")
    print(f"DPT JAR: {DPT_JAR}")
    print(f"DPT JAR EXISTS: {os.path.isfile(DPT_JAR)}")
    print(f"SHELL FILES: {SHELL_FILES}")
    print(f"SHELL FILES EXISTS: {os.path.isdir(SHELL_FILES)}")
    print("========================================")

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    # Commands
    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "dpt",
            dpt
        )
    )

    app.add_handler(
        CommandHandler(
            "admin",
            admin
        )
    )

    app.add_handler(
        CommandHandler(
            "cancel",
            cancel
        )
    )

    # Inline callbacks
    app.add_handler(
        CallbackQueryHandler(
            callback
        )
    )

    # APK / documents
    app.add_handler(
        MessageHandler(
            filters.Document.ALL,
            document
        )
    )

    # Text
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_message
        )
    )

    # Start bot
    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
