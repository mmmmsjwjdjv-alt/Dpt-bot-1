import asyncio, html, json, os, shutil, sqlite3, tempfile
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.error import RetryAfter
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TOKEN=os.getenv('BOT_TOKEN','').strip()
ADMIN_ID=int(os.getenv('ADMIN_ID','0') or 0)
DB=os.getenv('DB_PATH','/tmp/maxo.db')
JOBS='/tmp/maxo_jobs'
DPT_JAR='/opt/dpt.jar'
SHELL_FILES='/opt/shell-files'
UNLOCK_CP='/opt/fahad-unpacker/build/install/fahad-unpacker/lib/*'
UNLOCK_MAIN='com.dpt.unpack.MainKt'
MAX_INPUT=20*1024*1024
MAX_OUTPUT=20*1024*1024
TIMEOUT=6*60*60
os.makedirs(JOBS,exist_ok=True)
STICKER_START=''; STICKER_PROCESS=''; STICKER_SUCCESS=''; STICKER_ERROR=''
HTML=ParseMode.HTML
FEATS=('dpt','unlock')
PER_FA={'week':'هفته','month':'ماه'}
DIG=str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩','01234567890123456789')
_JL=None
def joblock():
    global _JL
    if _JL is None: _JL=asyncio.Lock()
    return _JL

# ---------- fonts / text helpers ----------
def F(t):
    o=[]
    for ch in str(t):
        if 'A'<=ch<='Z': o.append(chr(0x1D400+ord(ch)-65))
        elif 'a'<=ch<='z': o.append(chr(0x1D41A+ord(ch)-97))
        else: o.append(ch)
    return ''.join(o)
def b(t): return '<b>'+t+'</b>'
def esc(t): return html.escape(str(t))
def fn(t): return esc(F(t))
def money(n): return f'{int(n):,}'
HEAD=b('✦ 𝐌𝐀𝐗𝐎 𝐃𝐏𝐓 ✦')
ADM=b('✦ 𝐌𝐀𝐗𝐎 𝐀𝐃𝐌𝐈𝐍 ✦')
APK=F('APK'); DPTF=F('DPT'); UNL=F('UNLOCK')
FA=dict(
 welcome=HEAD+'\n\n'+b('👋 به ربات حرفه‌ای '+DPTF+' خوش آمدید')+'\n'+b('📲 فایل '+APK+' خود را ارسال کنید.')+'\n\n'+b('💎 از بخش خرید اشتراک می‌توانید پلن تهیه کنید.'),
 ready=b('📲 فایل '+APK+' خود را ارسال کنید.'),
 unlock_ready=b('🔓 فایل '+APK+' دارای '+DPTF+' را برای بازگشت به حالت عادی ارسال کنید.'),
 only=b('⚠️ فقط فایل '+APK+' قابل قبول است.'),
 big=b('⚠️ حداکثر حجم '+APK+' برابر 20'+F('MB')+' است.'),
 blocked=b('⛔ دسترسی شما مسدود شده است.'),
 off=b('🔒 پردازش '+DPTF+' در حال حاضر غیرفعال است.'),
 processing=HEAD+'\n\n'+b('⏳ در حال پردازش '+APK+'...'),
 unlock_processing=HEAD+'\n\n'+b('🔓 در حال برگرداندن '+APK+' به حالت عادی...'),
 success=HEAD+'\n\n'+b('✅ پردازش با موفقیت انجام شد.'),
 unlock_success=HEAD+'\n\n'+b('✅ '+APK+' با موفقیت به حالت عادی برگردانده شد.'),
 failed=HEAD+'\n\n'+b('❌ پردازش ناموفق بود.'),
 timeout=HEAD+'\n\n'+b('⏰ پردازش بیش از 6 ساعت طول کشید.'),
 noquota_dpt=HEAD+'\n\n'+b('❌ سهمیه '+DPTF+' شما تمام شده است.')+'\n'+b('💎 برای ادامه از بخش خرید اشتراک، پلن تهیه کنید.'),
 noquota_unlock=HEAD+'\n\n'+b('❌ سهمیه '+UNL+' شما تمام شده است.')+'\n'+b('💎 برای ادامه از بخش خرید اشتراک، پلن تهیه کنید.'),
 cancelled=b('↩️ عملیات لغو شد.'),
)

# ---------- buttons ----------
def B(t):
    try: return KeyboardButton(t,style='primary')
    except TypeError: return KeyboardButton(t,api_kwargs={'style':'primary'})
def IB(t,d):
    try: return InlineKeyboardButton(t,callback_data=d,style='primary')
    except TypeError: return InlineKeyboardButton(t,callback_data=d,api_kwargs={'style':'primary'})
def IK(*rows): return InlineKeyboardMarkup([list(r) for r in rows])
_BT=dict(dpt='DPT',unlock='UNLOCK',buy='BUY PLAN',account='MY ACCOUNT',support='SUPPORT',admin='ADMIN PANEL',users='USERS',stats='STATS',plans='PLANS',card='CARD',limits='FREE LIMITS',reset='RESET FREE',broadcast='BROADCAST',backup='BACKUP',restore='RESTORE',enable='ENABLE',disable='DISABLE',close='CLOSE',cancel='CANCEL')
BT={k:F(v) for k,v in _BT.items()}
BTR={v:k for k,v in BT.items()}
ADMIN_KEYS={'admin','users','stats','plans','card','limits','reset','broadcast','backup','restore','enable','disable','close'}

