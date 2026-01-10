import os
import logging
import asyncio
import io
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from mutagen.id3 import ID3, TIT2, APIC, error
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3
from supabase import create_client, Client

# --- SOZLAMALAR ---
BOT_TOKEN = "8390443392:AAGrr9hwOz0gw_m4CbrlCGwKA2gmlFcOBrs"
SUPABASE_URL = "https://trybbxovootehqvaiydn.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRyeWJieG92b290ZWhxdmFpeWRuIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NzY4OTUxNiwiZXhwIjoyMDgzMjY1NTE2fQ.UAkYDJeipnuBLJgLWcw0brs1wLYIl92smd1EBfrFRZg" 
ADMIN_ID = 7894854944

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# --- FSM HOLATLARI ---
class EditorStates(StatesGroup):
    waiting_for_mp3 = State()
    choosing_action = State()
    waiting_for_name = State()
    waiting_for_cover = State()

class AdminStates(StatesGroup):
    waiting_for_ad_content = State()

# --- DINAMIK TUGMALAR ---
def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Nomni tahrirlash", callback_data="edit_name"),
         InlineKeyboardButton(text="🖼 Muqova qo'shish", callback_data="edit_cover")],
        [InlineKeyboardButton(text="🚀 Tayyor, yuborish!", callback_data="send_final")],
        [InlineKeyboardButton(text="🗑 Bekor qilish", callback_data="cancel_edit")]
    ])

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga qaytish", callback_data="back_to_menu")]
    ])

# --- ADMIN FUNKSIYALARI ---
@dp.message(Command("stats"), F.from_user.id == ADMIN_ID)
async def get_stats(message: types.Message):
    try:
        res = supabase.table("mp3_logs").select("*").execute()
        total_edits = len(res.data)
        unique_users = len(set([row['user_id'] for row in res.data]))
        text = (
            "📊 <b>Bot Statistikasi</b>\n\n"
            f"👤 Foydalanuvchilar: <code>{unique_users} ta</code>\n"
            f"🎵 Tahrirlangan: <code>{total_edits} ta</code>"
        )
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")

@dp.message(Command("send"), F.from_user.id == ADMIN_ID)
async def start_mailing(message: types.Message, state: FSMContext):
    await message.answer("📢 <b>Reklama xabarini yuboring:</b>", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_ad_content)

@dp.message(AdminStates.waiting_for_ad_content, F.from_user.id == ADMIN_ID)
async def broadcast_message(message: types.Message, state: FSMContext):
    res = supabase.table("mp3_logs").select("user_id").execute()
    user_ids = list(set([row['user_id'] for row in res.data]))
    count = 0
    for uid in user_ids:
        try:
            await message.copy_to(chat_id=uid)
            count += 1
            await asyncio.sleep(0.05)
        except: continue
    await message.answer(f"✅ <b>Yuborildi:</b> <code>{count}</code> ta foydalanuvchiga.", parse_mode="HTML")
    await state.clear()

# --- ASOSIY BOT LOGIKASI ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("✨ <b>Xush kelibsiz!</b>\n\nMarhamat, boshlash uchun MP3 fayl yuboring:", parse_mode="HTML")
    await state.set_state(EditorStates.waiting_for_mp3)

@dp.message(F.audio)
async def handle_audio(message: types.Message, state: FSMContext):
    status = await message.answer("⏳ <b>Fayl yuklanmoqda...</b>", parse_mode="HTML")
    file_id = message.audio.file_id
    file_name = message.audio.file_name or "music.mp3"
    
    os.makedirs("downloads", exist_ok=True)
    file_path = os.path.abspath(f"downloads/{file_id}.mp3")
    
    file = await bot.get_file(file_id)
    await bot.download_file(file.file_path, file_path)
    
    await status.edit_text(
        f"🎧 <b>Musiqa tanlandi:</b>\n<code>{file_name}</code>",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )
    await state.update_data(current_file=file_path, original_name=file_name, main_msg_id=status.message_id)
    await state.set_state(EditorStates.choosing_action)

