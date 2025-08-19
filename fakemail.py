import os
import logging
import json
import random
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode

# ========= CONFIG ==========
BOT_TOKEN = os.environ.get("5989609124:AAGEePfgxnqfw-kEYnmBufKL1sO3SE4uj-Q")
ADMIN_ID = int(os.environ.get("5923090134", "0"))
DATA_FILE = "data.json"
# ===========================

logging.basicConfig(level=logging.INFO)

# Load or initialize database
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        db = json.load(f)
else:
    db = {"user_mails": {}, "mail_owners": {}}

def save_db():
    with open(DATA_FILE, "w") as f:
        json.dump(db, f, indent=2)

# Providers and domains
providers = {
    "1secmail": ["1secmail.com", "dcctb.com", "esiix.com"],
    "mailtm": ["mail.tm"]
}

# ========= Helper Functions =========
def generate_random_username():
    return "user" + str(random.randint(10000, 99999))

async def get_inbox(mail):
    if "@1secmail" in mail or any(mail.endswith("@" + d) for d in providers["1secmail"]):
        login, domain = mail.split("@")
        url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}"
        return requests.get(url).json()
    elif "@mail.tm" in mail:
        return [{"from": "noreply@mail.tm", "subject": "Sample Mail", "date": "Today"}]
    return []

def ensure_user(uid):
    if str(uid) not in db["user_mails"]:
        db["user_mails"][str(uid)] = {"active": None, "mails": [], "trash": []}

# ========= USER COMMANDS =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Use /cmds to see all commands.")

async def cmds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    commands = [
        "/start - Welcome message",
        "/cmds - Show all commands",
        "/newmail - Create a new fake mail (choose provider & domain)",
        "/mymail - Show your current active mail",
        "/inbox - View inbox of your current mail",
        "/setmail email@domain.com - Switch to one of your saved mails",
        "/transfer @user - Transfer your current mail to another user",
        "/deletemail - Delete current mail and auto-switch",
        "/add email@domain.com - Restore a trashed mail",
        "/cleartrash - Empty your trash"
    ]
    msg = "📌 Available Commands:\n" + "\n".join(commands)

    if uid == ADMIN_ID:
        admin_cmds = [
            "\n👑 Admin Commands:",
            "/adminsetmail @user email@domain.com - Force assign mail",
            "/admindelete email@domain.com - Delete any mail",
            "/admininbox email@domain.com - Read inbox of any mail",
            "/adminlist - List all mails and owners",
            "/adminusers - List all users and their mails"
        ]
        msg += "\n" + "\n".join(admin_cmds)

    await update.message.reply_text(msg)

# ========= /newmail =========
async def newmail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ensure_user(uid)
    keyboard = []
    for prov, domains in providers.items():
        row = []
        for d in domains:
            row.append(InlineKeyboardButton(f"{prov}: {d}", callback_data=f"create:{prov}:{d}"))
        keyboard.append(row)
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📧 Choose provider & domain:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("create:"):
        _, prov, domain = data.split(":")
        mail = f"{generate_random_username()}@{domain}"
        uid = query.from_user.id
        ensure_user(uid)
        if mail in db["mail_owners"]:
            await query.edit_message_text("⚠️ Mail already taken. Try again.")
            return
        db["user_mails"][str(uid)]["mails"].append(mail)
        db["user_mails"][str(uid)]["active"] = mail
        db["mail_owners"][mail] = uid
        save_db()
        await query.edit_message_text(f"✅ New mail created: `{mail}`", parse_mode=ParseMode.MARKDOWN)

# ========= Mail Management =========
async def mymail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ensure_user(uid)
    active = db["user_mails"][str(uid)]["active"]
    if not active:
        await update.message.reply_text("❌ No active mail. Use /newmail.")
        return
    await update.message.reply_text(f"📧 Your current mail: `{active}`", parse_mode=ParseMode.MARKDOWN)

