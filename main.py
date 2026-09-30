import asyncio
import os
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
)
from telegram import InlineKeyboardMarkup, InlineKeyboardButton


TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN = int(os.environ.get("ADMIN_ID", "0") or 0)

MAX_IN = 50 * 1024 * 1024
MAX_OUT = 50 * 1024 * 1024

# حداکثر زمان واقعی اجرای DPT
TIMEOUT = 6 * 60 * 60

# مسیر صحیحی که Dockerfile می‌سازد
DPT_JAR = "/opt/dpt.jar"

DB = Path("/tmp/maxo.db")
ROOT = Path("/tmp/maxo_jobs")

ROOT.mkdir(parents=True, exist_ok=True)

SEM = asyncio.Semaphore(1)
enabled = True
upload_users = set()


def db():
    c = sqlite3.connect(DB)

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            first TEXT,
            username TEXT,
            seen INTEGER
        )
    """)

    c.commit()
    return c


def add_user(u):
    c = db()

    c.execute("""
        INSERT INTO users(id, first, username, seen)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            first=excluded.first,
            username=excluded.username,
            seen=excluded.seen
    """, (
        u.id,
        u.first_name or "",
        u.username or "",
        int(time.time())
    ))

    c.commit()
    c.close()


def kb(admin=False):
    rows = [
        [
            KeyboardButton(
                "🔴 آپلود فایل",
                style="danger"
            )
        ]
    ]

    if admin:
        rows.append([
            KeyboardButton(
                "🔴 مدیریت",
                style="danger"
            )
        ])

    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        is_persistent=True
    )


def admin_kb():
    return InlineKeyboardMarkup([
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
        ]
    ])


def outname():
    return "✧ 𝐂𝐑𝐄𝐀𝐓𝐄 𝐁𝐘 𝐌𝐀𝐗𝐎 ✧.apk"


def find_apk(directory):
    candidates = []

    directory = Path(directory)

    if not directory.exists():
        return None

    for p in directory.rglob("*.apk"):
        try:
            if not p.is_file():
                continue

            size = p.stat().st_size

            if size <= 0:
                continue

            if size > MAX_OUT:
                continue

            candidates.append(p)

        except Exception:
            pass

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda x: x.stat().st_mtime
    )


def valid_apk(path):
    if not path:
        return False

    path = Path(path)

    try:
        if not path.is_file():
            return False

        if path.stat().st_size <= 0:
            return False

        if path.stat().st_size > MAX_OUT:
            return False

        import zipfile

        if not zipfile.is_zipfile(path):
            return False

        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())

            if "AndroidManifest.xml" in names:
                return True

            for name in names:
                if name.endswith("/AndroidManifest.xml"):
                    return True

        return False

    except Exception:
        return False


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    add_user(update.effective_user)

    await update.message.reply_text(
        """
╭────────────────────╮
        <b>MAXO DPT</b>
╰────────────────────╯

<b>محافظت حرفه‌ای APK با DPT Shell</b>

فقط فایل <b>APK</b> را ارسال کنید.
ZIP و 7Z پشتیبانی نمی‌شوند.

