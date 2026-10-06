import re

path = "/app/main.py"
with open(path, "r", encoding="utf-8") as f:
    s = f.read()

# Add imports.
s = s.replace(
    "import asyncio, html, json, os, shutil, sqlite3, tempfile",
    "import asyncio, html, json, os, shutil, sqlite3, tempfile, re"
)

# Dex2C constants.
s = s.replace(
    "UNLOCK_MAIN='com.dpt.unpack.MainKt'\n",
    "UNLOCK_MAIN='com.dpt.unpack.MainKt'\nDEX2C_ROOT='/opt/dex2c'\nDEX2C_MAIN='/opt/dex2c/dcc.py'\n"
)

# Add feature.
s = s.replace("FEATS=('dpt','unlock')", "FEATS=('dpt','unlock','dex2c')")
s = s.replace("APK=F('APK'); DPTF=F('DPT'); UNL=F('UNLOCK')",
              "APK=F('APK'); DPTF=F('DPT'); UNL=F('UNLOCK'); D2CF=F('DEX2C')")

# Add messages.
needle = "  cancelled=b('↩️ عملیات لغو شد.'),"
replacement = """  cancelled=b('↩️ عملیات لغو شد.'),
  dex2c_ready=b('🛡 فایل APK را ارسال کنید. سپس فایل maxo.txt را ارسال کنید.'),
  dex2c_txt_ready=b('📝 حالا فایل maxo.txt را ارسال کنید.'),
  dex2c_processing=HEAD+'\\\\n\\\\n'+b('🛡 در حال اجرای DEX2C...'),
  noquota_dex2c=HEAD+'\\\\n\\\\n'+b('❌ سهمیه DEX2C شما تمام شده است.')+'\\\\n'+b('💎 برای ادامه از بخش خرید اشتراک، پلن تهیه کنید.'),
  dex2c_success=HEAD+'\\\\n\\\\n'+b('✅ DEX2C با موفقیت انجام شد.'),
"""
s = s.replace(needle, replacement)

# Button and reverse map.
s = s.replace(
    "_BT=dict(dpt='DPT',unlock='UNLOCK',buy='BUY PLAN'",
    "_BT=dict(dpt='DPT',unlock='UNLOCK',dex2c='DEX2C',buy='BUY PLAN'"
)

# DB users: add subscription column migration.
s = s.replace(
    "for n,t in (('sub_dpt','INTEGER DEFAULT 0'),('sub_unlock','INTEGER DEFAULT 0'),('sub_plan',\"TEXT DEFAULT ''\")):",
    "for n,t in (('sub_dpt','INTEGER DEFAULT 0'),('sub_unlock','INTEGER DEFAULT 0'),('sub_dex2c','INTEGER DEFAULT 0'),('sub_plan',\"TEXT DEFAULT ''\")):"
)

# Settings.
s = s.replace(
    "('enabled','1'),('dpt_limit','10'),('dpt_period','month'),('unlock_limit','1'),('unlock_period','month'),",
    "('enabled','1'),('dpt_limit','10'),('dpt_period','month'),('unlock_limit','1'),('unlock_period','month'),('dex2c_limit','1'),('dex2c_period','month'),"
)

# Main keyboard.
s = s.replace(
    "rows=[[B(BT['dpt']),B(BT['unlock'])],[B(BT['buy']),B(BT['account'])]",
    "rows=[[B(BT['dpt']),B(BT['unlock'])],[B(BT['dex2c'])],[B(BT['buy']),B(BT['account'])]"
)

# Plan card: show dex2c uses.
s = s.replace(
    "b(f\"🔓 {UNL}: {p['unlock_uses']} بار\")",
    "b(f\"🔓 {UNL}: {p['unlock_uses']} بار\")+'\\\\n'+b(f\"🛡 {D2CF}: {p['dex2c_uses']} بار\")"
)

# Plans table schema.
s = s.replace(
    "CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,price INTEGER DEFAULT 0,dpt_uses INTEGER DEFAULT 0,unlock_uses INTEGER DEFAULT 0)",
    "CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,price INTEGER DEFAULT 0,dpt_uses INTEGER DEFAULT 0,unlock_uses INTEGER DEFAULT 0,dex2c_uses INTEGER DEFAULT 0)"
)
# Receipt table + migration.
s = s.replace(
    "CREATE TABLE IF NOT EXISTS receipts(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,plan_name TEXT,price INTEGER,dpt_uses INTEGER DEFAULT 0,unlock_uses INTEGER DEFAULT 0,status TEXT DEFAULT 'pending',created_at TEXT)",
    "CREATE TABLE IF NOT EXISTS receipts(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,plan_name TEXT,price INTEGER,dpt_uses INTEGER DEFAULT 0,unlock_uses INTEGER DEFAULT 0,dex2c_uses INTEGER DEFAULT 0,status TEXT DEFAULT 'pending',created_at TEXT)"
)