async def inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ensure_user(uid)
    active = db["user_mails"][str(uid)]["active"]
    if not active:
        await update.message.reply_text("❌ No active mail.")
        return
    msgs = await get_inbox(active)
    if not msgs:
        await update.message.reply_text("📭 Inbox is empty.")
        return
    reply = f"📥 Inbox for `{active}`:\n"
    for m in msgs:
        reply += f"- From: {m['from']}, Subject: {m['subject']}, Date: {m.get('date','N/A')}\n"
    await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)

async def setmail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ensure_user(uid)
    mails = db["user_mails"][str(uid)]["mails"]
    if not mails:
        await update.message.reply_text("❌ You have no saved mails.")
        return
    if context.args:
        mail_choice = context.args[0]
        if mail_choice not in mails:
            await update.message.reply_text("❌ Mail not found in your saved mails.")
            return
        db["user_mails"][str(uid)]["active"] = mail_choice
        save_db()
        await update.message.reply_text(f"✅ Active mail set to `{mail_choice}`", parse_mode=ParseMode.MARKDOWN)
        return
    reply = "📧 Your saved mails:\n"
    for m in mails:
        reply += f"- {m}\n"
    reply += "\nUse /setmail email@domain.com to set as active."
    await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)

async def transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ensure_user(uid)
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /transfer @user")
        return
    target_id = int(context.args[0].replace("@",""))
    ensure_user(target_id)
    active = db["user_mails"][str(uid)]["active"]
    if not active:
        await update.message.reply_text("❌ No active mail to transfer.")
        return
    if active in db["user_mails"][str(target_id)]["mails"]:
        await update.message.reply_text("⚠️ Target already owns this mail.")
        return
    db["user_mails"][str(uid)]["mails"].remove(active)
    db["user_mails"][str(target_id)]["mails"].append(active)
    db["user_mails"][str(uid)]["active"] = db["user_mails"][str(uid)]["mails"][-1] if db["user_mails"][str(uid)]["mails"] else None
    db["user_mails"][str(target_id)]["active"] = active
    db["mail_owners"][active] = target_id
    save_db()
    await update.message.reply_text(f"✅ Mail `{active}` transferred successfully to user {target_id}", parse_mode=ParseMode.MARKDOWN)

async def deletemail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ensure_user(uid)
    active = db["user_mails"][str(uid)]["active"]
    if not active:
        await update.message.reply_text("❌ No active mail to delete.")
        return
    db["user_mails"][str(uid)]["mails"].remove(active)
    db["user_mails"][str(uid)]["trash"].append(active)
    db["user_mails"][str(uid)]["active"] = db["user_mails"][str(uid)]["mails"][-1] if db["user_mails"][str(uid)]["mails"] else None
    db["mail_owners"].pop(active, None)
    save_db()
    await update.message.reply_text(f"🗑 Mail `{active}` deleted successfully.", parse_mode=ParseMode.MARKDOWN)

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ensure_user(uid)
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /add email@domain.com")
        return
    mail = context.args[0]
    if mail not in db["user_mails"][str(uid)]["trash"]:
        await update.message.reply_text("❌ Mail not found in your trash.")
        return
    if mail in db["mail_owners"]:
        await update.message.reply_text("❌ Mail already owned by another user.")
        return
    db["user_mails"][str(uid)]["trash"].remove(mail)
    db["user_mails"][str(uid)]["mails"].append(mail)
    db["user_mails"][str(uid)]["active"] = mail
    db["mail_owners"][mail] = uid
    save_db()
    await update.message.reply_text(f"✅ Mail `{mail}` restored successfully.", parse_mode=ParseMode.MARKDOWN)

async def cleartrash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ensure_user(uid)
    db["user_mails"][str(uid)]["trash"].clear()
    save_db()
    await update.message.reply_text("🗑 Trash cleared successfully.")

