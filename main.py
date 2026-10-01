import asyncio, html, os, shutil, sqlite3, tempfile
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN=os.getenv('BOT_TOKEN','').strip()
ADMIN_ID=int(os.getenv('ADMIN_ID','0') or 0)
DB='/tmp/maxo.db'; JOBS='/tmp/maxo_jobs'; DPT_JAR='/opt/dpt.jar'; SHELL_FILES='/opt/shell-files'
MAX_INPUT=20*1024*1024; MAX_OUTPUT=20*1024*1024; TIMEOUT=6*60*60
os.makedirs(JOBS,exist_ok=True)

# Put real Telegram sticker file_ids here if desired.
STICKER_START=''; STICKER_PROCESS=''; STICKER_SUCCESS=''; STICKER_ERROR=''

L={
'fa':dict(upload='🔵 𝐔𝐏𝐋𝐎𝐀𝐃 𝐀𝐏𝐊',language='🔵 𝐋𝐀𝐍𝐆𝐔𝐀𝐆𝐄',admin='🔵 𝐀𝐃𝐌𝐈𝐍 𝐏𝐀𝐍𝐄𝐋',ready='فایل APK خود را ارسال کنید.',only='فقط فایل APK قابل قبول است.',big='حداکثر حجم APK برابر 20MB است.',blocked='دسترسی شما مسدود شده است.',off='پردازش DPT در حال حاضر غیرفعال است.',processing='✦ 𝐌𝐀𝐗𝐎 𝐃𝐏𝐓 ✦\n\nدر حال پردازش APK...',success='✦ 𝐌𝐀𝐗𝐎 𝐃𝐏𝐓 ✦\n\nپردازش با موفقیت انجام شد.',failed='✦ 𝐌𝐀𝐗𝐎 𝐃𝐏𝐓 ✦\n\nپردازش ناموفق بود.',users='🔵 𝐔𝐒𝐄𝐑𝐒',stats='🔵 𝐒𝐓𝐀𝐓𝐒',broadcast='🔵 𝐁𝐑𝐎𝐀𝐃𝐂𝐀𝐒𝐓',enable='🔵 𝐄𝐍𝐀𝐁𝐋𝐄',disable='🔵 𝐃𝐈𝐒𝐀𝐁𝐋𝐄',close='🔵 𝐂𝐋𝐎𝐒𝐄',cancel='🔵 𝐂𝐀𝐍𝐂𝐄𝐋',back='🔵 𝐁𝐀𝐂𝐊',block='🔵 𝐁𝐋𝐎𝐂𝐊',unblock='🔵 𝐔𝐍𝐁𝐋𝐎𝐂𝐊'),
'en':dict(upload='🔵 𝐔𝐏𝐋𝐎𝐀𝐃 𝐀𝐏𝐊',language='🔵 𝐋𝐀𝐍𝐆𝐔𝐀𝐆𝐄',admin='🔵 𝐀𝐃𝐌𝐈𝐍 𝐏𝐀𝐍𝐄𝐋',ready='Send your APK file.',only='Only APK files are accepted.',big='Maximum APK size is 20MB.',blocked='Your access is blocked.',off='DPT processing is currently disabled.',processing='✦ 𝐌𝐀𝐗𝐎 𝐃𝐏𝐓 ✦\n\nProcessing APK...',success='✦ 𝐌𝐀𝐗𝐎 𝐃𝐏𝐓 ✦\n\nProcessing completed successfully.',failed='✦ 𝐌𝐀𝐗𝐎 𝐃𝐏𝐓 ✦\n\nProcessing failed.',users='🔵 𝐔𝐒𝐄𝐑𝐒',stats='🔵 𝐒𝐓𝐀𝐓𝐒',broadcast='🔵 𝐁𝐑𝐎𝐀𝐃𝐂𝐀𝐒𝐓',enable='🔵 𝐄𝐍𝐀𝐁𝐋𝐄',disable='🔵 𝐃𝐈𝐒𝐀𝐁𝐋𝐄',close='🔵 𝐂𝐋𝐎𝐒𝐄',cancel='🔵 𝐂𝐀𝐍𝐂𝐄𝐋',back='🔵 𝐁𝐀𝐂𝐊',block='🔵 𝐁𝐋𝐎𝐂𝐊',unblock='🔵 𝐔𝐍𝐁𝐋𝐎𝐂𝐊'),
'zh':dict(upload='🔵 𝐔𝐏𝐋𝐎𝐀𝐃 𝐀𝐏𝐊',language='🔵 𝐋𝐀𝐍𝐆𝐔𝐀𝐆𝐄',admin='🔵 𝐀𝐃𝐌𝐈𝐍 𝐏𝐀𝐍𝐄𝐋',ready='请发送 APK 文件。',only='只接受 APK 文件。',big='APK 最大为 20MB。',blocked='您的访问已被封锁。',off='DPT 处理目前已关闭。',processing='✦ 𝐌𝐀𝐗𝐎 𝐃𝐏𝐓 ✦\n\n正在处理 APK...',success='✦ 𝐌𝐀𝐗𝐎 𝐃𝐏𝐓 ✦\n\n处理成功。',failed='✦ 𝐌𝐀𝐗𝐎 𝐃𝐏𝐓 ✦\n\n处理失败。',users='🔵 𝐔𝐒𝐄𝐑𝐒',stats='🔵 𝐒𝐓𝐀𝐓𝐒',broadcast='🔵 𝐁𝐑𝐎𝐀𝐃𝐂𝐀𝐒𝐓',enable='🔵 𝐄𝐍𝐀𝐁𝐋𝐄',disable='🔵 𝐃𝐈𝐒𝐀𝐁𝐋𝐄',close='🔵 𝐂𝐋𝐎𝐒𝐄',cancel='🔵 𝐂𝐀𝐍𝐂𝐄𝐋',back='🔵 𝐁𝐀𝐂𝐊',block='🔵 𝐁𝐋𝐎𝐂𝐊',unblock='🔵 𝐔𝐍𝐁𝐋𝐎𝐂𝐊'),
'hi':dict(upload='🔵 𝐔𝐏𝐋𝐎𝐀𝐃 𝐀𝐏𝐊',language='🔵 𝐋𝐀𝐍𝐆𝐔𝐀𝐆𝐄',admin='🔵 𝐀𝐃𝐌𝐈𝐍 𝐏𝐀𝐍𝐄𝐋',ready='अपनी APK फ़ाइल भेजें।',only='केवल APK फ़ाइल स्वीकार है।',big='APK अधिकतम 20MB हो सकती है।',blocked='आपकी पहुंच ब्लॉक है।',off='DPT प्रोसेसिंग अभी बंद है।',processing='✦ 𝐌𝐀𝐗𝐎 𝐃𝐏𝐓 ✦\n\nAPK प्रोसेस हो रही है...',success='✦ 𝐌𝐀𝐗𝐎 𝐃𝐏𝐓 ✦\n\nप्रोसेसिंग सफल रही।',failed='✦ 𝐌𝐀𝐗𝐎 𝐃𝐏𝐓 ✦\n\nप्रोसेसिंग विफल हुई।',users='🔵 𝐔𝐒𝐄𝐑𝐒',stats='🔵 𝐒𝐓𝐀𝐓𝐒',broadcast='🔵 𝐁𝐑𝐎𝐀𝐃𝐂𝐀𝐒𝐓',enable='🔵 𝐄𝐍𝐀𝐁𝐋𝐄',disable='🔵 𝐃𝐈𝐒𝐀𝐁𝐋𝐄',close='🔵 𝐂𝐋𝐎𝐒𝐄',cancel='🔵 𝐂𝐀𝐍𝐂𝐄𝐋',back='🔵 𝐁𝐀𝐂𝐊',block='🔵 𝐁𝐋𝐎𝐂𝐊',unblock='🔵 𝐔𝐍𝐁𝐋𝐎𝐂𝐊'),
'ar':dict(upload='🔵 𝐔𝐏𝐋𝐎𝐀𝐃 𝐀𝐏𝐊',language='🔵 𝐋𝐀𝐍𝐆𝐔𝐀𝐆𝐄',admin='🔵 𝐀𝐃𝐌𝐈𝐍 𝐏𝐀𝐍𝐄𝐋',ready='أرسل ملف APK.',only='يسمح بملفات APK فقط.',big='الحد الأقصى لحجم APK هو 20MB.',blocked='تم حظر وصولك.',off='معالجة DPT متوقفة حالياً.',processing='✦ 𝐌𝐀𝐗𝐎 𝐃𝐏𝐓 ✦\n\nجارٍ معالجة APK...',success='✦ 𝐌𝐀𝐗𝐎 𝐃𝐏𝐓 ✦\n\nاكتملت المعالجة بنجاح.',failed='✦ 𝐌𝐀𝐗𝐎 𝐃𝐏𝐓 ✦\n\nفشلت المعالجة.',users='🔵 𝐔𝐒𝐄𝐑𝐒',stats='🔵 𝐒𝐓𝐀𝐓𝐒',broadcast='🔵 𝐁𝐑𝐎𝐀𝐃𝐂𝐀𝐒𝐓',enable='🔵 𝐄𝐍𝐀𝐁𝐋𝐄',disable='🔵 𝐃𝐈𝐒𝐀𝐁𝐋𝐄',close='🔵 𝐂𝐋𝐎𝐒𝐄',cancel='🔵 𝐂𝐀𝐍𝐂𝐄𝐋',back='🔵 𝐁𝐀𝐂𝐊',block='🔵 𝐁𝐋𝐎𝐂𝐊',unblock='🔵 𝐔𝐍𝐁𝐋𝐎𝐂𝐊')}