برای شروع، روی دکمه <b>آپلود فایل</b> بزنید
یا یک APK را ریپلای کرده و <code>/dpt</code> را ارسال کنید.
""",
        parse_mode=ParseMode.HTML,
        reply_markup=kb(
            update.effective_user.id == ADMIN
        )
    )


async def admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN:
        return

    await update.message.reply_text(
        "<b>MAXO DPT — مدیریت</b>\n\n"
        "وضعیت سرویس را کنترل کنید.",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_kb()
    )


async def callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global enabled

    q = update.callback_query

    await q.answer()

    if q.from_user.id != ADMIN:
        return

    if q.data == "toggle":

        enabled = not enabled

        await q.edit_message_text(
            "<b>MAXO DPT</b>\n\n"
            f"وضعیت: <b>{'فعال' if enabled else 'خاموش'}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_kb()
        )

    elif q.data == "users":

        c = db()

        rows = c.execute("""
            SELECT id, first, username
            FROM users
            ORDER BY seen DESC
            LIMIT 100
        """).fetchall()

        total = c.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        c.close()

        lines = [
            f"<b>تعداد کاربران: {total}</b>",
            ""
        ]

        for i, row in enumerate(rows, 1):

            uid = row[0]
            first = row[1] or "بدون نام"
            username = (
                "@" + row[2]
                if row[2]
                else "بدون یوزرنیم"
            )

            lines.append(
                f"{i}. <code>{uid}</code> — "
                f"{first} — {username}"
            )

        result = "\n".join(lines)

        if len(result) > 3900:
            result = result[:3800] + "\n\n<i>۱۰۰ کاربر اخیر</i>"

        await q.edit_message_text(
            result,
            parse_mode=ParseMode.HTML,
            reply_markup=admin_kb()
        )

    elif q.data == "stats":

        c = db()

        users = c.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        c.close()

        await q.edit_message_text(
            "<b>MAXO DPT STATS</b>\n\n"
            f"کاربران: <b>{users}</b>\n"
            f"وضعیت: <b>{'فعال' if enabled else 'خاموش'}</b>\n"
            "حداکثر ورودی: <b>50 MB</b>\n"
            "حداکثر خروجی: <b>50 MB</b>\n"
            "پردازش همزمان: <b>1</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_kb()
        )

    elif q.data == "broadcast":

        ctx.user_data["broadcast"] = True

        await q.edit_message_text(
            "<b>پیام همگانی</b>\n\n"
            "متن پیام را ارسال کنید.\n"
            "برای لغو <code>/cancel</code> را بزنید.",
            parse_mode=ParseMode.HTML
        )

    elif q.data == "close":

        await q.delete_message()


async def text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    u = update.effective_user

    add_user(u)

    t = update.message.text or ""

    if (
        u.id == ADMIN
        and ctx.user_data.get("broadcast")
    ):

        ctx.user_data.pop("broadcast", None)

        c = db()

        ids = [
            x[0]
            for x in c.execute(
                "SELECT id FROM users"
            ).fetchall()
        ]

        c.close()

        ok = 0

        for uid in ids:

            try:
                await ctx.bot.send_message(
                    chat_id=uid,
                    text=t
                )

                ok += 1

            except Exception:
                pass

            await asyncio.sleep(0.04)

        await update.message.reply_text(
            f"<b>پیام ارسال شد:</b> {ok}",
            parse_mode=ParseMode.HTML,
            reply_markup=kb(True)
        )

        return

    if t == "🔴 آپلود فایل":

        upload_users.add(u.id)

        await update.message.reply_text(
            "<b>فایل APK را ارسال کنید.</b>\n\n"
            "حداکثر حجم: <b>50 MB</b>\n"
            "ZIP و 7Z پشتیبانی نمی‌شوند.",
            parse_mode=ParseMode.HTML,
            reply_markup=kb(
                u.id == ADMIN
            )
        )

        return

    if (
        t == "🔴 مدیریت"
        and u.id == ADMIN
    ):

        await admin(update, ctx)


async def dpt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    u = update.effective_user

    add_user(u)

    if u.id != ADMIN:
        return

    r = update.message.reply_to_message

    if (
        not r
        or not r.document
        or not (
            r.document.file_name or ""
        ).lower().endswith(".apk")
    ):

        await update.message.reply_text(
            "روی یک فایل <b>APK</b> ریپلای کنید "
            "و سپس /dpt را بزنید.",
            parse_mode=ParseMode.HTML
        )

        return

    await process(
        update,
        ctx,
        r.document.file_id,
        r.document.file_name
    )


async def document(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE
):

    u = update.effective_user

    add_user(u)

    doc = update.message.document

    name = doc.file_name or "app.apk"

    if not name.lower().endswith(".apk"):

        await update.message.reply_text(
            "فقط فایل <b>APK</b> قبول می‌شود.",
            parse_mode=ParseMode.HTML,
            reply_markup=kb(
                u.id == ADMIN
            )
        )

        return

    if (
        u.id != ADMIN
        and u.id not in upload_users
    ):
        return

    upload_users.discard(u.id)

    await process(
        update,
        ctx,
        doc.file_id,
        name
    )


async def process(
    update,
    ctx,
    file_id,
    name
):

    global enabled

    if not enabled:

        await update.effective_message.reply_text(
            "سرویس DPT موقتاً خاموش است."
        )

        return

    msg = await update.effective_message.reply_text(
        "<b>MAXO DPT</b>\n\n"
        "در حال دریافت APK...",
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

    out.mkdir()

    try:

        # دانلود APK
        f = await ctx.bot.get_file(file_id)

        await f.download_to_drive(
            custom_path=str(inp)
        )

        if not inp.exists():
            raise RuntimeError(
                "دانلود APK انجام نشد."
            )

        input_size = inp.stat().st_size

        if input_size <= 0:
            raise RuntimeError(
                "فایل APK خالی است."
            )

        if input_size > MAX_IN:
            raise RuntimeError(
                "حجم فایل بیشتر از 50 MB است."
            )

        await msg.edit_text(
            "<b>MAXO DPT</b>\n\n"
            "APK دریافت شد.\n"
            "در حال اجرای DPT Shell...\n\n"
            "<i>لطفاً تا پایان پردازش صبر کنید.</i>",
            parse_mode=ParseMode.HTML
        )

        async with SEM:

            if not Path(DPT_JAR).is_file():
                raise RuntimeError(
                    f"DPT JAR پیدا نشد: {DPT_JAR}"
                )

            # اجرای واقعی DPT
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
                start_new_session=True
            )

            try:

                output, _ = await asyncio.wait_for(
                    process.communicate(),
                    timeout=TIMEOUT
                )

            except asyncio.TimeoutError:

                try:
                    os.killpg(
                        process.pid,
                        9
                    )
                except Exception:

                    try:
                        process.kill()
                    except Exception:
                        pass

                try:
                    await process.wait()
                except Exception:
                    pass

                raise RuntimeError(
                    "اجرای DPT بیشتر از 6 ساعت طول کشید."
                )

            log = (
                output.decode(
                    "utf-8",
                    errors="replace"
                )
                if output
                else ""
            )

            apk = find_apk(out)

            # مهم:
            # اگر DPT خروجی معتبر ساخته باشد،
            # صرفاً non-zero بودن return code باعث
            # حذف نتیجه نمی‌شود.
            if not apk:

                details = log[-2500:]

                if process.returncode != 0:

                    raise RuntimeError(
                        "DPT با خطا متوقف شد.\n\n"
                        + details
                    )

                raise RuntimeError(
                    "DPT اجرا شد اما خروجی APK پیدا نشد.\n\n"
                    + details
                )

            if not valid_apk(apk):

                raise RuntimeError(
                    "فایل خروجی APK معتبر نیست."
                )

            if (
                apk.stat().st_size
                > MAX_OUT
            ):

                raise RuntimeError(
                    "حجم خروجی بیشتر از 50 MB است."
                )

        await msg.edit_text(
            "<b>MAXO DPT</b>\n\n"
            "محافظت با موفقیت انجام شد.\n"
            "در حال ارسال فایل...",
            parse_mode=ParseMode.HTML
        )

        with apk.open("rb") as fh:

            await update.effective_message.reply_document(
                document=fh,
                filename=outname(),
                caption="CREATE BY MAXO\n@Pv_MAXO"
            )

        try:
            await msg.delete()
        except Exception:
            pass

    except Exception as e:

        error_text = str(e)

        if len(error_text) > 3000:
            error_text = error_text[-3000:]

        await msg.edit_text(
            "<b>MAXO DPT</b>\n\n"
            "پردازش ناموفق بود.\n\n"
            f"<code>{error_text}</code>",
            parse_mode=ParseMode.HTML
        )

        if ADMIN:

            try:

                await ctx.bot.send_message(
                    chat_id=ADMIN,
                    text=(
                        "⚠️ <b>MAXO DPT ERROR</b>\n\n"
                        f"User: <code>{update.effective_user.id}</code>\n"
                        f"File: <code>{name}</code>\n\n"
                        f"<code>{error_text}</code>"
                    ),
                    parse_mode=ParseMode.HTML
                )

            except Exception:
                pass

    finally:

        # تمام فایل‌های این Job حذف می‌شوند
        shutil.rmtree(
            job,
            ignore_errors=True
        )


async def cancel(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE
):

    ctx.user_data.pop(
        "broadcast",
        None
    )

    await update.message.reply_text(
        "لغو شد.",
        reply_markup=kb(
            update.effective_user.id == ADMIN
        )
    )


def main():

    if not TOKEN or not ADMIN:

        raise SystemExit(
            "BOT_TOKEN و ADMIN_ID را در Railway Variables تنظیم کنید."
        )

    db().close()

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

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

    app.add_handler(
        CallbackQueryHandler(
            callback
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Document.ALL,
            document
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text
        )
    )

    print("MAXO DPT BOT STARTED")

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()