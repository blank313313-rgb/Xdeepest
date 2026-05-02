# bot.py - البوت الرئيسي (نسخة Webhook لـ Hugging Face Spaces)

import logging
import os
import asyncio
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, CallbackQueryHandler, filters, ContextTypes
)
import config
import database
import file_parser

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

WAITING_SEARCH, WAITING_ADD, WAITING_PHONE_SEARCH = range(3)

MAIN_KEYBOARD = ReplyKeyboardMarkup([
    ['🔍 بحث بالاسم', '📱 بحث بالرقم'],
    ['📤 رفع ملف', '➕ إضافة شخص'],
    ['📊 إحصائيات', '❓ مساعدة']
], resize_keyboard=True)


def is_admin(user_id):
    return user_id == config.ADMIN_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ غير مصرح لك باستخدام هذا البوت.")
        return ConversationHandler.END

    await update.message.reply_text(
        "🔒 *أهلاً بك في بوت إدارة بيانات الشركة*\n\n"
        "✅ فرز ودمج ذكي للبيانات\n"
        "✅ كشف المكررين تلقائياً\n"
        "✅ بحث بالاسم أو الرقم\n\n"
        "اختر من القائمة:",
        reply_markup=MAIN_KEYBOARD,
        parse_mode='Markdown'
    )
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    await update.message.reply_text(
        "📋 *دليل الاستخدام*\n\n"
        "🔍 *بحث بالاسم* — ابحث بالاسم (ثنائي أو ثلاثي)\n"
        "📱 *بحث بالرقم* — ابحث برقم الهاتف\n"
        "📤 *رفع ملف* — ارفع ملفات متعددة\n"
        "➕ *إضافة شخص* — أضف يدوياً\n"
        "📊 *إحصائيات* — عدد السجلات\n\n"
        "🧠 *الفرز الذكي:*\n"
        "• يدمج السجلات المكملة تلقائياً\n"
        "• يحذف المكررين\n"
        "• لو نتائج متعددة → تختار منها\n\n"
        "📌 *الصيغ المدعومة:*\n"
        "CSV, XLS, XLSX, XLSB, TXT, ZIP, RAR, 7Z",
        parse_mode='Markdown'
    )


async def search_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    await update.message.reply_text(
        "🔍 أرسل الاسم (ثنائي أو ثلاثي أو جزء منه):",
        reply_markup=ReplyKeyboardRemove()
    )
    return WAITING_SEARCH


async def do_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    results = database.search_person(query)

    if not results:
        await update.message.reply_text(
            "❌ لم يتم العثور على نتائج.",
            reply_markup=MAIN_KEYBOARD
        )
        return ConversationHandler.END

    if len(results) == 1:
        await show_person_details(update, results[0])
        return ConversationHandler.END

    buttons = []
    for row in results[:20]:
        pid, name, phone, address, birth, age, fb, insta, ptype, family, notes = row
        type_emoji = {"employee": "👨‍💼", "client": "🤝"}.get(ptype, "❓")
        label = f"{type_emoji} {name}"
        if phone:
            label += f" | {phone}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"view_{pid}")])

    await update.message.reply_text(
        f"🔍 *تم العثور على {len(results)} نتائج:*\n\nاضغط لعرض التفاصيل:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode='Markdown'
    )
    return ConversationHandler.END


async def show_person_details(update_or_query, row):
    pid, name, phone, address, birth, age, fb, insta, ptype, family, notes = row

    type_name = {"employee": "موظف 👨‍💼", "client": "عميل 🤝"}.get(ptype, "غير مصنف ❓")

    response = f"👤 *{name}*\n"
    response += f"🏷 التصنيف: {type_name}\n"
    response += "━━━━━━━━━━━━━━━━━━\n"

    if phone:
        response += f"📱 الهاتف: `{phone}`\n"
    if address:
        response += f"🏠 السكن: {address}\n"
    if birth:
        response += f"📅 المواليد: {birth}\n"
    if age:
        response += f"🎂 العمر: {age}\n"
    if fb:
        response += f"📘 فيسبوك: {fb}\n"
    if insta:
        response += f"📸 انستقرام: {insta}\n"
    if family:
        response += f"👨‍👩‍👧‍👦 العائلة: {family}\n"
    if notes:
        response += f"📝 ملاحظات: {notes}\n"

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 حذف هذا الشخص", callback_data=f"del_{pid}")]
    ])

    if hasattr(update_or_query, 'message'):
        await update_or_query.message.reply_text(
            response, reply_markup=MAIN_KEYBOARD, parse_mode='Markdown'
        )
    else:
        await update_or_query.edit_message_text(
            response, parse_mode='Markdown', reply_markup=buttons
        )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("view_"):
        pid = int(data.split("_")[1])
        person = database.get_person_by_id(pid)
        if person:
            await show_person_details(query, person)
        else:
            await query.edit_message_text("❌ لم يتم العثور على الشخص.")

    elif data.startswith("del_"):
        pid = int(data.split("_")[1])
        database.delete_person(pid)
        await query.edit_message_text("✅ تم حذف الشخص.")