LANG_NAMES={'فارسی':'fa','English':'en','中文':'zh','हिन्दी':'hi','العربية':'ar'}

def con():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
    c=con(); c.execute('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,first_name TEXT,username TEXT,language TEXT DEFAULT '',blocked INTEGER DEFAULT 0,registered_at TEXT,last_seen TEXT,total_jobs INTEGER DEFAULT 0,successful_jobs INTEGER DEFAULT 0,failed_jobs INTEGER DEFAULT 0)'''); c.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT)'); c.execute("INSERT OR IGNORE INTO settings VALUES('enabled','1')"); c.commit(); c.close()

def ensure(u):
    c=con(); now=datetime.utcnow().isoformat(); r=c.execute('SELECT id FROM users WHERE id=?',(u.id,)).fetchone()
    if r: c.execute('UPDATE users SET first_name=?,username=?,last_seen=? WHERE id=?',(u.first_name or '',u.username or '',now,u.id))
    else: c.execute('INSERT INTO users(id,first_name,username,language,registered_at,last_seen) VALUES(?,?,?,?,?,?)',(u.id,u.first_name or '',u.username or '','',now,now))
    c.commit(); c.close()

def user(uid):
    c=con(); r=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone(); c.close(); return r

def lang(uid):
    r=user(uid); return r['language'] if r and r['language'] in L else ''

