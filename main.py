import asyncio
import html
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TOKEN = os.environ.get("BOT_TOKEN", "").strip()
try:
    ADMIN = int(os.environ.get("ADMIN_ID", "0"))
except ValueError:
    ADMIN = 0

MAX_INPUT = 20 * 1024 * 1024
MAX_OUTPUT = 20 * 1024 * 1024
DPT_TIMEOUT = 6 * 60 * 60
DPT_JAR = "/opt/dpt.jar"
SHELL_FILES = "/opt/shell-files"
DB_PATH = "/tmp/maxo.db"
JOBS_DIR = "/tmp/maxo_jobs"
os.makedirs(JOBS_DIR, exist_ok=True)

LANGS = {
 "fa":{"upload":"آپلود APK","language":"زبان","admin":"پنل مدیریت","choose":"زبان خود را انتخاب کنید:","ready":"آماده است. فایل APK را ارسال کنید.","only_apk":"فقط فایل APK مجاز است.","too_big":"حجم APK نباید بیشتر از 20MB باشد.","blocked":"دسترسی شما مسدود شده است.","disabled":"پردازش APK در حال حاضر غیرفعال است.","processing":"در حال پردازش APK...","success":"پردازش با موفقیت انجام شد.","failed":"پردازش APK ناموفق بود.","admin_panel":"پنل مدیریت MAXO DPT","enable":"فعال کردن پردازش","disable":"غیرفعال کردن پردازش","users":"کاربران","stats":"آمار","broadcast":"ارسال همگانی","close":"بستن","back":"بازگشت","block":"مسدود کردن","unblock":"رفع مسدودی","active":"فعال","blocked_status":"مسدود","broadcast_prompt":"پیامی که می‌خواهید برای کاربران ارسال شود را بفرستید."},
 "en":{"upload":"Upload APK","language":"Language","admin":"Admin Panel","choose":"Choose your language:","ready":"Ready. Send the APK file.","only_apk":"Only APK files are allowed.","too_big":"APK size must not exceed 20MB.","blocked":"Your access is blocked.","disabled":"APK processing is currently disabled.","processing":"Processing APK...","success":"Processing completed successfully.","failed":"APK processing failed.","admin_panel":"MAXO DPT Admin Panel","enable":"Enable Processing","disable":"Disable Processing","users":"Users","stats":"Stats","broadcast":"Broadcast","close":"Close","back":"Back","block":"Block","unblock":"Unblock","active":"Active","blocked_status":"Blocked","broadcast_prompt":"Send the message you want to broadcast."},
 "zh":{"upload":"上传 APK","language":"语言","admin":"管理面板","choose":"请选择语言：","ready":"准备就绪，请发送 APK 文件。","only_apk":"只允许 APK 文件。","too_big":"APK 大小不能超过 20MB。","blocked":"您的访问已被封锁。","disabled":"APK 处理目前已关闭。","processing":"正在处理 APK...","success":"处理成功。","failed":"APK 处理失败。","admin_panel":"MAXO DPT 管理面板","enable":"启用处理","disable":"关闭处理","users":"用户","stats":"统计","broadcast":"群发","close":"关闭","back":"返回","block":"封锁","unblock":"解除封锁","active":"正常","blocked_status":"已封锁","broadcast_prompt":"请发送要群发的消息。"},
 "hi":{"upload":"APK अपलोड","language":"भाषा","admin":"एडमिन पैनल","choose":"भाषा चुनें:","ready":"तैयार है। APK फ़ाइल भेजें।","only_apk":"केवल APK फ़ाइलें स्वीकार हैं।","too_big":"APK का आकार 20MB से अधिक नहीं होना चाहिए।","blocked":"आपकी पहुंच ब्लॉक है।","disabled":"APK प्रोसेसिंग अभी बंद है।","processing":"APK प्रोसेस हो रहा है...","success":"प्रोसेसिंग सफल रही।","failed":"APK प्रोसेसिंग विफल हुई।","admin_panel":"MAXO DPT एडमिन पैनल","enable":"प्रोसेसिंग चालू","disable":"प्रोसेसिंग बंद","users":"यूज़र","stats":"आंकड़े","broadcast":"ब्रॉडकास्ट","close":"बंद","back":"वापस","block":"ब्लॉक करें","unblock":"अनब्लॉक करें","active":"सक्रिय","blocked_status":"ब्लॉक","broadcast_prompt":"ब्रॉडकास्ट करने वाला संदेश भेजें।"},
 "ar":{"upload":"رفع APK","language":"اللغة","admin":"لوحة الإدارة","choose":"اختر لغتك:","ready":"جاهز. أرسل ملف APK.","only_apk":"يسمح بملفات APK فقط.","too_big":"يجب ألا يتجاوز حجم APK ‏20MB.","blocked":"تم حظر وصولك.","disabled":"المعالجة متوقفة حالياً.","processing":"جارٍ معالجة APK...","success":"اكتملت المعالجة بنجاح.","failed":"فشلت معالجة APK.","admin_panel":"لوحة إدارة MAXO DPT","enable":"تفعيل المعالجة","disable":"تعطيل المعالجة","users":"المستخدمون","stats":"الإحصائيات","broadcast":"إذاعة","close":"إغلاق","back":"رجوع","block":"حظر","unblock":"إلغاء الحظر","active":"نشط","blocked_status":"محظور","broadcast_prompt":"أرسل الرسالة التي تريد إذاعتها."}
}