# ---------- database ----------
def con():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def init_db():
    c=con()
    c.execute('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,first_name TEXT,username TEXT,language TEXT DEFAULT '',blocked INTEGER DEFAULT 0,registered_at TEXT,last_seen TEXT,total_jobs INTEGER DEFAULT 0,successful_jobs INTEGER DEFAULT 0,failed_jobs INTEGER DEFAULT 0)''')
    c.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,price INTEGER DEFAULT 0,dpt_uses INTEGER DEFAULT 0,unlock_uses INTEGER DEFAULT 0)')
    c.execute('CREATE TABLE IF NOT EXISTS usage(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,feature TEXT,ts TEXT)')
    c.execute("CREATE TABLE IF NOT EXISTS receipts(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,plan_name TEXT,price INTEGER,dpt_uses INTEGER,unlock_uses INTEGER,status TEXT DEFAULT 'pending',created_at TEXT)")
    cols={r[1] for r in c.execute('PRAGMA table_info(users)')}
    for n,t in (('sub_dpt','INTEGER DEFAULT 0'),('sub_unlock','INTEGER DEFAULT 0'),('sub_plan',"TEXT DEFAULT ''")):
        if n not in cols: c.execute(f'ALTER TABLE users ADD COLUMN {n} {t}')
    for k,v in (('enabled','1'),('dpt_limit','10'),('dpt_period','month'),('unlock_limit','1'),('unlock_period','month'),('card_number',''),('card_name',''),('reset_at','')):
        c.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',(k,v))
    c.commit(); c.close()
def get(k,d=''):
    c=con(); r=c.execute('SELECT value FROM settings WHERE key=?',(k,)).fetchone(); c.close(); return r['value'] if r and r['value'] is not None else d
def setv(k,v):
    c=con(); c.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',(k,str(v))); c.commit(); c.close()
def ensure(u):
    c=con(); now=datetime.utcnow().isoformat(); r=c.execute('SELECT id FROM users WHERE id=?',(u.id,)).fetchone()
    if r: c.execute('UPDATE users SET first_name=?,username=?,last_seen=? WHERE id=?',(u.first_name or '',u.username or '',now,u.id))
    else: c.execute('INSERT INTO users(id,first_name,username,language,registered_at,last_seen) VALUES(?,?,?,?,?,?)',(u.id,u.first_name or '',u.username or '','',now,now))
    c.commit(); c.close()
def user(uid):
    c=con(); r=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone(); c.close(); return r
def blocked(uid): r=user(uid); return bool(r and r['blocked'])
def enabled():
    c=con(); r=c.execute("SELECT value FROM settings WHERE key='enabled'").fetchone(); c.close(); return bool(r and r['value']=='1')
def set_enabled(v):
    c=con(); c.execute("UPDATE settings SET value=? WHERE key='enabled'",('1' if v else '0',)); c.commit(); c.close()
def stats(uid,ok):
    c=con(); c.execute('UPDATE users SET total_jobs=total_jobs+1 WHERE id=?',(uid,)); c.execute('UPDATE users SET successful_jobs=successful_jobs+1 WHERE id=?',(uid,)) if ok else c.execute('UPDATE users SET failed_jobs=failed_jobs+1 WHERE id=?',(uid,)); c.commit(); c.close()
def plan(pid):
    c=con(); r=c.execute('SELECT * FROM plans WHERE id=?',(pid,)).fetchone(); c.close(); return r
def num(s):
    s=(s or '').translate(DIG).replace(',','').replace('٬','').strip()
    return int(s) if s.isdigit() else None

# ---------- quotas ----------
def lim(f):
    try: return max(0,int(get(f+'_limit','0') or 0))
    except ValueError: return 0
def per(f): return 'week' if get(f+'_period','month')=='week' else 'month'
def window(f):
    start=(datetime.utcnow()-timedelta(days=7 if per(f)=='week' else 30)).isoformat()
    return max(start,get('reset_at',''))
def used(uid,f):
    c=con(); n=c.execute('SELECT COUNT(*) FROM usage WHERE user_id=? AND feature=? AND ts>?',(uid,f,window(f))).fetchone()[0]; c.close(); return n
def paid(uid,f):
    r=user(uid); return int(r['sub_'+f] or 0) if r else 0
def left(uid,f): return max(0,lim(f)-used(uid,f))
def consume(uid,f):
    c=con(); tok=None
    if used(uid,f)<lim(f):
        cur=c.execute('INSERT INTO usage(user_id,feature,ts) VALUES(?,?,?)',(uid,f,datetime.utcnow().isoformat())); tok=('free',cur.lastrowid)
    else:
        col='sub_'+f
        if c.execute(f'UPDATE users SET {col}={col}-1 WHERE id=? AND {col}>0',(uid,)).rowcount: tok=('paid',0)
    c.commit(); c.close(); return tok
def refund(uid,f,tok):
    if not tok: return
    c=con()
    if tok[0]=='free': c.execute('DELETE FROM usage WHERE id=?',(tok[1],))
    else: c.execute(f'UPDATE users SET sub_{f}=sub_{f}+1 WHERE id=?',(uid,))
    c.commit(); c.close()
def quota_text(uid):
    out=[]
    for f in FEATS:
        out.append(b('🔹 '+F(f.upper())+':')+' '+b(f'{left(uid,f)} از {lim(f)} رایگان در {PER_FA[per(f)]}')+' '+b(f'+ {paid(uid,f)} اشتراکی'))
    return '\n'.join(out)

# ---------- keyboards ----------
def main_kb(uid):
    rows=[[B(BT['dpt']),B(BT['unlock'])],[B(BT['buy']),B(BT['account'])],[B(BT['support'])]]
    if uid==ADMIN_ID: rows.append([B(BT['admin'])])
    return ReplyKeyboardMarkup(rows,resize_keyboard=True,is_persistent=True)
