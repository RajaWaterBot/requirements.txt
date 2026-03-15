# main.py
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import qrcode
import os
import config
import database as db

bot = telebot.TeleBot(config.BOT_TOKEN)

# --- Keyboards ---
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🛍 Products", "👤 Account", "💳 Deposit", "💸 Withdraw", "🎁 Refer & Earn", "📞 Support")
    return markup

def cancel_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("❌ Cancel")
    return markup

# --- Start Command ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.chat.id
    ref_by = None
    if len(message.text.split()) > 1:
        try: ref_by = int(message.text.split()[1])
        except: pass
    
    db.add_user(user_id, ref_by)
    bot.send_message(user_id, "✅ Welcome to our Bot!", reply_markup=main_menu())

# --- User Menus ---
@bot.message_handler(func=lambda m: m.text == "❌ Cancel")
def cancel_action(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    bot.send_message(message.chat.id, "❌ Process has been cancelled.", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "👤 Account")
def account_menu(message):
    user = db.get_user(message.chat.id)
    text = f"""👤 **My Account**
ID: `{user['user_id']}`
💰 **Balance:** ₹{user['balance']:.2f}

📊 **Statistics:**
Total Recharge: ₹{user['total_recharge']}
Total Refer: {user['total_refer']}
Refer Income: ₹{user['refer_income']}
💳 Wallet: {user['wallet'] if user['wallet'] else 'Not Set'}"""
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📞 Support")
def support_menu(message):
    bot.send_message(message.chat.id, f"For any help or query, please contact our support team: {config.SUPPORT_BOT}")

@bot.message_handler(func=lambda m: m.text == "🎁 Refer & Earn")
def refer_menu(message):
    user = db.get_user(message.chat.id)
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={message.chat.id}"
    text = f"""🎁 **Refer & Earn System**
Invite your friends and earn a commission on every recharge!
Level 1: 25% | Level 2: 3% | Level 3: 2%

🔗 **Your Referral Link:**
`{ref_link}`"""
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# --- Deposit System ---
@bot.message_handler(func=lambda m: m.text == "💳 Deposit")
def deposit_init(message):
    msg = bot.send_message(message.chat.id, "Enter the amount you want to Deposit (Minimum ₹50):", reply_markup=cancel_menu())
    bot.register_next_step_handler(msg, process_deposit_amount)

def process_deposit_amount(message):
    if message.text == "❌ Cancel": return cancel_action(message)
    try:
        amount = int(message.text)
        if amount < 50: raise ValueError
        
        # Generate QR Code
        upi_url = f"upi://pay?pa={config.UPI_ID}&pn={config.UPI_NAME}&am={amount}&cu=INR"
        qr = qrcode.make(upi_url)
        qr_path = f"qr_{message.chat.id}.png"
        qr.save(qr_path)
        
        with open(qr_path, "rb") as photo:
            msg = bot.send_photo(message.chat.id, photo, caption=f"🔰 **Amount:** ₹{amount}\nScan the QR Code to pay or copy the UPI ID below:\n`{config.UPI_ID}`\n\n✅ After payment, enter your **12-digit UTR/Ref Number** below:", parse_mode="Markdown", reply_markup=cancel_menu())
        os.remove(qr_path)
        bot.register_next_step_handler(msg, lambda m: process_utr(m, amount))
    except:
        bot.send_message(message.chat.id, "❌ Please enter a valid amount!", reply_markup=main_menu())

def process_utr(message, amount):
    if message.text == "❌ Cancel": return cancel_action(message)
    utr = message.text
    user_id = message.chat.id
    
    bot.send_message(user_id, "⏳ Your deposit request has been sent to the admin. Please wait for approval.", reply_markup=main_menu())
    
    # Send to Log Group
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Approve", callback_data=f"dep_app_{user_id}_{amount}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"dep_rej_{user_id}")
    )
    bot.send_message(config.LOG_GROUP_ID, f"💳 **New Deposit Request**\nUser: `{user_id}`\nAmount: ₹{amount}\nUTR: `{utr}`", parse_mode="Markdown", reply_markup=markup)

# --- Withdraw System ---
@bot.message_handler(func=lambda m: m.text == "💸 Withdraw")
def withdraw_init(message):
    user = db.get_user(message.chat.id)
    if user['balance'] < config.MIN_WITHDRAW:
        return bot.send_message(message.chat.id, f"❌ Your balance is less than ₹{config.MIN_WITHDRAW}!")
    
    msg = bot.send_message(message.chat.id, "Enter your Payment Address (UPI/USDT):", reply_markup=cancel_menu())
    bot.register_next_step_handler(msg, process_withdraw_address)

def process_withdraw_address(message):
    if message.text == "❌ Cancel": return cancel_action(message)
    db.set_wallet(message.chat.id, message.text)
    msg = bot.send_message(message.chat.id, "Enter the amount you want to Withdraw:", reply_markup=cancel_menu())
    bot.register_next_step_handler(msg, process_withdraw_amount)