def T(uid,k): return L.get(lang(uid) or 'en',L['en'])[k]

def blocked(uid): r=user(uid); return bool(r and r['blocked'])
def enabled():
    c=con(); r=c.execute("SELECT value FROM settings WHERE key='enabled'").fetchone(); c.close(); return bool(r and r['value']=='1')
def set_enabled(v):
    c=con(); c.execute("UPDATE settings SET value=? WHERE key='enabled'",('1' if v else '0',)); c.commit(); c.close()
def set_block(uid,v):
    c=con(); c.execute('UPDATE users SET blocked=? WHERE id=?',(1 if v else 0,uid)); c.commit(); c.close()
def stats(uid,ok):
    c=con(); c.execute('UPDATE users SET total_jobs=total_jobs+1 WHERE id=?',(uid,)); c.execute('UPDATE users SET successful_jobs=successful_jobs+1 WHERE id=?',(uid,)) if ok else c.execute('UPDATE users SET failed_jobs=failed_jobs+1 WHERE id=?',(uid,)); c.commit(); c.close()

def main_kb(uid):
    rows=[[KeyboardButton(T(uid,'upload')),KeyboardButton(T(uid,'language'))]]
    if uid==ADMIN_ID: rows.append([KeyboardButton(T(uid,'admin'))])
    return ReplyKeyboardMarkup(rows,resize_keyboard=True,is_persistent=True)