def admin_kb(uid=None):
    toggle=BT['disable'] if enabled() else BT['enable']
    return ReplyKeyboardMarkup([[B(BT['users']),B(BT['stats'])],[B(BT['plans']),B(BT['card'])],[B(BT['limits']),B(BT['reset'])],[B(BT['broadcast'])],[B(BT['backup']),B(BT['restore'])],[B(toggle),B(BT['close'])]],resize_keyboard=True,is_persistent=True)
def cancel_kb(): return ReplyKeyboardMarkup([[B(BT['cancel'])]],resize_keyboard=True,is_persistent=True)
async def say(update,text,kb=None): return await update.effective_message.reply_text(text,parse_mode=HTML,reply_markup=kb)
async def retry(fn):
    try: return await fn()
    except RetryAfter as e:
        await asyncio.sleep(e.retry_after+1); return await fn()

# ---------- views ----------
def plan_card(p,admin=False):
    t=b('🎁 '+fn(p['name'])+('  •  #'+str(p['id']) if admin else ''))+'\n'+b(f"💰 قیمت: {money(p['price'])} تومان")+'\n'+b(f"🔵 {DPTF}: {p['dpt_uses']} بار")+'\n'+b(f"🔓 {UNL}: {p['unlock_uses']} بار")
    return '<blockquote>'+t+'</blockquote>'
def plans_view():
    c=con(); ps=c.execute('SELECT * FROM plans ORDER BY price,id').fetchall(); c.close()
    t=ADM+'\n\n'+b('📦 پلن‌های اشتراک')+'\n\n'; rows=[]
    if not ps: t+=b('هنوز پلنی ثبت نشده است.')
    for p in ps:
        t+=plan_card(p,True)+'\n'; rows.append([IB(F('DELETE')+' #'+str(p['id'])+' '+F(p['name']),'pl:del:'+str(p['id']))])
    rows.append([IB(F('ADD PLAN'),'pl:add')])
    return t,IK(*rows)
def limits_view():
    t=ADM+'\n\n'+b('⚙️ تنظیمات سهمیه رایگان')+'\n\n'; rows=[]
    for f in FEATS:
        t+=b('🔹 '+F(f.upper())+f': {lim(f)} بار در {PER_FA[per(f)]}')+'\n'
        rows.append([IB(F(f.upper()+' LIMIT'),f'lim:{f}:n'),IB(F(f.upper()+' PERIOD: '+per(f).upper()),f'lim:{f}:p')])
    t+='\n'+b('🔄 با دکمه '+F('PERIOD')+' بازه را بین هفته و ماه جابجا کنید.')
    return t,IK(*rows)
def card_view():
    n=get('card_number'); nm=get('card_name')
    t=ADM+'\n\n'+b('💳 اطلاعات کارت')+'\n\n'+b('شماره کارت:')+' '+('<code>'+esc(n)+'</code>' if n else b('ثبت نشده'))+'\n'+b('به نام:')+' '+(b(fn(nm)) if nm else b('ثبت نشده'))
    return t,IK([IB(F('SET NUMBER'),'card:num'),IB(F('SET NAME'),'card:name')])
def account_text(uid):
    r=user(uid); active=(paid(uid,'dpt')>0 or paid(uid,'unlock')>0) and (r['sub_plan'] or '')
    return HEAD+'\n\n'+b('👤 حساب کاربری')+'\n\n'+b('🆔 شناسه:')+' <code>'+str(uid)+'</code>\n'+b('💎 اشتراک فعال:')+' '+(b(fn(active)) if active else b('ندارد'))+'\n\n'+quota_text(uid)+'\n\n'+b(f"🛠 تعداد پردازش‌ها: {r['total_jobs']}")+'\n'+b(f"✅ موفق: {r['successful_jobs']}")+b(f" | ❌ ناموفق: {r['failed_jobs']}")

# ---------- backup / restore ----------
def dump_db():
    c=con(); data={'maxo_backup':1,'created':datetime.utcnow().isoformat(),'tables':{}}
    for (name,) in [(r[0],) for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]:
        cur=c.execute(f'SELECT * FROM "{name}"'); cols=[d[0] for d in cur.description]
        data['tables'][name]={'columns':cols,'rows':[list(r) for r in cur.fetchall()]}
    c.close(); return json.dumps(data,ensure_ascii=False).encode('utf-8')