def db():
    c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; return c

def init_db():
    c=db()
    c.execute("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,first_name TEXT DEFAULT '',username TEXT DEFAULT '',language TEXT DEFAULT 'en',blocked INTEGER DEFAULT 0,registered_at TEXT,last_seen TEXT,total_jobs INTEGER DEFAULT 0,successful_jobs INTEGER DEFAULT 0,failed_jobs INTEGER DEFAULT 0)""")
    c.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT)")
    c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('enabled','1')")
    c.commit(); c.close()

def ensure_user(u):
    now=datetime.utcnow().isoformat(); c=db()
    if c.execute("SELECT 1 FROM users WHERE id=?",(u.id,)).fetchone():
        c.execute("UPDATE users SET first_name=?,username=?,last_seen=? WHERE id=?",(u.first_name or '',u.username or '',now,u.id))
    else:
        c.execute("INSERT INTO users(id,first_name,username,language,registered_at,last_seen) VALUES(?,?,?,?,?,?)",(u.id,u.first_name or '',u.username or '','en',now,now))
    c.commit(); c.close()

def get_user(uid):
    c=db(); r=c.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone(); c.close(); return r

def lang_of(uid):
    r=get_user(uid); return r['language'] if r and r['language'] in LANGS else 'en'

def t(uid,k): return LANGS[lang_of(uid)].get(k,LANGS['en'].get(k,k))

def is_blocked(uid):
    r=get_user(uid); return bool(r and r['blocked'])

def set_block(uid,v):
    c=db(); c.execute("UPDATE users SET blocked=? WHERE id=?",(1 if v else 0,uid)); c.commit(); c.close()

def set_lang(uid,l):
    c=db(); c.execute("UPDATE users SET language=? WHERE id=?",(l,uid)); c.commit(); c.close()

def enabled():
    c=db(); r=c.execute("SELECT value FROM settings WHERE key='enabled'").fetchone(); c.close(); return bool(r and r['value']=='1')

def set_enabled(v):
    c=db(); c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('enabled',?)",('1' if v else '0',)); c.commit(); c.close()

def job_stat(uid,ok):
    c=db(); c.execute("UPDATE users SET total_jobs=total_jobs+1 WHERE id=?",(uid,)); c.execute("UPDATE users SET {}= {}+1 WHERE id=?".format('successful_jobs' if ok else 'failed_jobs','successful_jobs' if ok else 'failed_jobs'),(uid,)); c.commit(); c.close()

def lang_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton('فارسی',callback_data='lang:fa'),InlineKeyboardButton('English',callback_data='lang:en')],[InlineKeyboardButton('中文',callback_data='lang:zh'),InlineKeyboardButton('हिन्दी',callback_data='lang:hi')],[InlineKeyboardButton('العربية',callback_data='lang:ar')]])

def main_keyboard(uid):
    rows=[[InlineKeyboardButton(t(uid,'upload'),callback_data='upload'),InlineKeyboardButton(t(uid,'language'),callback_data='language')]]
    if uid==ADMIN: rows.append([InlineKeyboardButton(t(uid,'admin'),callback_data='admin')])
    return InlineKeyboardMarkup(rows)