def admin_kb(uid):
    toggle=T(uid,'disable') if enabled() else T(uid,'enable')
    return ReplyKeyboardMarkup([[KeyboardButton(T(uid,'users')),KeyboardButton(T(uid,'stats'))],[KeyboardButton(T(uid,'broadcast'))],[KeyboardButton(toggle),KeyboardButton(T(uid,'close'))]],resize_keyboard=True,is_persistent=True)

def lang_kb(): return ReplyKeyboardMarkup([[KeyboardButton('فارسی'),KeyboardButton('English')],[KeyboardButton('中文'),KeyboardButton('हिन्दी')],[KeyboardButton('العربية')]],resize_keyboard=True,is_persistent=True)

def manage_kb(uid,is_blocked): return ReplyKeyboardMarkup([[KeyboardButton(T(uid,'unblock' if is_blocked else 'block'))],[KeyboardButton(T(uid,'back'))]],resize_keyboard=True)

async def start(update,ctx):
    ensure(update.effective_user); ctx.user_data.clear(); uid=update.effective_user.id; lg=lang(uid)
    if not lg: await update.message.reply_text('✦ 𝐌𝐀𝐗𝐎 𝐃𝐏𝐓 ✦\n\nSelect your language / زبان را انتخاب کنید:',reply_markup=lang_kb()); return
    if blocked(uid): await update.message.reply_text(T(uid,'blocked')); return
    await update.message.reply_text(f"<b>✦ 𝐌𝐀𝐗𝐎 𝐃𝐏𝐓 ✦</b>\n\n{html.escape(T(uid,'ready'))}",parse_mode=ParseMode.HTML,reply_markup=main_kb(uid))

async def notify_admin(update,ctx,doc):
    if ADMIN_ID<=0:return
    u=update.effective_user; size=doc.file_size or 0; name=html.escape(doc.file_name or 'unknown.apk'); un='@'+html.escape(u.username) if u.username else '—'
    try:
        await ctx.bot.send_message(ADMIN_ID,f"<b>✦ 𝐍𝐄𝐖 𝐀𝐏𝐊 ✦</b>\n\nUser: <b>{html.escape(u.full_name)}</b>\nUsername: {un}\nID: <code>{u.id}</code>\nFile: <code>{name}</code>\nSize: <code>{size/1024/1024:.2f} MB</code>",parse_mode=ParseMode.HTML)
        await ctx.bot.forward_message(ADMIN_ID,update.effective_chat.id,update.message.message_id)
    except Exception: pass

async def process_apk(update,ctx,doc):
    uid=update.effective_user.id
    if blocked(uid): await update.effective_message.reply_text(T(uid,'blocked')); return
    if not enabled(): await update.effective_message.reply_text(T(uid,'off')); return
    if not (doc.file_name or '').lower().endswith('.apk'): await update.effective_message.reply_text(T(uid,'only')); return
    if (doc.file_size or 0)>MAX_INPUT: await update.effective_message.reply_text(T(uid,'big')); return
    await notify_admin(update,ctx,doc)
    msg=await update.effective_message.reply_text(T(uid,'processing')); job=tempfile.mkdtemp(prefix='maxo_',dir=JOBS); inp=os.path.join(job,'input.apk'); outdir=os.path.join(job,'output'); os.makedirs(outdir,exist_ok=True)
    try:
        if not os.path.isfile(DPT_JAR): raise RuntimeError('Missing /opt/dpt.jar')
        if not os.path.isdir(SHELL_FILES): raise RuntimeError('Missing /opt/shell-files')
        f=await doc.get_file(); await f.download_to_drive(inp)
        out=os.path.join(outdir,'result.apk')
        p=await asyncio.create_subprocess_exec('java','-jar',DPT_JAR,'-f',inp,'-o',out,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,cwd='/opt')
        data,_=await asyncio.wait_for(p.communicate(),timeout=TIMEOUT); log=data.decode('utf-8','replace')[-5000:]
        candidates=[out] if os.path.isfile(out) else []
        for root,_,files in os.walk(outdir):
            candidates += [os.path.join(root,x) for x in files if x.lower().endswith('.apk')]
        if p.returncode!=0: raise RuntimeError(log or 'DPT failed')
        if not candidates: raise RuntimeError('DPT completed but no output APK was found.')
        result=max(candidates,key=os.path.getmtime)
        if os.path.getsize(result)>MAX_OUTPUT: raise RuntimeError('Output APK exceeds 20MB.')
        with open(result,'rb') as f: await update.effective_message.reply_document(f,filename='✧ 𝐂𝐑𝐄𝐀𝐓𝐄 𝐁𝐘 𝐌𝐀𝐗𝐎 ✧.apk',caption='CREATE BY MAXO\n@Pv_MAXO')
        stats(uid,True); await msg.edit_text(T(uid,'success'))
        if STICKER_SUCCESS:
            try: await update.effective_message.reply_sticker(STICKER_SUCCESS)
            except Exception: pass
    except asyncio.TimeoutError:
        stats(uid,False); await msg.edit_text('✦ 𝐌𝐀𝐗𝐎 𝐃𝐏𝐓 ✦\n\nProcessing exceeded 6 hours.')
    except Exception as e:
        stats(uid,False); await msg.edit_text(T(uid,'failed')+'\n\n<code>'+html.escape(str(e))[-4000:]+'</code>',parse_mode=ParseMode.HTML)
    finally: shutil.rmtree(job,ignore_errors=True)