def restore_db(data):
    t=data.get('tables') if isinstance(data,dict) and data.get('maxo_backup')==1 else None
    if not isinstance(t,dict) or not t: raise ValueError('Invalid backup file')
    c=con(); n=0
    try:
        have={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        for name,tb in t.items():
            if name not in have: continue
            ch=[r[1] for r in c.execute(f'PRAGMA table_info("{name}")')]
            use=[x for x in tb['columns'] if x in ch]; idx=[tb['columns'].index(x) for x in use]
            c.execute(f'DELETE FROM "{name}"')
            q='INSERT INTO "%s"(%s) VALUES(%s)'%(name,','.join('"'+x+'"' for x in use),','.join('?'*len(use)))
            for row in tb['rows']: c.execute(q,[row[i] for i in idx]); n+=1
        c.commit()
    except Exception:
        c.rollback(); raise
    finally: c.close()
    init_db(); return n

# ---------- core processing ----------
async def start(update,ctx):
    ensure(update.effective_user); ctx.user_data.clear(); uid=update.effective_user.id
    if blocked(uid): await say(update,FA['blocked']); return
    await say(update,FA['welcome'],main_kb(uid))
async def notify_admin(update,ctx,doc,source_message=None):
    if ADMIN_ID<=0:return
    u=update.effective_user; size=doc.file_size or 0; name=esc(doc.file_name or 'unknown.apk'); un='@'+esc(u.username) if u.username else '—'
    try:
        await ctx.bot.send_message(ADMIN_ID,b('✦ 𝐍𝐄𝐖 𝐀𝐏𝐊 ✦')+'\n\n'+b('👤 کاربر:')+' '+b(esc(u.full_name))+'\n'+b('🔗 یوزرنیم:')+' '+un+'\n'+b('🆔 آیدی:')+' <code>'+str(u.id)+'</code>\n'+b('📁 فایل:')+' <code>'+name+'</code>\n'+b('📦 حجم:')+' <code>'+f'{size/1024/1024:.2f} MB'+'</code>',parse_mode=HTML)
        if source_message: await ctx.bot.forward_message(ADMIN_ID,update.effective_chat.id,source_message.message_id)
        elif update.message: await ctx.bot.forward_message(ADMIN_ID,update.effective_chat.id,update.message.message_id)
    except Exception: pass
async def process_apk(update,ctx,doc,mode='dpt',source_message=None):
    uid=update.effective_user.id
    if blocked(uid): await say(update,FA['blocked']); return
    if mode=='dpt' and not enabled(): await say(update,FA['off']); return
    if not (doc.file_name or '').lower().endswith('.apk'): await say(update,FA['only']); return
    if (doc.file_size or 0)>MAX_INPUT: await say(update,FA['big']); return
    tok=None
    if uid!=ADMIN_ID:
        tok=consume(uid,mode)
        if tok is None: await say(update,FA['noquota_'+mode]); return
    await notify_admin(update,ctx,doc,source_message)
    msg=await say(update,FA['processing' if mode=='dpt' else 'unlock_processing'])
    job=tempfile.mkdtemp(prefix='maxo_',dir=JOBS); inp=os.path.join(job,'input.apk'); outdir=os.path.join(job,'output'); os.makedirs(outdir,exist_ok=True); p=None
    try:
        f=await doc.get_file(); await f.download_to_drive(inp)
        async with joblock():
            if mode=='dpt':
                if not os.path.isfile(DPT_JAR): raise RuntimeError('Missing /opt/dpt.jar')
                if not os.path.isdir(SHELL_FILES): raise RuntimeError('Missing /opt/shell-files')
                out=os.path.join(outdir,'result.apk')
                p=await asyncio.create_subprocess_exec('java','-jar',DPT_JAR,'-f',inp,'-o',out,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,cwd='/opt')
            else:
                if not os.path.isdir('/opt/fahad-unpacker/build/install/fahad-unpacker/lib'): raise RuntimeError('Unlock engine is not installed.')
                p=await asyncio.create_subprocess_exec('java','-Xmx1g','-cp',UNLOCK_CP,UNLOCK_MAIN,'-i',inp,'-o',outdir,'--mode','dpt',stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,cwd='/opt/fahad-unpacker')
            data,_=await asyncio.wait_for(p.communicate(),timeout=TIMEOUT); log=data.decode('utf-8','replace')[-8000:]
        candidates=[]
        for root,_,files in os.walk(outdir): candidates += [os.path.join(root,x) for x in files if x.lower().endswith('.apk')]
        if p.returncode!=0: raise RuntimeError(log or ('Unlock failed' if mode=='unlock' else 'DPT failed'))
        if not candidates: raise RuntimeError(('Unlock completed but no output APK was found.' if mode=='unlock' else 'DPT completed but no output APK was found.'))
        result=max(candidates,key=os.path.getmtime)
        if os.path.getsize(result)>MAX_OUTPUT: raise RuntimeError('Output APK exceeds 20MB.')
        filename='✧ 𝐌𝐀𝐗𝐎 𝐔𝐍𝐋𝐎𝐂𝐊 ✧.apk' if mode=='unlock' else '✧ 𝐂𝐑𝐄𝐀𝐓𝐄 𝐁𝐘 𝐌𝐀𝐗𝐎 ✧.apk'
        caption=F('UNLOCK BY MAXO')+'\n@Pv_MAXO' if mode=='unlock' else F('CREATE BY MAXO')+'\n@Pv_MAXO'
        with open(result,'rb') as f: await update.effective_message.reply_document(f,filename=filename,caption=caption)
        stats(uid,True); await msg.edit_text(FA['unlock_success' if mode=='unlock' else 'success'],parse_mode=HTML)
        if STICKER_SUCCESS:
            try: await update.effective_message.reply_sticker(STICKER_SUCCESS)
            except Exception: pass
        if uid!=ADMIN_ID: await say(update,b('📊 باقی‌مانده شما')+'\n\n'+quota_text(uid))
    except asyncio.TimeoutError:
        try: p.kill()
        except Exception: pass
        stats(uid,False); refund(uid,mode,tok); await msg.edit_text(FA['timeout'],parse_mode=HTML)
    except Exception as e:
        stats(uid,False); refund(uid,mode,tok); await msg.edit_text(FA['failed']+'\n\n<code>'+esc(str(e)[-3000:])+'</code>',parse_mode=HTML)
    finally: shutil.rmtree(job,ignore_errors=True)
async def dpt(update,ctx):
    ensure(update.effective_user); r=update.message.reply_to_message
    if not r or not r.document: await say(update,b('↩️ روی یک '+APK+' ریپلای کنید و /dpt را بفرستید.')); return
    await process_apk(update,ctx,r.document,'dpt',r)

# ---------- menu ----------
async def menu(update,ctx,key):
    uid=update.effective_user.id; u=update.effective_user
    if key=='dpt':
        ctx.user_data['mode']='dpt'; t=HEAD+'\n\n'+FA['ready']
        if uid!=ADMIN_ID: t+='\n\n'+quota_text(uid)
        await say(update,t,main_kb(uid)); return
    if key=='unlock':
        ctx.user_data['mode']='unlock'; t=HEAD+'\n\n'+FA['unlock_ready']
        if uid!=ADMIN_ID: t+='\n\n'+quota_text(uid)
        await say(update,t,main_kb(uid)); return
    if key=='buy':
        c=con(); ps=c.execute('SELECT * FROM plans ORDER BY price,id').fetchall(); c.close()
        if not ps: await say(update,HEAD+'\n\n'+b('😔 در حال حاضر پلنی برای خرید موجود نیست.'),main_kb(uid)); return
        t=HEAD+'\n\n'+b('💎 پلن‌های اشتراک')+'\n'+b('👇 پلن مورد نظر خود را انتخاب کنید')+'\n\n'; rows=[]
        for p in ps: t+=plan_card(p)+'\n'; rows.append([IB(F(p['name'])+'  |  '+money(p['price'])+' '+F('TMN'),'buy:'+str(p['id']))])
        await say(update,t,IK(*rows)); return
    if key=='account': await say(update,account_text(uid),main_kb(uid)); return
    if key=='support':
        ctx.user_data['state']='support'
        await say(update,HEAD+'\n\n'+b('🎧 پشتیبانی')+'\n'+b('📩 پیام خود را (متن، عکس، فیلم + کپشن) ارسال کنید.'),cancel_kb()); return
    # ---- admin ----
    if key=='admin': await say(update,ADM+'\n\n'+b('🎛 به پنل مدیریت خوش آمدید'),admin_kb(uid)); return
    if key=='users':
        c=con(); rows=c.execute('SELECT * FROM users ORDER BY last_seen DESC LIMIT 100').fetchall(); c.close(); chunks=[]; cur=ADM+'\n\n'+b('👥 کاربران')
        for r in rows:
            un='@'+esc(r['username']) if r['username'] else '—'
            item='\n\n'+b(esc(r['first_name'] or 'بدون نام'))+' '+un+'\n'+b('🆔')+' <code>'+str(r['id'])+'</code> '+b(f"| 🛠 {r['total_jobs']} | 💎 {r['sub_dpt'] or 0} / {r['sub_unlock'] or 0} | "+('🚫 مسدود' if r['blocked'] else '✅ فعال'))
            if len(cur)+len(item)>3800: chunks.append(cur); cur=''
            cur+=item
        chunks.append(cur)
        for ch in chunks: await say(update,ch,admin_kb(uid))
        return
    if key=='stats':
        c=con(); a=c.execute('SELECT COUNT(*) FROM users').fetchone()[0]; bl=c.execute('SELECT COUNT(*) FROM users WHERE blocked=1').fetchone()[0]; j=c.execute('SELECT COALESCE(SUM(total_jobs),0) FROM users').fetchone()[0]; ok=c.execute('SELECT COALESCE(SUM(successful_jobs),0) FROM users').fetchone()[0]; fail=c.execute('SELECT COALESCE(SUM(failed_jobs),0) FROM users').fetchone()[0]
        sc,sr=c.execute("SELECT COUNT(*),COALESCE(SUM(price),0) FROM receipts WHERE status='approved'").fetchone(); pend=c.execute("SELECT COUNT(*) FROM receipts WHERE status='pending'").fetchone()[0]; c.close()
        await say(update,b('✦ 𝐒𝐓𝐀𝐓𝐒 ✦')+'\n\n'+b(f'👥 کاربران: {a}')+'\n'+b(f'🚫 مسدود: {bl}')+'\n'+b(f'🛠 پردازش‌ها: {j}')+'\n'+b(f'✅ موفق: {ok}')+'\n'+b(f'❌ ناموفق: {fail}')+'\n\n'+b(f'💎 اشتراک‌های فروخته‌شده: {sc}')+'\n'+b(f'💰 مجموع فروش: {money(sr)} تومان')+'\n'+b(f'⏳ رسیدهای در انتظار: {pend}'),admin_kb(uid)); return
    if key=='plans':
        t,kb=plans_view(); await say(update,t,kb); return
    if key=='card':
        t,kb=card_view(); await say(update,t,kb); return
    if key=='limits':
        t,kb=limits_view(); await say(update,t,kb); return
    if key=='reset':
        await say(update,ADM+'\n\n'+b('⚠️ سهمیه رایگان همه کاربران بازنشانی شود و برای همه پیام ارسال شود؟'),IK([IB(F('CONFIRM'),'rs:ok'),IB(F('CANCEL'),'rs:no')])); return
    if key=='broadcast':
        ctx.user_data['state']='broadcast'; await say(update,ADM+'\n\n'+b('📢 پیام همگانی را ارسال کنید.')+'\n'+b('🖼 متن، عکس، فیلم و ... با کپشن، بولد، نقل‌قول و همه فرمت‌ها پشتیبانی می‌شود.'),cancel_kb()); return
    if key=='backup':
        raw=dump_db(); fname='MAXO_BACKUP_'+datetime.utcnow().strftime('%Y%m%d_%H%M%S')+'.json'
        await update.effective_message.reply_document(raw,filename=fname,caption=b('💾 بکاپ کامل اطلاعات و تنظیمات')+'\n'+b('♻️ برای بازگردانی از دکمه '+F('RESTORE')+' استفاده کنید.'),parse_mode=HTML,reply_markup=admin_kb(uid)); return
    if key=='restore':
        ctx.user_data['state']='restore'; await say(update,ADM+'\n\n'+b('♻️ فایل بکاپ را ارسال کنید.')+'\n'+b('⚠️ همه اطلاعات فعلی با اطلاعات بکاپ جایگزین می‌شود.'),cancel_kb()); return
    if key=='enable': set_enabled(True); await say(update,b('✅ پردازش '+DPTF+' فعال شد.'),admin_kb(uid)); return
    if key=='disable': set_enabled(False); await say(update,b('⛔ پردازش '+DPTF+' غیرفعال شد.'),admin_kb(uid)); return
    if key=='close': await say(update,HEAD,main_kb(uid)); return

# ---------- stateful inputs ----------
async def st_receipt(update,ctx,pid):
    m=update.message; u=update.effective_user; p=plan(pid)
    if not (m.photo or m.document or m.text): await say(update,b('⚠️ لطفاً تصویر رسید را ارسال کنید.')); return
    ctx.user_data.pop('state',None)
    if not p: await say(update,b('⚠️ این پلن دیگر موجود نیست.'),main_kb(u.id)); return
    c=con(); rid=c.execute('INSERT INTO receipts(user_id,plan_name,price,dpt_uses,unlock_uses,status,created_at) VALUES(?,?,?,?,?,?,?)',(u.id,p['name'],p['price'],p['dpt_uses'],p['unlock_uses'],'pending',datetime.utcnow().isoformat())).lastrowid; c.commit(); c.close()
    un='@'+esc(u.username) if u.username else '—'
    try:
        await ctx.bot.send_message(ADMIN_ID,b(f'🧾 رسید جدید #{rid}')+'\n\n'+b('👤 کاربر:')+' '+b(esc(u.full_name))+'\n'+b('🔗 یوزرنیم:')+' '+un+'\n'+b('🆔 آیدی:')+' <code>'+str(u.id)+'</code>\n'+b('🎁 پلن:')+' '+b(fn(p['name']))+'\n'+b('💰 مبلغ:')+' '+b(money(p['price'])+' تومان'),parse_mode=HTML)
        await ctx.bot.copy_message(ADMIN_ID,m.chat_id,m.message_id,reply_markup=IK([IB(F('APPROVE'),f'rc:ok:{rid}'),IB(F('REJECT'),f'rc:no:{rid}')]))
    except Exception: pass
    await say(update,HEAD+'\n\n'+b('✅ رسید شما ارسال شد.')+'\n'+b('⏳ پس از تایید ادمین، اشتراک شما فعال می‌شود.'),main_kb(u.id))
async def st_support(update,ctx):
    m=update.message; u=update.effective_user; ctx.user_data.pop('state',None); un='@'+esc(u.username) if u.username else '—'
    try:
        await ctx.bot.send_message(ADMIN_ID,b('📩 پیام جدید پشتیبانی')+'\n\n'+b('👤 کاربر:')+' '+b(esc(u.full_name))+'\n'+b('🔗 یوزرنیم:')+' '+un+'\n'+b('🆔 آیدی:')+' <code>'+str(u.id)+'</code>',parse_mode=HTML)
        await ctx.bot.copy_message(ADMIN_ID,m.chat_id,m.message_id,reply_markup=IK([IB(F('REPLY'),f'sp:r:{u.id}'),IB(F('IGNORE'),'sp:x')]))
    except Exception: pass
    await say(update,HEAD+'\n\n'+b('✅ پیام شما برای پشتیبانی ارسال شد.')+'\n'+b('⏳ منتظر پاسخ بمانید.'),main_kb(u.id))
async def fanout(ctx,ids,fnc):
    ok=bad=0
    for i in ids:
        try: await retry(lambda: fnc(i)); ok+=1
        except Exception: bad+=1
        await asyncio.sleep(.04)
    return ok,bad
async def state_input(update,ctx,st):
    m=update.message; uid=update.effective_user.id; a,_,x=st.partition(':'); s=(m.text or '').strip()
    if a=='receipt': await st_receipt(update,ctx,int(x)); return
    if a=='support': await st_support(update,ctx); return
    if uid!=ADMIN_ID: ctx.user_data.pop('state',None); return
    if a=='broadcast':
        c=con(); ids=[r['id'] for r in c.execute('SELECT id FROM users WHERE blocked=0')]; c.close(); ctx.user_data.pop('state',None)
        await say(update,b('📢 در حال ارسال...'))
        ok,bad=await fanout(ctx,ids,lambda i: ctx.bot.copy_message(i,m.chat_id,m.message_id))
        await say(update,b('✦ 𝐁𝐑𝐎𝐀𝐃𝐂𝐀𝐒𝐓 𝐃𝐎𝐍𝐄 ✦')+'\n\n'+b(f'✅ ارسال موفق: {ok}')+'\n'+b(f'❌ ناموفق: {bad}'),admin_kb(uid)); return
    if a=='restore':
        d=m.document
        if not d: await say(update,b('⚠️ فایل بکاپ را به صورت فایل ارسال کنید.')); return
        try:
            f=await d.get_file(); raw=bytes(await f.download_as_bytearray()); n=restore_db(json.loads(raw.decode('utf-8')))
        except Exception as e:
            await say(update,b('❌ بازگردانی ناموفق بود.')+'\n<code>'+esc(str(e)[:500])+'</code>'); return
        ctx.user_data.pop('state',None); await say(update,ADM+'\n\n'+b('✅ اطلاعات با موفقیت بازگردانی شد.')+'\n'+b(f'📦 تعداد رکوردها: {n}'),admin_kb(uid)); return
    if a=='reply':
        ctx.user_data.pop('state',None)
        try:
            await ctx.bot.send_message(int(x),HEAD+'\n\n'+b('💬 پاسخ پشتیبانی:'),parse_mode=HTML)
            await ctx.bot.copy_message(int(x),m.chat_id,m.message_id)
            await say(update,b('✅ پاسخ ارسال شد.'),admin_kb(uid))
        except Exception: await say(update,b('❌ ارسال پاسخ ممکن نشد.'),admin_kb(uid))
        return
    if a=='card':
        if not s: await say(update,b('⚠️ متن ارسال کنید.')); return
        setv('card_number' if x=='num' else 'card_name',s[:100]); ctx.user_data.pop('state',None); t,kb=card_view(); await say(update,b('✅ ذخیره شد.'),admin_kb(uid)); await say(update,t,kb); return
    if a=='setlim':
        n=num(s)
        if n is None: await say(update,b('⚠️ فقط عدد ارسال کنید.')); return
        setv(x+'_limit',n); ctx.user_data.pop('state',None); t,kb=limits_view(); await say(update,b('✅ ذخیره شد.'),admin_kb(uid)); await say(update,t,kb); return
    if a=='addplan':
        np=ctx.user_data.setdefault('np',{})
        if x=='name':
            if not s: await say(update,b('⚠️ نام پلن را بنویسید.')); return
            np['name']=s[:40]; ctx.user_data['state']='addplan:price'; await say(update,b('💰 قیمت پلن را به تومان ارسال کنید (فقط عدد).')); return
        n=num(s)
        if n is None: await say(update,b('⚠️ فقط عدد ارسال کنید.')); return
        if x=='price': np['price']=n; ctx.user_data['state']='addplan:dpt'; await say(update,b('🔵 تعداد دفعات استفاده از '+DPTF+' در این پلن؟ (عدد)')); return
        if x=='dpt': np['dpt']=n; ctx.user_data['state']='addplan:unlock'; await say(update,b('🔓 تعداد دفعات استفاده از '+UNL+' در این پلن؟ (عدد)')); return
        if x=='unlock':
            if np.get('dpt',0)==0 and n==0:
                ctx.user_data['state']='addplan:dpt'; await say(update,b('⚠️ حداقل یکی از دو مقدار باید بیشتر از 0 باشد.')+'\n'+b('🔵 دوباره تعداد '+DPTF+' را ارسال کنید.')); return
            c=con(); c.execute('INSERT INTO plans(name,price,dpt_uses,unlock_uses) VALUES(?,?,?,?)',(np['name'],np['price'],np['dpt'],n)); c.commit(); c.close()
            ctx.user_data.pop('state',None); ctx.user_data.pop('np',None); await say(update,b('✅ پلن با موفقیت اضافه شد.'),admin_kb(uid)); t,kb=plans_view(); await say(update,t,kb); return

# ---------- router ----------
async def router(update,ctx):
    m=update.message
    if not m or not update.effective_user: return
    u=update.effective_user; ensure(u); uid=u.id; s=(m.text or '').strip(); key=BTR.get(s)
    if key=='cancel':
        old=ctx.user_data.pop('state',None); ctx.user_data.pop('mode',None); ctx.user_data.pop('np',None)
        kb=admin_kb(uid) if uid==ADMIN_ID and old and old.split(':')[0] not in ('receipt','support') else main_kb(uid)
        await say(update,FA['cancelled'],kb); return
    if blocked(uid): await say(update,FA['blocked']); return
    if key:
        if key in ADMIN_KEYS and uid!=ADMIN_ID: return
        ctx.user_data.pop('state',None); ctx.user_data.pop('np',None)
        if key not in ('dpt','unlock'): ctx.user_data.pop('mode',None)
        await menu(update,ctx,key); return
    st=ctx.user_data.get('state')
    if st: await state_input(update,ctx,st); return
    d=m.document
    if d:
        if not (d.file_name or '').lower().endswith('.apk'): await say(update,FA['only']); return
        if (d.file_size or 0)>MAX_INPUT: await say(update,FA['big']); return
        mode='unlock' if ctx.user_data.get('mode')=='unlock' else 'dpt'
        ctx.user_data.pop('mode',None)
        await process_apk(update,ctx,d,mode); return
    await say(update,HEAD+'\n\n'+FA['ready'],main_kb(uid))

# ---------- inline callbacks ----------
async def cb(update,ctx):
    q=update.callback_query; d=q.data or ''; uid=q.from_user.id; p=d.split(':'); M=q.message; ensure(q.from_user)
    if p[0] in ('rc','sp','pl','lim','rs','card') and uid!=ADMIN_ID: await q.answer('⛔',show_alert=True); return
    await q.answer()
    async def reply(t,kb=None): return await M.reply_text(t,parse_mode=HTML,reply_markup=kb)
    if p[0]=='buy':
        if blocked(uid): await reply(FA['blocked']); return
        pl=plan(int(p[1]))
        if not pl: await reply(b('⚠️ این پلن دیگر موجود نیست.')); return
        n=get('card_number'); nm=get('card_name')
        if not n: await reply(b('⚠️ شماره کارت هنوز توسط ادمین ثبت نشده است.')); return
        ctx.user_data['state']='receipt:'+str(pl['id'])
        await reply(HEAD+'\n\n'+b('💳 اطلاعات پرداخت')+'\n\n'+b('🎁 پلن انتخابی:')+' '+b(fn(pl['name']))+'\n'+b('💰 مبلغ قابل پرداخت:')+' '+b(money(pl['price'])+' تومان')+'\n\n'+b('🏦 شماره کارت:')+'\n<code>'+esc(n)+'</code>\n'+b('👤 به نام:')+' '+b(fn(nm or '—'))+'\n\n'+b('📸 پس از واریز، تصویر رسید را همینجا ارسال کنید.'),cancel_kb()); return
    if p[0]=='rc':
        rid=int(p[2]); c=con(); r=c.execute('SELECT * FROM receipts WHERE id=?',(rid,)).fetchone()
        if not r or r['status']!='pending': c.close(); await reply(b('⚠️ این رسید قبلاً بررسی شده است.')); return
        if p[1]=='ok':
            c.execute('UPDATE users SET sub_dpt=COALESCE(sub_dpt,0)+?,sub_unlock=COALESCE(sub_unlock,0)+?,sub_plan=? WHERE id=?',(r['dpt_uses'],r['unlock_uses'],r['plan_name'],r['user_id'])); c.execute("UPDATE receipts SET status='approved' WHERE id=?",(rid,))
        else: c.execute("UPDATE receipts SET status='rejected' WHERE id=?",(rid,))
        c.commit(); c.close()
        try: await q.edit_message_reply_markup(None)
        except Exception: pass
        await reply(b(f'✅ رسید #{rid} تایید شد.' if p[1]=='ok' else f'🚫 رسید #{rid} رد شد.'))
        try:
            if p[1]=='ok': await ctx.bot.send_message(r['user_id'],HEAD+'\n\n'+b('🎉 پرداخت شما تایید شد!')+'\n'+b('✅ اشتراک شما فعال گردید.')+'\n\n'+b('🎁 پلن:')+' '+b(fn(r['plan_name']))+'\n\n'+quota_text(r['user_id']),parse_mode=HTML)
            else: await ctx.bot.send_message(r['user_id'],HEAD+'\n\n'+b('❌ رسید شما تایید نشد.')+'\n'+b('🎧 در صورت اشتباه از بخش پشتیبانی پیگیری کنید.'),parse_mode=HTML)
        except Exception: pass
        return
    if p[0]=='sp':
        if p[1]=='x':
            try: await q.edit_message_reply_markup(None)
            except Exception: pass
            return
        ctx.user_data['state']='reply:'+p[2]; await reply(b('✍️ پاسخ خود را ارسال کنید (متن، عکس، فیلم + کپشن).'),cancel_kb()); return
    if p[0]=='pl':
        if p[1]=='add': ctx.user_data['np']={}; ctx.user_data['state']='addplan:name'; await reply(b('🎁 نام پلن را ارسال کنید.'),cancel_kb()); return
        if p[1]=='del':
            c=con(); c.execute('DELETE FROM plans WHERE id=?',(int(p[2]),)); c.commit(); c.close(); t,kb=plans_view()
            try: await q.edit_message_text(t,parse_mode=HTML,reply_markup=kb)
            except Exception: pass
            return
    if p[0]=='lim' and p[1] in FEATS:
        if p[2]=='n': ctx.user_data['state']='setlim:'+p[1]; await reply(b('🔢 تعداد مجاز رایگان برای '+F(p[1].upper())+' را ارسال کنید (عدد).'),cancel_kb()); return
        setv(p[1]+'_period','month' if per(p[1])=='week' else 'week'); t,kb=limits_view()
        try: await q.edit_message_text(t,parse_mode=HTML,reply_markup=kb)
        except Exception: pass
        return
    if p[0]=='card': ctx.user_data['state']='card:'+p[1]; await reply(b('💳 شماره کارت را ارسال کنید.' if p[1]=='num' else '👤 نام صاحب کارت را ارسال کنید.'),cancel_kb()); return
    if p[0]=='rs':
        try: await q.edit_message_reply_markup(None)
        except Exception: pass
        if p[1]=='no': await reply(FA['cancelled']); return
        setv('reset_at',datetime.utcnow().isoformat())
        c=con(); ids=[r['id'] for r in c.execute('SELECT id FROM users WHERE blocked=0')]; c.close()
        txt=HEAD+'\n\n'+b('🔄 سهمیه رایگان شما بازنشانی شد!')+'\n'+b('🚀 هم‌اکنون می‌توانید دوباره از قابلیت‌ها استفاده کنید.')
        ok,bad=await fanout(ctx,ids,lambda i: ctx.bot.send_message(i,txt,parse_mode=HTML))
        await reply(b('✅ بازنشانی انجام شد.')+'\n'+b(f'📨 ارسال موفق: {ok}')+'\n'+b(f'❌ ناموفق: {bad}')); return

# ---------- commands ----------
async def admin_cmd(update,ctx):
    ensure(update.effective_user)
    if update.effective_user.id==ADMIN_ID: await say(update,ADM+'\n\n'+b('🎛 پنل مدیریت'),admin_kb(ADMIN_ID))
async def cancel_cmd(update,ctx):
    if update.effective_user.id==ADMIN_ID:
        for k in ('state','mode','np'): ctx.user_data.pop(k,None)
        await say(update,FA['cancelled'],main_kb(ADMIN_ID))
def main():
    if not TOKEN: raise RuntimeError('BOT_TOKEN is missing.')
    if ADMIN_ID<=0: raise RuntimeError('ADMIN_ID is missing or invalid.')
    init_db(); app=Application.builder().token(TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler('start',start)); app.add_handler(CommandHandler('dpt',dpt)); app.add_handler(CommandHandler('admin',admin_cmd)); app.add_handler(CommandHandler('cancel',cancel_cmd))
    app.add_handler(CallbackQueryHandler(cb))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.StatusUpdate.ALL,router))
    app.run_polling(allowed_updates=Update.ALL_TYPES)
if __name__=='__main__': main()