def admin_keyboard(uid):
    label=t(uid,'disable') if enabled() else t(uid,'enable')
    return InlineKeyboardMarkup([[InlineKeyboardButton(label,callback_data='adm:toggle')],[InlineKeyboardButton(t(uid,'users'),callback_data='adm:users'),InlineKeyboardButton(t(uid,'stats'),callback_data='adm:stats')],[InlineKeyboardButton(t(uid,'broadcast'),callback_data='adm:broadcast')],[InlineKeyboardButton(t(uid,'close'),callback_data='adm:close')]])

async def start(update,context):
    ensure_user(update.effective_user); context.user_data.pop('broadcast',None)
    await update.message.reply_text('MAXO DPT\n\n'+LANGS['en']['choose'],reply_markup=lang_keyboard())

async def callbacks(update,context):
    q=update.callback_query; await q.answer(); u=q.from_user; ensure_user(u); uid=u.id
    d=q.data
    if d.startswith('lang:'):
        code=d.split(':',1)[1]
        if code in LANGS: set_lang(uid,code)
        await q.edit_message_text('<b>MAXO DPT</b>\n\n'+html.escape(t(uid,'ready')),parse_mode=ParseMode.HTML,reply_markup=main_keyboard(uid)); return
    if d=='language': await q.edit_message_text(LANGS['en']['choose'],reply_markup=lang_keyboard()); return
    if d=='upload': await q.answer(t(uid,'ready'),show_alert=True); return
    if uid!=ADMIN: return
    if d=='admin': await q.edit_message_text('<b>'+t(uid,'admin_panel')+'</b>',parse_mode=ParseMode.HTML,reply_markup=admin_keyboard(uid))
    elif d=='adm:toggle': set_enabled(not enabled()); await q.edit_message_text('<b>'+t(uid,'admin_panel')+'</b>',parse_mode=ParseMode.HTML,reply_markup=admin_keyboard(uid))
    elif d=='adm:stats':
        c=db(); users=c.execute('SELECT COUNT(*) n FROM users').fetchone()['n']; blocked=c.execute('SELECT COUNT(*) n FROM users WHERE blocked=1').fetchone()['n']; jobs=c.execute('SELECT COALESCE(SUM(total_jobs),0) n FROM users').fetchone()['n']; ok=c.execute('SELECT COALESCE(SUM(successful_jobs),0) n FROM users').fetchone()['n']; bad=c.execute('SELECT COALESCE(SUM(failed_jobs),0) n FROM users').fetchone()['n']; c.close()
        text=f'<b>{t(uid,"stats")}</b>\n\nUsers: <b>{users}</b>\nBlocked: <b>{blocked}</b>\nJobs: <b>{jobs}</b>\nSuccessful: <b>{ok}</b>\nFailed: <b>{bad}</b>'
        await q.edit_message_text(text,parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(uid,'back'),callback_data='admin')]]))
    elif d=='adm:users': await show_users(q,0)
    elif d.startswith('adm:users:'): await show_users(q,int(d.rsplit(':',1)[1]))
    elif d.startswith('adm:user:'): await show_user(q,int(d.rsplit(':',1)[1]))
    elif d.startswith('adm:block:'): set_block(int(d.rsplit(':',1)[1]),True); await show_user(q,int(d.rsplit(':',1)[1]))
    elif d.startswith('adm:unblock:'): set_block(int(d.rsplit(':',1)[1]),False); await show_user(q,int(d.rsplit(':',1)[1]))
    elif d=='adm:broadcast': context.user_data['broadcast']=True; await q.edit_message_text(t(uid,'broadcast_prompt'),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(uid,'close'),callback_data='adm:cancelbc')]]))
    elif d=='adm:cancelbc': context.user_data.pop('broadcast',None); await q.edit_message_text('<b>'+t(uid,'admin_panel')+'</b>',parse_mode=ParseMode.HTML,reply_markup=admin_keyboard(uid))
    elif d=='adm:close': await q.edit_message_text('MAXO DPT')