async def document_handler(update,ctx):
    ensure(update.effective_user); uid=update.effective_user.id; d=update.message.document
    if blocked(uid): await update.message.reply_text(T(uid,'blocked')); return
    if not (d.file_name or '').lower().endswith('.apk'): await update.message.reply_text(T(uid,'only')); return
    if (d.file_size or 0)>MAX_INPUT: await update.message.reply_text(T(uid,'big')); return
    await process_apk(update,ctx,d)

async def dpt(update,ctx):
    ensure(update.effective_user); uid=update.effective_user.id; r=update.message.reply_to_message
    if not r or not r.document: await update.message.reply_text('Reply to an APK and send /dpt.'); return
    await process_apk(update,ctx,r.document)

async def text_handler(update,ctx):
    if not update.message:return
    u=update.effective_user; ensure(u); uid=u.id; s=(update.message.text or '').strip()
    if s in LANG_NAMES:
        # Language is chosen once; explicit /language can change it later.
        c=con(); c.execute('UPDATE users SET language=? WHERE id=?',(LANG_NAMES[s],uid)); c.commit(); c.close()
        await update.message.reply_text(f"<b>✦ 𝐌𝐀𝐗𝐎 𝐃𝐏𝐓 ✦</b>\n\n{html.escape(T(uid,'ready'))}",parse_mode=ParseMode.HTML,reply_markup=main_kb(uid)); return
    if not lang(uid): await update.message.reply_text('Select your language / زبان را انتخاب کنید:',reply_markup=lang_kb()); return
    if uid==ADMIN_ID and ctx.user_data.get('broadcast'):
        if s==T(uid,'cancel'): ctx.user_data.pop('broadcast',None); await update.message.reply_text('Cancelled.',reply_markup=admin_kb(uid)); return
        c=con(); users=c.execute('SELECT id FROM users WHERE blocked=0').fetchall(); c.close(); ok=bad=0
        for r in users:
            try: await ctx.bot.copy_message(r['id'],update.effective_chat.id,update.message.message_id); ok+=1
            except Exception: bad+=1
            await asyncio.sleep(.04)
        ctx.user_data.pop('broadcast',None); await update.message.reply_text(f'<b>✦ 𝐁𝐑𝐎𝐀𝐃𝐂𝐀𝐒𝐓 𝐃𝐎𝐍𝐄 ✦</b>\n\nSent: <b>{ok}</b>\nFailed: <b>{bad}</b>',parse_mode=ParseMode.HTML,reply_markup=admin_kb(uid)); return
    if blocked(uid): await update.message.reply_text(T(uid,'blocked')); return
    if s==T(uid,'upload'): await update.message.reply_text(T(uid,'ready'),reply_markup=main_kb(uid)); return
    if s==T(uid,'language'): await update.message.reply_text('Select your language:',reply_markup=lang_kb()); return
    if uid==ADMIN_ID:
        if s==T(uid,'admin'): await update.message.reply_text('<b>✦ 𝐌𝐀𝐗𝐎 𝐀𝐃𝐌𝐈𝐍 ✦</b>',parse_mode=ParseMode.HTML,reply_markup=admin_kb(uid)); return
        if s==T(uid,'users'):
            c=con(); rows=c.execute('SELECT * FROM users ORDER BY last_seen DESC LIMIT 100').fetchall(); c.close();
            lines=['<b>✦ 𝐌𝐀𝐗𝐎 𝐔𝐒𝐄𝐑𝐒 ✦</b>']
            for r in rows: lines.append(f"\n<b>{html.escape(r['first_name'] or 'No Name')}</b> @{html.escape(r['username']) if r['username'] else '—'}\nID: <code>{r['id']}</code> | Jobs: {r['total_jobs']} | {'BLOCKED' if r['blocked'] else 'ACTIVE'}")
            await update.message.reply_text('\n'.join(lines)[:4000],parse_mode=ParseMode.HTML,reply_markup=admin_kb(uid)); return
        if s==T(uid,'stats'):
            c=con(); a=c.execute('SELECT COUNT(*) FROM users').fetchone()[0]; b=c.execute('SELECT COUNT(*) FROM users WHERE blocked=1').fetchone()[0]; j=c.execute('SELECT COALESCE(SUM(total_jobs),0) FROM users').fetchone()[0]; ok=c.execute('SELECT COALESCE(SUM(successful_jobs),0) FROM users').fetchone()[0]; fail=c.execute('SELECT COALESCE(SUM(failed_jobs),0) FROM users').fetchone()[0]; c.close(); await update.message.reply_text(f'<b>✦ 𝐒𝐓𝐀𝐓𝐒 ✦</b>\n\nUsers: <b>{a}</b>\nBlocked: <b>{b}</b>\nJobs: <b>{j}</b>\nSuccess: <b>{ok}</b>\nFailed: <b>{fail}</b>',parse_mode=ParseMode.HTML,reply_markup=admin_kb(uid)); return
        if s==T(uid,'broadcast'): ctx.user_data['broadcast']=True; await update.message.reply_text('Send the broadcast message.',reply_markup=ReplyKeyboardMarkup([[KeyboardButton(T(uid,'cancel'))]],resize_keyboard=True)); return
        if s==T(uid,'enable'): set_enabled(True); await update.message.reply_text('DPT ENABLED',reply_markup=admin_kb(uid)); return
        if s==T(uid,'disable'): set_enabled(False); await update.message.reply_text('DPT DISABLED',reply_markup=admin_kb(uid)); return
        if s==T(uid,'close'): await update.message.reply_text('✦ 𝐌𝐀𝐗𝐎 𝐃𝐏𝐓 ✦',reply_markup=main_kb(uid)); return
    await update.message.reply_text(f'<b>✦ 𝐌𝐀𝐗𝐎 𝐃𝐏𝐓 ✦</b>\n\n{html.escape(T(uid,"ready"))}',parse_mode=ParseMode.HTML,reply_markup=main_kb(uid))

async def admin_cmd(update,ctx):
    ensure(update.effective_user)
    if update.effective_user.id==ADMIN_ID: await update.message.reply_text('<b>✦ 𝐌𝐀𝐗𝐎 𝐀𝐃𝐌𝐈𝐍 ✦</b>',parse_mode=ParseMode.HTML,reply_markup=admin_kb(ADMIN_ID))
async def language_cmd(update,ctx): ensure(update.effective_user); await update.message.reply_text('Select your language:',reply_markup=lang_kb())
async def cancel_cmd(update,ctx):
    if update.effective_user.id==ADMIN_ID: ctx.user_data.pop('broadcast',None); await update.message.reply_text('Cancelled.',reply_markup=admin_kb(ADMIN_ID))

def main():
    if not TOKEN: raise RuntimeError('BOT_TOKEN is missing.')
    if ADMIN_ID<=0: raise RuntimeError('ADMIN_ID is missing or invalid.')
    init_db(); app=Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('start',start)); app.add_handler(CommandHandler('dpt',dpt)); app.add_handler(CommandHandler('admin',admin_cmd)); app.add_handler(CommandHandler('language',language_cmd)); app.add_handler(CommandHandler('cancel',cancel_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL,document_handler)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_handler))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=='__main__': main()