# Migration for old plans table.
s = s.replace(
    "for k,v in (('enabled','1'),",
    "pcols={r[1] for r in c.execute('PRAGMA table_info(plans)')}\\n    if 'dex2c_uses' not in pcols: c.execute('ALTER TABLE plans ADD COLUMN dex2c_uses INTEGER DEFAULT 0')\\n    for k,v in (('enabled','1'),"
)

# Limits UI gets FEATS automatically, but plan add flow needs dex2c.
s = s.replace(
    "if x=='dpt': np['dpt']=n; ctx.user_data['state']='addplan:unlock'; await say(update,b('🔓 تعداد دفعات استفاده از '+UNL+' در این پلن؟ (عدد)')); return",
    "if x=='dpt': np['dpt']=n; ctx.user_data['state']='addplan:unlock'; await say(update,b('🔓 تعداد دفعات استفاده از '+UNL+' در این پلن؟ (عدد)')); return"
)
s = s.replace(
    "if x=='unlock':\n            if np.get('dpt',0)==0 and n==0:",
    "if x=='unlock':\n            np['unlock']=n; ctx.user_data['state']='addplan:dex2c'; await say(update,b('🛡 تعداد دفعات استفاده از '+D2CF+' در این پلن؟ (عدد)')); return\n        if x=='dex2c':\n            if np.get('dpt',0)==0 and np.get('unlock',0)==0 and n==0:\n                ctx.user_data['state']='addplan:dpt'; await say(update,b('⚠️ حداقل یکی از سه مقدار باید بیشتر از 0 باشد.')+'\\\\n'+b('🔵 دوباره تعداد '+DPTF+' را ارسال کنید.')); return"
)
# Replace old insertion tail after the newly inserted conditional.
s = s.replace(
    "c=con(); c.execute('INSERT INTO plans(name,price,dpt_uses,unlock_uses) VALUES(?,?,?,?)',(np['name'],np['price'],np['dpt'],n)); c.commit(); c.close()",
    "c=con(); c.execute('INSERT INTO plans(name,price,dpt_uses,unlock_uses,dex2c_uses) VALUES(?,?,?,?,?)',(np['name'],np['price'],np['dpt'],np.get('unlock',0),n)); c.commit(); c.close()"
)

# Receipt schema.
s = s.replace(
    "INSERT INTO receipts(user_id,plan_name,price,dpt_uses,unlock_uses,status,created_at) VALUES(?,?,?,?,?,?,?)",
    "INSERT INTO receipts(user_id,plan_name,price,dpt_uses,unlock_uses,dex2c_uses,status,created_at) VALUES(?,?,?,?,?,?,?,?)"
)
s = s.replace(
    "(u.id,p['name'],p['price'],p['dpt_uses'],p['unlock_uses'],'pending',datetime.utcnow().isoformat())",
    "(u.id,p['name'],p['price'],p['dpt_uses'],p['unlock_uses'],p['dex2c_uses'],'pending',datetime.utcnow().isoformat())"
)
# Receipt approval.
s = s.replace(
    "UPDATE users SET sub_dpt=COALESCE(sub_dpt,0)+?,sub_unlock=COALESCE(sub_unlock,0)+?,sub_plan=? WHERE id=?",
    "UPDATE users SET sub_dpt=COALESCE(sub_dpt,0)+?,sub_unlock=COALESCE(sub_unlock,0)+?,sub_dex2c=COALESCE(sub_dex2c,0)+?,sub_plan=? WHERE id=?"
)
s = s.replace(
    "(r['dpt_uses'],r['unlock_uses'],r['plan_name'],r['user_id'])",
    "(r['dpt_uses'],r['unlock_uses'],r['dex2c_uses'],r['plan_name'],r['user_id'])"
)

# Plan add prompt.
s = s.replace(
    "await say(update,b('🔓 تعداد دفعات استفاده از '+UNL+' در این پلن؟ (عدد)')); return",
    "await say(update,b('🔓 تعداد دفعات استفاده از '+UNL+' در این پلن؟ (عدد)')); return"
)

# Account quota display uses FEATS automatically.

# Insert DEX2C helpers before core processing.
marker = "# ---------- core processing ----------"
helper = r