async def show_users(q,page):
    c=db(); total=c.execute('SELECT COUNT(*) n FROM users').fetchone()['n']; rows=c.execute('SELECT id,first_name,username,blocked FROM users ORDER BY last_seen DESC LIMIT 8 OFFSET ?',(page*8,)).fetchall(); c.close()
    if not rows: text='No users found.'
    else:
        parts=['<b>Users</b>\n']
        for r in rows:
            name=html.escape(r['first_name'] or 'No name'); uname=(' @'+html.escape(r['username'])) if r['username'] else ''
            parts.append(f'• <b>{name}{uname}</b>\n  ID: <code>{r["id"]}</code> | {"Blocked" if r["blocked"] else "Active"}')
        text='\n'.join(parts)
    buttons=[]
    for r in rows: buttons.append([InlineKeyboardButton(f'{r["first_name"] or r["id"]}',callback_data=f'adm:user:{r["id"]}')])
    nav=[]
    if page>0: nav.append(InlineKeyboardButton('‹',callback_data=f'adm:users:{page-1}'))
    if (page+1)*8<total: nav.append(InlineKeyboardButton('›',callback_data=f'adm:users:{page+1}'))
    if nav: buttons.append(nav)
    buttons.append([InlineKeyboardButton('Back',callback_data='admin')])
    await q.edit_message_text(text,parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(buttons))

async def show_user(q,uid):
    r=get_user(uid)
    if not r: await q.answer('User not found',show_alert=True); return
    uname='@'+html.escape(r['username']) if r['username'] else '—'
    status='Blocked' if r['blocked'] else 'Active'
    text=f'<b>User Information</b>\n\nName: <b>{html.escape(r["first_name"] or "No name")}</b>\nUsername: {uname}\nID: <code>{r["id"]}</code>\nLanguage: {r["language"]}\nStatus: <b>{status}</b>\nTotal jobs: {r["total_jobs"]}\nSuccessful: {r["successful_jobs"]}\nFailed: {r["failed_jobs"]}'
    action=('adm:unblock:' if r['blocked'] else 'adm:block:')+str(uid); label='Unblock' if r['blocked'] else 'Block'
    await q.edit_message_text(text,parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(label,callback_data=action)],[InlineKeyboardButton('Back',callback_data='adm:users:0')]]))

async def notify_admin(update,context,doc):
    if ADMIN<=0: return
    u=update.effective_user
    info=(f'<b>New APK received</b>\n\nUser: <b>{html.escape(u.full_name or "Unknown")}</b>\nUsername: {("@"+html.escape(u.username)) if u.username else "—"}\nID: <code>{u.id}</code>\nFile: <code>{html.escape(doc.file_name or "unknown.apk")}</code>\nSize: <code>{(doc.file_size or 0)/1024/1024:.2f} MB</code>\nTime: <code>{datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC</code>')
    try:
        await context.bot.send_message(ADMIN,info,parse_mode=ParseMode.HTML)
        await context.bot.forward_message(ADMIN,update.effective_chat.id,update.message.message_id)
    except Exception: pass

async def process_apk(update,context,doc):
    uid=update.effective_user.id
    if is_blocked(uid): await update.effective_message.reply_text(t(uid,'blocked')); return
    if not enabled(): await update.effective_message.reply_text(t(uid,'disabled')); return
    if (doc.file_size or 0)>MAX_INPUT: await update.effective_message.reply_text(t(uid,'too_big')); return
    await notify_admin(update,context,doc)
    status=await update.effective_message.reply_text(t(uid,'processing'))
    job_dir=tempfile.mkdtemp(prefix='maxo_',dir=JOBS_DIR); inp=os.path.join(job_dir,'input.apk'); outdir=os.path.join(job_dir,'out'); os.makedirs(outdir,exist_ok=True)
    try:
        if not os.path.isfile(DPT_JAR): raise RuntimeError('Missing /opt/dpt.jar')
        if not os.path.isdir(SHELL_FILES): raise RuntimeError('Missing /opt/shell-files')
        tg=await doc.get_file(); await tg.download_to_drive(inp)
        if os.path.getsize(inp)>MAX_INPUT: raise RuntimeError('Input APK exceeds 20MB.')
        outapk=os.path.join(outdir,'result.apk')
        proc=await asyncio.create_subprocess_exec('java','-jar',DPT_JAR,'-f',inp,'-o',outapk,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,cwd='/opt')
        output,_=await asyncio.wait_for(proc.communicate(),timeout=DPT_TIMEOUT)
        log=output.decode('utf-8',errors='ignore')[-6000:]
        candidates=[]
        if os.path.isfile(outapk): candidates.append(outapk)
        for root,_,files in os.walk(outdir):
            for f in files:
                if f.lower().endswith('.apk'): candidates.append(os.path.join(root,f))
        if proc.returncode!=0 or not candidates: raise RuntimeError(log or 'DPT returned no APK output.')
        result=max(candidates,key=os.path.getmtime)
        if os.path.getsize(result)>MAX_OUTPUT: raise RuntimeError('Output APK exceeds 20MB.')
        with open(result,'rb') as f:
            await update.effective_message.reply_document(document=f,filename='✧ 𝐂𝐑𝐄𝐀𝐓𝐄 𝐁𝐘 𝐌𝐀𝐗𝐎 ✧.apk',caption='CREATE BY MAXO\n@Pv_MAXO')
        job_stat(uid,True); await status.edit_text(t(uid,'success'))
    except asyncio.TimeoutError:
        job_stat(uid,False); await status.edit_text('DPT processing timed out after 6 hours.')
    except Exception as e:
        job_stat(uid,False); await status.edit_text(t(uid,'failed')+'\n\n<code>'+html.escape(str(e))+'</code>',parse_mode=ParseMode.HTML)
    finally: shutil.rmtree(job_dir,ignore_errors=True)

