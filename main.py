import asyncio, os, shutil, sqlite3, tempfile, time
from pathlib import Path
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler

TOKEN=os.environ.get('BOT_TOKEN','').strip(); ADMIN=int(os.environ.get('ADMIN_ID','0') or 0)
MAX_IN=50*1024*1024; MAX_OUT=50*1024*1024; TIMEOUT=6*60*60
DB=Path('/tmp/maxo.db'); ROOT=Path('/tmp/maxo_jobs'); ROOT.mkdir(exist_ok=True)
SEM=asyncio.Semaphore(1); enabled=True; upload_users=set()


def db():
 c=sqlite3.connect(DB); c.execute('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, first TEXT, username TEXT, seen INTEGER)'); c.commit(); return c

def add_user(u):
 c=db(); c.execute('INSERT INTO users(id,first,username,seen) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET first=excluded.first,username=excluded.username,seen=excluded.seen',(u.id,u.first_name or '',u.username or '',int(time.time()))); c.commit(); c.close()

def kb(admin=False):
 rows=[[KeyboardButton('🔴 آپلود فایل', style='danger')]]
 if admin: rows.append([KeyboardButton('🔴 مدیریت', style='danger')])
 return ReplyKeyboardMarkup(rows,resize_keyboard=True,is_persistent=True)

def admin_kb():
 return InlineKeyboardMarkup([[InlineKeyboardButton('🔴 روشن / خاموش',callback_data='toggle')],[InlineKeyboardButton('🔴 کاربران',callback_data='users')],[InlineKeyboardButton('🔴 آمار',callback_data='stats')],[InlineKeyboardButton('🔴 پیام همگانی',callback_data='broadcast')],[InlineKeyboardButton('🔴 بستن',callback_data='close')]])

def outname(): return '✧ 𝐂𝐑𝐄𝐀𝐓𝐄 𝐁𝐘 𝐌𝐀𝐗𝐎 ✧.apk'

def find_apk(d, newer_than=0):
 p=[x for x in Path(d).rglob('*.apk') if x.is_file() and x.stat().st_size>0 and x.stat().st_mtime>=newer_than]
 return max(p,key=lambda x:x.stat().st_mtime) if p else None

async def start(update,ctx):
 add_user(update.effective_user)
 await update.message.reply_text('╭────────────────────╮\n        <b>MAXO DPT</b>\n╰────────────────────╯\n\n<b>محافظت حرفه‌ای APK با DPT Shell</b>\n\nفقط فایل <b>APK</b> را ارسال کنید.\nZIP و 7Z پشتیبانی نمی‌شوند.\n\nبرای شروع، روی دکمه <b>آپلود فایل</b> بزنید یا یک APK را ریپلای کرده و <code>/dpt</code> را ارسال کنید.',parse_mode=ParseMode.HTML,reply_markup=kb(update.effective_user.id==ADMIN))

async def admin(update,ctx):
 if update.effective_user.id!=ADMIN:return
 await update.message.reply_text('<b>⚙️ MAXO DPT — مدیریت</b>\n\nوضعیت سرویس را کنترل کنید:',parse_mode=ParseMode.HTML,reply_markup=admin_kb())

async def callback(update,ctx):
 global enabled
 q=update.callback_query; await q.answer()
 if q.from_user.id!=ADMIN:return
 if q.data=='toggle':
  enabled=not enabled; await q.edit_message_text(f'<b>MAXO DPT</b>\n\nوضعیت: <b>{"فعال" if enabled else "خاموش"}</b>',parse_mode=ParseMode.HTML,reply_markup=admin_kb())
 elif q.data=='users':
  c=db(); n=c.execute('SELECT COUNT(*) FROM users').fetchone()[0]; c.close(); await q.edit_message_text(f'<b>کاربران ثبت‌شده:</b> {n}',parse_mode=ParseMode.HTML,reply_markup=admin_kb())
 elif q.data=='stats':
  await q.edit_message_text(f'<b>وضعیت:</b> {"فعال" if enabled else "خاموش"}\n<b>محدودیت فایل:</b> 50 MB\n<b>صف پردازش:</b> 1 کار همزمان',parse_mode=ParseMode.HTML,reply_markup=admin_kb())
 elif q.data=='broadcast':
  ctx.user_data['broadcast']=True; await q.edit_message_text('<b>پیام همگانی</b>\n\nمتن پیام را ارسال کنید.\nبرای لغو: /cancel',parse_mode=ParseMode.HTML)
 elif q.data=='close': await q.delete_message()

async def text(update,ctx):
 u=update.effective_user; add_user(u); t=update.message.text or ''
 if u.id==ADMIN and ctx.user_data.pop('broadcast',False):
  c=db(); ids=[x[0] for x in c.execute('SELECT id FROM users')]; c.close(); ok=0
  for uid in ids:
   try: await ctx.bot.send_message(uid,t); ok+=1
   except: pass
   await asyncio.sleep(.04)
  await update.message.reply_text(f'<b>پیام ارسال شد:</b> {ok}',parse_mode=ParseMode.HTML,reply_markup=kb(True)); return
 if t=='🔴 آپلود فایل': upload_users.add(u.id); await update.message.reply_text('<b>فایل APK را ارسال کنید.</b>\n\nZIP و 7Z پشتیبانی نمی‌شوند.',parse_mode=ParseMode.HTML,reply_markup=kb(u.id==ADMIN))
 elif t=='🔴 مدیریت' and u.id==ADMIN: await admin(update,ctx)