def process_withdraw_amount(message):
    if message.text == "❌ Cancel": return cancel_action(message)
    try:
        amount = int(message.text)
        user = db.get_user(message.chat.id)
        if amount > user['balance'] or amount < config.MIN_WITHDRAW: raise ValueError
        
        # Deduct balance & Send request
        db.update_balance(message.chat.id, -amount)
        fee = amount * config.WITHDRAW_FEE
        net_amount = amount - fee
        
        bot.send_message(message.chat.id, f"✅ Your Withdraw request has been submitted successfully!\nFee: ₹{fee}\nNet Receive: ₹{net_amount}", reply_markup=main_menu())
        
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ Paid", callback_data=f"wit_app_{message.chat.id}"),
            InlineKeyboardButton("❌ Reject/Refund", callback_data=f"wit_rej_{message.chat.id}_{amount}")
        )
        bot.send_message(config.LOG_GROUP_ID, f"💸 **Withdraw Request**\nUser: `{message.chat.id}`\nWallet: `{user['wallet']}`\nRequest: ₹{amount}\nTo Pay: ₹{net_amount}", parse_mode="Markdown", reply_markup=markup)
    except:
        bot.send_message(message.chat.id, "❌ Please enter a valid amount or check your balance!", reply_markup=main_menu())

# --- Products ---
@bot.message_handler(func=lambda m: m.text == "🛍 Products")
def products_menu(message):
    markup = InlineKeyboardMarkup(row_width=1)
    for prod, price in config.PRODUCTS.items():
        markup.add(InlineKeyboardButton(f"🛒 {prod} Key - ₹{price}", callback_data=f"buy_{prod}_{price}"))
    bot.send_message(message.chat.id, "🛍 Select your preferred package from below:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def buy_product(call):
    data = call.data.split("_")
    prod, price = data[1], int(data[2])
    user_id = call.message.chat.id
    user = db.get_user(user_id)
    
    if user['balance'] < price:
        return bot.answer_callback_query(call.id, "❌ Insufficient Balance!", show_alert=True)
    
    key = db.get_and_use_key(prod)
    if not key:
        return bot.answer_callback_query(call.id, "❌ Out of Stock! Please contact the Admin.", show_alert=True)
    
    db.update_balance(user_id, -price)
    bot.edit_message_text(f"✅ **Purchase Successful!**\n\nProduct: {prod}\nYour Key:\n`{key}`", user_id, call.message.message_id, parse_mode="Markdown")

# --- Admin Handlers (Inline Buttons from Log Group) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("dep_"))
def admin_deposit_action(call):
    data = call.data.split("_")
    action, user_id = data[1], int(data[2])
    
    if action == "app":
        amount = int(data[3])
        db.update_balance(user_id, amount, recharge=True)
        bot.edit_message_text(call.message.text + "\n\n✅ **Status: APPROVED**", call.message.chat.id, call.message.message_id)
        bot.send_message(user_id, f"🎉 Your deposit of ₹{amount} has been successfully approved!")
        
        # Simple Refer Bonus (Level 1 - 25%)
        user = db.get_user(user_id)
        if user['referred_by']:
            bonus = amount * 0.25
            db.add_refer_income(user['referred_by'], bonus)
            bot.send_message(user['referred_by'], f"🎁 A user joined using your link and recharged ₹{amount}. You received a commission of ₹{bonus}!")
            
    elif action == "rej":
        bot.edit_message_text(call.message.text + "\n\n❌ **Status: REJECTED**", call.message.chat.id, call.message.message_id)
        bot.send_message(user_id, "❌ Your deposit request has been rejected.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("wit_"))
def admin_withdraw_action(call):
    data = call.data.split("_")
    action, user_id = data[1], int(data[2])
    
    if action == "app":
        bot.edit_message_text(call.message.text + "\n\n✅ **Status: PAID**", call.message.chat.id, call.message.message_id)
        bot.send_message(user_id, "✅ Your withdraw request has been successfully paid!")
    elif action == "rej":
        amount = int(data[3])
        db.update_balance(user_id, amount) # Refund
        bot.edit_message_text(call.message.text + "\n\n❌ **Status: REJECTED (Refunded)**", call.message.chat.id, call.message.message_id)
        bot.send_message(user_id, f"❌ Your withdraw request has been rejected and ₹{amount} has been refunded to your balance.")

# --- Admin Commands ---
@bot.message_handler(commands=['addkey'])
def add_key_cmd(message):
    if message.chat.id != config.ADMIN_ID: return
    try:
        _, prod, key = message.text.split(maxsplit=2)
        if prod not in config.PRODUCTS:
            return bot.reply_to(message, f"Valid products: {', '.join(config.PRODUCTS.keys())}")
        db.add_key(prod, key)
        bot.reply_to(message, f"✅ {prod} Key Added Successfully!")
    except:
        bot.reply_to(message, "Usage: /addkey <Product> <Key>")

@bot.message_handler(commands=['keystock'])
def stock_cmd(message):
    if message.chat.id != config.ADMIN_ID: return
    stock = db.get_key_stock()
    text = "📦 **Key Stock:**\n"
    for p, count in stock.items(): text += f"{p}: {count}\n"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['addbalance'])
def add_bal_cmd(message):
    if message.chat.id != config.ADMIN_ID: return
    try:
        _, user_id, amt = message.text.split()
        db.update_balance(int(user_id), float(amt))
        bot.reply_to(message, f"✅ Balance Added to {user_id}")
        bot.send_message(int(user_id), f"💰 Admin added ₹{amt} to your balance.")
    except:
        bot.reply_to(message, "Usage: /addbalance <user_id> <amount>")

# Run Bot
if __name__ == "__main__":
    print("🚀 Bot is running...")
    bot.infinity_polling()