@dp.message(EditorStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    new_title = message.text
    data = await state.get_data()
    file_path = data.get('current_file')
    main_msg_id = data.get('main_msg_id')

    try:
        await message.delete()
        # "Can't sync to MPEG frame" xatosini chetlab o'tish uchun to'g'ridan-to'g'ri ID3 ishlatamiz
        try:
            tags = ID3(file_path)
        except error:
            tags = ID3()
            
        tags.add(TIT2(encoding=3, text=new_title))
        tags.save(file_path, v2_version=3)
        
        await state.update_data(new_title=new_title)
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=main_msg_id,
            text=f"✅ <b>Nom saqlandi:</b> <code>{new_title}</code>\n\nYana biror narsa o'zgartiramizmi?",
            reply_markup=main_menu_kb(),
            parse_mode="HTML"
        )
        await state.set_state(EditorStates.choosing_action)
    except Exception as e:
        logging.error(f"Xato: {e}")
        await message.answer(f"⚠️ Xatolik: {e}")

@dp.message(F.photo, EditorStates.waiting_for_cover)
async def process_cover(message: types.Message, state: FSMContext):
    data = await state.get_data()
    file_path = data.get('current_file')
    main_msg_id = data.get('main_msg_id')

    await message.delete()
    photo_file = await bot.get_file(message.photo[-1].file_id)
    dest = io.BytesIO()
    await bot.download_file(photo_file.file_path, dest)
    
    try:
        tags = ID3(file_path)
        tags.delall('APIC')
        tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=dest.getvalue()))
        tags.save(file_path, v2_version=3)
        
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=main_msg_id,
            text="✅ <b>Muqova yangilandi!</b>\n\nYana biror narsa o'zgartiramizmi?",
            reply_markup=main_menu_kb(),
            parse_mode="HTML"
        )
        await state.set_state(EditorStates.choosing_action)
    except Exception as e:
        await message.answer(f"⚠️ Rasmda xatolik: {e}")

@dp.callback_query(F.data == "send_final")
async def send_music(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    file_path = data.get('current_file')
    new_title = data.get('new_title', data.get('original_name', 'music.mp3'))
    
    await call.message.edit_text("🚀 <b>Tayyorlanmoqda...</b>", parse_mode="HTML")
    
    clean_name = "".join([c for c in new_title if c.isalnum() or c in (' ', '-', '_')]).strip() + ".mp3"
    final_path = os.path.join("downloads", clean_name)

    try:
        os.rename(file_path, final_path)
        await bot.send_audio(
            chat_id=call.message.chat.id,
            audio=FSInputFile(final_path),
            title=new_title,
            caption=f"🎵 <b>{new_title}</b>\n\n✅ @music_editormirshodbot",
            parse_mode="HTML"
        )
        await call.message.delete()
        supabase.table("mp3_logs").insert({"user_id": call.from_user.id, "action_type": "success"}).execute()
    except Exception as e:
        await call.message.answer(f"🚀 Xato: {e}")
    finally:
        if os.path.exists(final_path): os.remove(final_path)
        await state.clear()

# --- QOLGAN CALLBACKLAR ---
@dp.callback_query(F.data == "edit_name")
async def edit_name_call(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("📝 <b>Yangi nomni yuboring:</b>", reply_markup=back_kb(), parse_mode="HTML")
    await state.set_state(EditorStates.waiting_for_name)

@dp.callback_query(F.data == "edit_cover")
async def edit_cover_call(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("🖼 <b>Rasm yuboring:</b>", reply_markup=back_kb(), parse_mode="HTML")
    await state.set_state(EditorStates.waiting_for_cover)

@dp.callback_query(F.data == "back_to_menu")
async def back(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await call.message.edit_text(f"🎧 Musiqa: <code>{data.get('original_name')}</code>", reply_markup=main_menu_kb(), parse_mode="HTML")
    await state.set_state(EditorStates.choosing_action)

@dp.callback_query(F.data == "cancel_edit")
async def cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("🗑 Bekor qilindi. Yangi fayl yuborishingiz mumkin.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())