async def document_handler(update,context):
    ensure_user(update.effective_user); doc=update.message.document
    if is_blocked(update.effective_user.id): await update.message.reply_text(t(update.effective_user.id,'blocked')); return
    if not (doc.file_name or '').lower().endswith('.apk'): await update.message.reply_text(t(update.effective_user.id,'only_apk')); return
    if (doc.file_size or 0)>MAX_INPUT: await update.message.reply_text(t(update.effective_user.id,'too_big')); return
    await process_apk(update,context,doc)

async def dpt_command(update,context):
    ensure_user(update.effective_user); m=update.message; uid=update.effective_user.id
    if not m.reply_to_message or not m.reply_to_message.document: await m.reply_text('Reply to an APK with /dpt.'); return
    doc=m.reply_to_message.document
    if not (doc.file_name or '').lower().endswith('.apk'): await m.reply_text(t(uid,'only_apk')); return
    if (doc.file_size or 0)>MAX_INPUT: await m.reply_text(t(uid,'too_big')); return
    await process_apk(update,context,doc)

async def broadcast_message(update,context):
    if update.effective_user.id!=ADMIN or not context.user_data.get('broadcast') or not update.message: return
    c=db(); users=c.execute('SELECT id FROM users WHERE blocked=0').fetchall(); c.close(); sent=0
    for r in users:
        try:
            await context.bot.copy_message(chat_id=r['id'],from_chat_id=update.effective_chat.id,message_id=update.message.message_id); sent+=1
        except Exception: pass
    context.user_data.pop('broadcast',None)
    await update.message.reply_text(f'Broadcast completed: {sent}/{len(users)}')

async def normal_message(update,context):
    ensure_user(update.effective_user)
    if update.effective_user.id==ADMIN and context.user_data.get('broadcast'):
        await broadcast_message(update,context); return
    uid=update.effective_user.id
    if is_blocked(uid): await update.message.reply_text(t(uid,'blocked')); return
    await update.message.reply_text('<b>MAXO DPT</b>\n\n'+html.escape(t(uid,'ready')),parse_mode=ParseMode.HTML,reply_markup=main_keyboard(uid))

async def admin_command(update,context):
    ensure_user(update.effective_user)
    if update.effective_user.id!=ADMIN: return
    await update.message.reply_text('<b>'+t(update.effective_user.id,'admin_panel')+'</b>',parse_mode=ParseMode.HTML,reply_markup=admin_keyboard(update.effective_user.id))

async def language_command(update,context):
    ensure_user(update.effective_user); await update.message.reply_text(LANGS['en']['choose'],reply_markup=lang_keyboard())

async def cancel_command(update,context):
    if update.effective_user.id==ADMIN:
        context.user_data.pop('broadcast',None); await update.message.reply_text('Cancelled.')

def main():
    if not TOKEN: raise RuntimeError('BOT_TOKEN is missing.')
    if ADMIN<=0: raise RuntimeError('ADMIN_ID is missing or invalid.')
    init_db()
    app=Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('start',start))
    app.add_handler(CommandHandler('dpt',dpt_command))
    app.add_handler(CommandHandler('admin',admin_command))
    app.add_handler(CommandHandler('language',language_command))
    app.add_handler(CommandHandler('cancel',cancel_command))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.Document.ALL,document_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND,normal_message))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=='__main__':
    main()