async def dpt(update,ctx):
 u=update.effective_user; add_user(u)
 if u.id!=ADMIN: return
 r=update.message.reply_to_message
 if not r or not r.document or not (r.document.file_name or '').lower().endswith('.apk'):
  await update.message.reply_text('روی یک فایل <b>APK</b> ریپلای کنید و /dpt را بزنید.',parse_mode=ParseMode.HTML); return
 await process(update,ctx,r.document.file_id,r.document.file_name)

async def document(update,ctx):
 u=update.effective_user; add_user(u); doc=update.message.document; name=doc.file_name or 'app.apk'
 if not name.lower().endswith('.apk'):
  await update.message.reply_text('❌ فقط فایل <b>APK</b> قبول می‌شود.',parse_mode=ParseMode.HTML,reply_markup=kb(u.id==ADMIN)); return
 if u.id!=ADMIN and u.id not in upload_users: return
 upload_users.discard(u.id); await process(update,ctx,doc.file_id,name)

async def process(update,ctx,file_id,name):
 global enabled
 if not enabled: await update.effective_message.reply_text('⛔ سرویس DPT موقتاً خاموش است.'); return
 msg=await update.effective_message.reply_text('⏳ <b>MAXO DPT</b>\n\nدر حال دریافت و آماده‌سازی APK...',parse_mode=ParseMode.HTML)
 job=Path(tempfile.mkdtemp(prefix='maxo_',dir=ROOT)); inp=job/'input.apk'; out=job/'out'; out.mkdir()
 try:
  f=await ctx.bot.get_file(file_id); await f.download_to_drive(inp)
  if inp.stat().st_size>MAX_IN: raise RuntimeError('حجم فایل بیشتر از 50MB است.')
  await msg.edit_text('⚙️ <b>MAXO DPT</b>\n\nدر حال اجرای DPT Shell...',parse_mode=ParseMode.HTML)
  async with SEM:
   p=await asyncio.create_subprocess_exec('java','-jar','/opt/dpt/dpt.jar','-f',str(inp),'-o',str(out),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT)
   started=time.time(); chunks=[]
   while True:
    try: line=await asyncio.wait_for(p.stdout.readline(),timeout=2)
    except asyncio.TimeoutError:
     line=b''
    if line: chunks.append(line)
    if p.returncode is not None: break
    apk=find_apk(out,started)
    if apk: break
    if time.time()-started>TIMEOUT:
     p.kill(); await p.wait(); raise RuntimeError('پردازش DPT بیش از زمان مجاز طول کشید.')
   if p.returncode not in (0,None): raise RuntimeError('DPT با خطا متوقف شد.')
   apk=find_apk(out,started)
   if not apk: raise RuntimeError('خروجی APK پیدا نشد.')
  if apk.stat().st_size>MAX_OUT: raise RuntimeError('حجم خروجی بیشتر از 50MB است.')
  await msg.edit_text('✅ <b>پردازش با موفقیت انجام شد.</b>\n\nدر حال ارسال فایل...',parse_mode=ParseMode.HTML)
  with apk.open('rb') as fh: await update.effective_message.reply_document(fh,filename=outname(),caption='CREATE BY MAXO\n@Pv_MAXO')
  await msg.delete()
 except Exception as e:
  await msg.edit_text('❌ <b>پردازش ناموفق بود.</b>\n\n<code>'+str(e)[:1200]+'</code>',parse_mode=ParseMode.HTML)
  if ADMIN:
   try: await ctx.bot.send_message(ADMIN,'⚠️ <b>MAXO DPT ERROR</b>\n\n'+f'User: {update.effective_user.id}\nFile: {name}\n\n{str(e)[:1500]}',parse_mode=ParseMode.HTML)
   except: pass
 finally: shutil.rmtree(job,ignore_errors=True)

async def cancel(update,ctx): ctx.user_data.pop('broadcast',None); await update.message.reply_text('لغو شد.',reply_markup=kb(update.effective_user.id==ADMIN))

def main():
 if not TOKEN or not ADMIN: raise SystemExit('BOT_TOKEN و ADMIN_ID را در Railway Variables تنظیم کنید.')
 db(); app=Application.builder().token(TOKEN).build(); app.add_handler(CommandHandler('start',start)); app.add_handler(CommandHandler('dpt',dpt)); app.add_handler(CommandHandler('admin',admin)); app.add_handler(CommandHandler('cancel',cancel)); app.add_handler(CallbackQueryHandler(callback)); app.add_handler(MessageHandler(filters.Document.ALL,document)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text)); app.run_polling(drop_pending_updates=True)
if __name__=='__main__': main()