async def phone_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    await update.message.reply_text(
        "📱 أرسل رقم الهاتف (أو جزء منه):",
        reply_markup=ReplyKeyboardRemove()
    )
    return WAITING_PHONE_SEARCH


async def do_phone_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    results = database.search_by_phone(query)

    if not results:
        await update.message.reply_text(
            "❌ لم يتم العثور على نتائج.",
            reply_markup=MAIN_KEYBOARD
        )
        return ConversationHandler.END

    if len(results) == 1:
        await show_person_details(update, results[0])
        return ConversationHandler.END

    buttons = []
    for row in results[:20]:
        pid, name, phone, address, birth, age, fb, insta, ptype, family, notes = row
        type_emoji = {"employee": "👨‍💼", "client": "🤝"}.get(ptype, "❓")
        label = f"{type_emoji} {name} | {phone}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"view_{pid}")])

    await update.message.reply_text(
        f"📱 *تم العثور على {len(results)} نتائج*\n\nاضغط لعرض التفاصيل:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode='Markdown'
    )
    return ConversationHandler.END


async def add_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    await update.message.reply_text(
        "➕ *إضافة شخص جديد*\n\n"
        "أرسل البيانات (سطر لكل حقل):\n\n"
        "```\n"
        "الاسم: محمد أحمد\n"
        "الهاتف: 966512345678\n"
        "السكن: الرياض\n"
        "المواليد: 1990-01-15\n"
        "العمر: 36\n"
        "فيسبوك: facebook.com/mohammed\n"
        "انستقرام: @mohammed\n"
        "النوع: موظف\n"
        "العائلة: متزوج + ولدين\n"
        "ملاحظات: أي معلومات\n"
        "```\n\n"
        "💡 الاسم فقط إجباري\n"
        "أرسل /cancel للإلغاء",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove()
    )
    return WAITING_ADD


async def do_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    data = {}

    for line in text.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()

            if key in ('الاسم', 'اسم'):
                data['full_name'] = value
            elif key in ('الهاتف', 'رقم', 'جوال'):
                data['phone'] = value
            elif key in ('السكن', 'العنوان', 'عنوان'):
                data['address'] = value
            elif key in ('المواليد', 'تاريخ الميلاد', 'ميلاد'):
                data['birth_date'] = value
            elif key in ('العمر', 'عمر'):
                data['age'] = value
            elif key in ('فيسبوك', 'facebook', 'fb'):
                data['facebook'] = value
            elif key in ('انستقرام', 'instagram', 'insta'):
                data['instagram'] = value
            elif key in ('النوع', 'نوع'):
                if 'موظف' in value:
                    data['person_type'] = 'employee'
                elif 'عميل' in value or 'زبون' in value:
                    data['person_type'] = 'client'
                else:
                    data['person_type'] = 'unknown'
            elif key in ('العائلة', 'عائلة', 'العائله'):
                data['family_details'] = value
            elif key in ('ملاحظات', 'ملاحظة', 'تفاصيل'):
                data['notes'] = value

    if not data.get('full_name'):
        await update.message.reply_text(
            "❌ لازم تحط الاسم!\n\nأعد الإرسال أو /cancel للإلغاء"
        )
        return WAITING_ADD

    pid, was_merged = database.insert_person(data)

    if was_merged:
        await update.message.reply_text(
            f"🔄 تم *دمج* بيانات *{data['full_name']}* مع السجل الموجود",
            reply_markup=MAIN_KEYBOARD, parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"✅ تم إضافة *{data['full_name']}* بنجاح!",
            reply_markup=MAIN_KEYBOARD, parse_mode='Markdown'
        )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ تم الإلغاء.", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    stats = database.get_stats()

    await update.message.reply_text(
        f"📊 *إحصائيات قاعدة البيانات*\n\n"
        f"👥 إجمالي الأشخاص: *{stats['total']}*\n"
        f"👨‍💼 الموظفين: *{stats['employees']}*\n"
        f"🤝 العملاء: *{stats['clients']}*\n"
        f"❓ غير مصنف: *{stats['unknown']}*\n"
        f"📁 الملفات المرفوعة: *{stats['files']}*",
        parse_mode='Markdown'
    )


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    doc = update.message.document
    if not doc:
        await update.message.reply_text("❌ أرسل ملف بصيغة مدعومة.")
        return

    filename = doc.file_name
    ext = os.path.splitext(filename)[1].lower()

    supported = ['.csv', '.xls', '.xlsx', '.xlsb', '.txt', '.zip', '.rar', '.7z', '.mdb', '.accdb']
    if ext not in supported:
        await update.message.reply_text(
            f"❌ صيغة ({ext}) غير مدعومة.\n\nالمدعومة: {', '.join(supported)}"
        )
        return

    wait_msg = await update.message.reply_text(
        f"⏳ جاري تحليل `{filename}`...\n\n🧠 تشغيل الفرز الذكي...",
        parse_mode='Markdown'
    )

    try:
        file = await doc.get_file()
        download_path = os.path.join('uploads', filename)
        os.makedirs('uploads', exist_ok=True)
        await file.download_to_drive(download_path)

        persons = file_parser.parse_file(download_path)

        if not persons:
            await wait_msg.edit_text(
                f"⚠️ الملف `{filename}` لا يحتوي على بيانات صالحة.",
                parse_mode='Markdown'
            )
            return

        result = database.smart_import(persons)
        database.log_upload(filename, result['new'] + result['merged'])

        total_now = database.get_stats()['total']

        report = (
            f"✅ *تم بنجاح!*\n\n"
            f"📁 الملف: `{filename}`\n"
            f"📋 سجلات: {result['total_imported']}\n"
            f"🔄 بعد الدمج: {result['after_dedup']}\n"
            f"🗑 مكررات محذوفة: {result['duplicates_removed']}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"➕ جديدة: {result['new']}\n"
            f"🔀 مدمجة: {result['merged']}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 إجمالي القاعدة: *{total_now} شخص*"
        )

        await wait_msg.edit_text(report, parse_mode='Markdown')
        os.remove(download_path)

    except Exception as e:
        await wait_msg.edit_text(
            f"❌ خطأ: `{str(e)}`",
            parse_mode='Markdown'
        )