# ========= ADMIN COMMANDS =========
async def adminlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not db["mail_owners"]:
        await update.message.reply_text("📭 No mails created.")
        return
    reply = "👑 All Mails:\n"
    for mail, owner in db["mail_owners"].items():
        reply += f"{mail} -> {owner}\n"
    await update.message.reply_text(reply)

async def adminsetmail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: /adminsetmail @user email@domain.com")
        return
    user_id = int(context.args[0].replace("@",""))
    mail = context.args[1]
    ensure_user(user_id)
    if mail in db["mail_owners"]:
        await update.message.reply_text("❌ Mail already owned by someone.")
        return
    db["user_mails"][str(user_id)]["mails"].append(mail)
    db["user_mails"][str(user_id)]["active"] = mail
    db["mail_owners"][mail] = user_id
    save_db()
    await update.message.reply_text(f"👑 Mail `{mail}` assigned to user {user_id}", parse_mode=ParseMode.MARKDOWN)

async def admindelete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /admindelete email@domain.com")
        return
    mail = context.args[0]
    if mail not in db["mail_owners"]:
        await update.message.reply_text("❌ Mail not found.")
        return
    owner = db["mail_owners"].pop(mail)
    if str(owner) in db["user_mails"] and mail in db["user_mails"][str(owner)]["mails"]:
        db["user_mails"][str(owner)]["mails"].remove(mail)
        if db["user_mails"][str(owner)]["active"] == mail:
            db["user_mails"][str(owner)]["active"] = None
    save_db()
    await update.message.reply_text(f"🗑 Mail `{mail}` deleted.", parse_mode=ParseMode.MARKDOWN)

async def admininbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /admininbox email@domain.com")
        return
    mail = context.args[0]
    msgs = await get_inbox(mail)
    if not msgs:
        await update.message.reply_text(f"📭 Inbox empty for `{mail}`", parse_mode=ParseMode.MARKDOWN)
        return
    reply = f"👑 Inbox for `{mail}`:\n"
    for m in msgs:
        reply += f"- From: {m['from']}, Subject: {m['subject']}, Date: {m.get('date','N/A')}\n"
    await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)

async def adminusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not db["user_mails"]:
        await update.message.reply_text("📭 No users yet.")
        return
    msg = "👑 Users and their mails:\n\n"
    for uid_str, data in db["user_mails"].items():
        uid = int(uid_str)
        try:
            chat = await context.bot.get_chat(uid)
            username = f"@{chat.username}" if chat.username else "N/A"
        except:
            username = "N/A"
        active = data.get("active", "None")
        saved = ", ".join(data.get("mails", [])) or "None"
        trash = ", ".join(data.get("trash", [])) or "None"
        msg += f"Username: {username}\nUser ID: {uid}\nActive Mail: {active}\nSaved Mails: {saved}\nTrash: {trash}\n\n"
    await update.message.reply_text(msg)

# ========= BOT SETUP =========
app = Application.builder().token(BOT_TOKEN).build()

# User handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("cmds", cmds))
app.add_handler(CommandHandler("newmail", newmail))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(CommandHandler("mymail", mymail))
app.add_handler(CommandHandler("inbox", inbox))
app.add_handler(CommandHandler("setmail", setmail))
app.add_handler(CommandHandler("transfer", transfer))
app.add_handler(CommandHandler("deletemail", deletemail))
app.add_handler(CommandHandler("add", add))
app.add_handler(CommandHandler("cleartrash", cleartrash))

# Admin handlers
app.add_handler(CommandHandler("adminlist", adminlist))
app.add_handler(CommandHandler("adminsetmail", adminsetmail))
app.add_handler(CommandHandler("admindelete", admindelete))
app.add_handler(CommandHandler("admininbox", admininbox))
app.add_handler(CommandHandler("adminusers", adminusers))

# ========= RUN BOT =========
if __name__ == "__main__":
    print("Bot started...")
    app.run_polling()