async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    text = update.message.text

    if text == '🔍 بحث بالاسم':
        await update.message.reply_text("🔍 أرسل الاسم:", reply_markup=ReplyKeyboardRemove())
        return WAITING_SEARCH
    elif text == '📱 بحث بالرقم':
        await update.message.reply_text("📱 أرسل الرقم:", reply_markup=ReplyKeyboardRemove())
        return WAITING_PHONE_SEARCH
    elif text == '➕ إضافة شخص':
        return await add_handler(update, context)
    elif text == '📊 إحصائيات':
        await stats_handler(update, context)
    elif text == '📤 رفع ملف':
        await update.message.reply_text(
            "📤 أرسل الملف هنا.\n\n"
            "الصيغ المدعومة:\nCSV, XLS, XLSX, XLSB, TXT, ZIP, RAR, 7Z, MDB, ACCDB\n\n"
            "🧠 الفرز الذكي يشتغل تلقائياً!"
        )
    elif text == '❓ مساعدة':
        await help_command(update, context)

    return ConversationHandler.END


# ========== Webhook Mode for HF Spaces ==========

from aiohttp import web

async def webhook_handler(request):
    """استقبال التحديثات من تليجرام عبر Webhook"""
    try:
        json_data = await request.json()
        update = Update.de_json(json_data, bot_app.bot)
        await bot_app.process_update(update)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
    return web.Response(status=200)


async def health_check(request):
    """فحص حالة البوت"""
    return web.Response(text="OK", status=200)


bot_app = None

def main():
    global bot_app

    database.init_db()
    os.makedirs('uploads', exist_ok=True)

    # إنشاء التطبيق
    bot_app = Application.builder().token(config.BOT_TOKEN).build()

    # إضافة المعالجات
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons),
        ],
        states={
            WAITING_SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, do_search),
            ],
            WAITING_PHONE_SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, do_phone_search),
            ],
            WAITING_ADD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, do_add),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    bot_app.add_handler(conv_handler)
    bot_app.add_handler(CallbackQueryHandler(button_callback))
    bot_app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    bot_app.add_handler(CommandHandler('help', help_command))
    bot_app.add_handler(CommandHandler('stats', stats_handler))

    # الحصول على رابط الـ Space
    space_url = os.environ.get("SPACE_HOST", "")
    hf_token = os.environ.get("HF_TOKEN", os.environ.get("HF_SPACE", ""))

    if space_url:
        # Webhook mode
        port = int(os.environ.get("PORT", 7860))
        webhook_url = f"https://{space_url}/webhook"

        async def setup_webhook(application):
            await application.bot.set_webhook(url=webhook_url)
            logger.info(f"✅ Webhook set: {webhook_url}")

        bot_app.post_init = setup_webhook

        # إنشاء خادم ويب
        web_app = web.Application()
        web_app.router.add_post("/webhook", webhook_handler)
        web_app.router.add_get("/health", health_check)
        web_app.router.add_get("/", health_check)

        async def run_both():
            await bot_app.initialize()
            await bot_app.start()
            runner = web.AppRunner(web_app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", port)
            await site.start()
            logger.info(f"🤖 البوت يعمل على المنفذ {port}")
            print(f"🤖 البوت يعمل (Webhook) على المنفذ {port}")

            # إبقاء العملية تعمل
            while True:
                await asyncio.sleep(3600)

        asyncio.run(run_both())
    else:
        # Polling mode (للتشغيل المحلي)
        logger.info("🤖 البوت يعمل (Polling)...")
        print("🤖 البوت يعمل (Polling)...")
        bot_app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
