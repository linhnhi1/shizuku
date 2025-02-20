import os
import random
import asyncio
import re
import sqlite3
from pyrogram import Client, filters
from pyrogram.types import ChatPermissions

# -------------------------------
# THÔNG TIN API – thay đổi theo thông tin của bạn
# -------------------------------
API_ID = 22286680                # Thay bằng API ID của bạn
API_HASH = "a614a27fc39c3e54bf2e15da2a971e78"       # Thay bằng API Hash của bạn
BOT_TOKEN = "7573169920:AAFLHoWTkCQJLTyCqn9fpwMk_3iXm2FHiAc"     # Thay bằng Bot Token của bạn

# Danh sách các owner (các owner này được phép dùng lệnh quản trị)
OWNER_IDS = [5867402532, 6370114941]  # VD: [5867402532, 123456789, 987654321]

# -------------------------------
# KHỞI TẠO DATABASE SQLite
# -------------------------------
DB_FILE = "data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            chat_id TEXT,
            user_id TEXT,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            joined INTEGER,
            PRIMARY KEY (chat_id, user_id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def save_user(chat_id, user, joined):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (chat_id, user_id, first_name, last_name, username, joined)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (str(chat_id),
          str(user.id),
          user.first_name,
          user.last_name,
          user.username,
          int(joined)))
    conn.commit()
    conn.close()

# -------------------------------
# HÀM CHUYỂN ĐỔI THỜI GIAN (ví dụ: 10s, 5m, 2h, 1d, 1w) thành số giây
# -------------------------------
def convert_time_to_seconds(time_str):
    time_units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    match = re.match(r"(\d+)([smhdw])", time_str)
    if match:
        value, unit = match.groups()
        return int(value) * time_units[unit]
    return None

# -------------------------------
# DANH SÁCH THÔNG ĐIỆP
# -------------------------------
funny_messages = [
    "🚀 {name} bay màu luôn luôn!",
    "😆 {name} vừa du hành qua không gian ảo!",
    "🎉 {name} đã được phóng thích!",
    "😎 {name} giờ tự do để tán gẫu!",
    "🎊 {name} vừa được giải phóng khỏi chế độ cấm!",
    "🔥 {name} vừa thoát khỏi trại giam ảo!",
    "😂 {name} đã được bấm nút phục hồi quyền!",
    "🤩 {name} giờ đã trở lại đỉnh cao chat!",
    "🎈 {name} vừa được trả tự do!",
    "🥳 {name} đã bùng nổ trở lại!"
]

missing_target_messages = [
    "⚠️ Vui lòng cung cấp ID, username hoặc reply tin nhắn của thành viên cần xử lý!",
    "❌ Bạn chưa chỉ định đối tượng cần xử lý!",
    "🚨 Thiếu thông tin, hãy thử lại!",
    "⛔ Không rõ đối tượng để ban/mute!",
    "❓ Bạn định xử lý ai vậy?",
    "😕 Chưa thấy thông tin, vui lòng nhập lại!",
    "🧐 Bạn có quên reply hoặc nhập id không?",
    "📢 Không có thông tin, hãy thử lại!",
    "🔍 Không tìm thấy đối tượng!",
    "🚫 Vui lòng cung cấp ID, username hoặc reply cho người cần xử lý!"
]

admin_protection_messages = [
    "Sếp ơi, nó là admin đó bình tĩnh🐶.",
    "Này này, admin này còn giá trị lợi dụng đấy sếp🌚.",
    "Hãy vào cài đặt sa thải admin rồi ban hoặc mute nhé!",
    "Ôi, admin này làm sếp không vui, để em xử lý cho!🐮"
]

group_greeting_messages = [
    "hello cà nha, bot đã đến rồi! 😄",
    "xin chào nhóm, rất vui được gặp! 🤗",
    "chào mọi người, bot đã xuất hiện! 😎",
    "hello team, cùng vui nào! 🎉",
    "chào mừng, bot đến rồi! 🚀",
    "xin chào, mình đây! 🐱",
    "chào nhóm, sẵn sàng bất ngờ! 🌟",
    "hello, bot đã đến! 😁",
    "chào các bạn, thật hạnh phúc! 🎈",
    "xin chào, cùng vui nhé! 😄"
]

welcome_messages = [
    "chào mừng bạn! 😊", "xin chào, vui vẻ nhé! 😄", "chào, mừng gia nhập! 🌟", "hello, chào bạn! 😍",
    "mừng bạn, hãy cười nhé! 😊", "vui quá, bạn đến rồi! 😁", "chào, bạn xinh lắm! 🌸", "mừng gia nhập, cùng vui! 🤗",
    "chào, tươi cười nhé! 😄", "mừng bạn vào nhóm! 😊", "chào, bạn thật dễ thương! 😍", "mừng bạn, cùng cười! 😊",
    "xin chào, vui lắm! 😁", "chào, mừng bạn vào nhóm! 🌸", "mừng bạn, hãy cười nhé! 😊", "hello, bạn đáng yêu! 😄",
    "chào, mừng bạn vào nhóm! 😊", "vui quá, chào bạn! 😍", "mừng bạn, cười lên! 😊", "chào, hãy cùng vui! 🤗",
    "mừng bạn, mỉm cười! 😊", "chào, gia nhập tuyệt! 😄", "xin chào, bạn dễ thương! 😍", "mừng bạn, luôn vui! 😊",
    "chào, cười nhé! 😊", "hello, gia nhập vui! 😁", "chào, mỉm cười nào! 😍", "mừng bạn, thật vui! 😊",
    "chào, hãy cười lên! 😄", "mừng bạn, chào mừng! 😊", "xin chào, bạn thật xinh! 😁", "chào mừng, mỉm cười nhé! 😊",
    "chào, gia nhập cực vui! 😍", "xin chào, cười thật nhiều! 😊", "mừng bạn, thật tuyệt! 😄", "chào, vui cùng nhau! 😊",
    "mừng bạn, luôn mỉm cười! 😁", "xin chào, bạn là niềm vui! 😍", "chào mừng, cười thật tươi! 😊", "chào, gia nhập thật vui! 😄",
    "mừng bạn, hãy cười lên! 😊", "xin chào, bạn thật tuyệt! 😁", "chào mừng, vui khôn xiết! 😍", "chào, gia nhập rạng rỡ! 😊",
    "mừng bạn, cười thật nhiều! 😄", "xin chào, luôn tươi cười! 😊", "chào mừng, bạn là nụ cười! 😁", "chào, vui quá khi gặp! 😍",
    "mừng bạn, chúc bạn cười! 😊", "xin chào, bạn thật mát! 😄", "chào mừng, bạn là ánh sáng! 😊", "chào, cùng cười nào! 😁",
    "mừng bạn, thật hạnh phúc! 😍", "xin chào, bạn là niềm vui! 😊", "chào mừng, cười thật lên! 😄", "chào, bạn thật rạng rỡ! 😊",
    "mừng bạn, vui quá! 😁", "xin chào, luôn mỉm cười! 😍", "chào mừng, bạn làm vui! 😊", "chào, gia nhập hân hoan! 😄",
    "mừng bạn, cười thật tươi! 😊", "xin chào, bạn cực kỳ dễ thương! 😁", "chào mừng, hãy cười nào! 😍", "chào, gia nhập cùng vui! 😊",
    "mừng bạn, thật tuyệt vời! 😄", "xin chào, bạn làm sáng nhóm! 😊", "chào mừng, cùng cười tươi! 😁", "chào, vui khôn xiết! 😍",
    "mừng bạn, chúc bạn cười mãi! 😊", "xin chào, bạn thật đáng yêu! 😄", "chào mừng, bạn là niềm hạnh phúc! 😊",
    "chào, gia nhập tuyệt cú! 😁", "mừng bạn, cười thật nhiều! 😍", "xin chào, bạn là điều tuyệt! 😊", "chào mừng, cùng vui vẻ! 😄",
    "chào, bạn thật xinh xắn! 😊", "mừng bạn, luôn tươi cười! 😁", "xin chào, bạn làm nhóm thêm vui! 😍", "chào mừng, hãy cười thật tươi! 😊",
    "chào, gia nhập tràn ngập vui! 😄", "mừng bạn, cười cho tươi! 😁", "nice to see you, chào nhé! 😊"
]

# -------------------------------
# KHỞI TẠO CLIENT BOT
# -------------------------------
app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# -------------------------------
# Decorator: chỉ cho phép các owner sử dụng lệnh quản trị
# -------------------------------
def owner_only(func):
    async def wrapper(client, message):
        if message.from_user.id not in OWNER_IDS:
            await message.reply(random.choice(missing_target_messages))
            return
        return await func(client, message)
    return wrapper

# -------------------------------
# Lệnh /xinfo hoặc /kiemtra: Xem thông tin người dùng (Sổ Hộ Khẩu)
# -------------------------------
@app.on_message(filters.command(["xinfo", "kiemtra"]) & (filters.group | filters.private))
async def xinfo_handler(client, message):
    # Xác định đối tượng cần kiểm tra:
    if message.reply_to_message:
        target = message.reply_to_message.from_user
        chat_id = message.chat.id
    else:
        args = message.text.split(maxsplit=1)
        if len(args) >= 2:
            identifier = args[1]
            if identifier.isdigit():
                identifier = int(identifier)
            try:
                target = await client.get_users(identifier)
            except Exception:
                await message.reply(f"❌ Không thể tìm thấy người dùng với thông tin {args[1]}")
                return
            chat_id = message.chat.id if message.chat else None
        else:
            target = message.from_user
            chat_id = message.chat.id if message.chat else None

    info = "🪪 **Sổ Hộ Khẩu:**\n"
    info += f"**Họ:** {target.last_name if target.last_name else 'Không có'}\n"
    info += f"**Tên:** {target.first_name}\n"
    info += f"**ID:** `{target.id}`\n"
    info += f"**Username:** {'@' + target.username if target.username else 'Không có'}\n"
    info += f"**Hồ sơ:** [Nhấn vào đây](tg://user?id={target.id})\n"

    # Xác định trạng thái theo vai trò
    owner_statuses = ["Vua", "Trùm Cuối", "Hoàng Thượng", "Chủ Tịch", "Trùm Mafia", "Tổng Tư Lệnh", "Hiệu Trưởng"]
    admin_statuses = ["Cận Vệ", "Ăn Bám", "Lính Có Quyền Admin", "Quan Lớn", "Hộ Vệ", "Tay Sai"]
    member_statuses = ["Người Hầu", "Lính Lát", "Thực Tập Sinh", "Người Lạ", "Trẻ Sơ Sinh"]

    role = ""
    # Nếu có thông tin chat (group) thì kiểm tra quyền:
    if chat_id:
        try:
            member = await client.get_chat_member(chat_id, target.id)
            if target.id in OWNER_IDS:
                role = random.choice(owner_statuses)
            elif member.status in ["administrator", "creator"]:
                role = random.choice(admin_statuses)
            else:
                role = random.choice(member_statuses)
        except Exception:
            role = random.choice(member_statuses)
    else:
        if target.id in OWNER_IDS:
            role = random.choice(owner_statuses)
        else:
            role = random.choice(member_statuses)
    icons = ["🔥", "💥", "✨", "🎉", "😎", "🚀", "🌟", "🥳", "💎", "🔔"]
    info += f"**Trạng thái:** {role} {random.choice(icons)}"
    await message.reply(info)

# -------------------------------
# Lệnh /report: Báo cáo tin nhắn cần report.
# Mọi người có thể sử dụng.
# -------------------------------
@app.on_message(filters.command("report"))
async def report_handler(client, message):
    if not message.reply_to_message:
        await message.reply("Vui lòng trả lời lại tin nhắn cần báo cáo.")
        return

    reported_msg = message.reply_to_message
    reporter = message.from_user
    reported_user = reported_msg.from_user

    reporter_fullname = reporter.first_name + ((" " + reporter.last_name) if reporter.last_name else "")
    group_report_message = f"{reporter_fullname} đã gửi báo cáo đoạn chat của thành viên cho quản trị viên, đề nghị @OverFlowVIP kiểm tra và xử lý."
    await message.reply(group_report_message)

    if message.chat.username:
        message_link = f"https://t.me/{message.chat.username}/{reported_msg.message_id}"
    else:
        chat_id_str = str(message.chat.id)
        chat_link_id = chat_id_str.replace("-100", "") if chat_id_str.startswith("-100") else chat_id_str
        message_link = f"https://t.me/c/{chat_link_id}/{reported_msg.message_id}"

    reported_fullname = reported_user.first_name + ((" " + reported_user.last_name) if reported_user.last_name else "")
    report_details = (
        f"📝 Báo cáo từ: {reporter_fullname} (ID: {reporter.id})\n"
        f"👤 Người bị báo cáo: {reported_fullname} (ID: {reported_user.id}, Username: {'@'+reported_user.username if reported_user.username else 'Không có'})\n"
        f"💬 Nội dung: {reported_msg.text if reported_msg.text else '[Không có nội dung]'}\n"
        f"🔗 Link: {message_link}"
    )
    for owner in OWNER_IDS:
        try:
            await client.send_message(owner, report_details)
        except Exception:
            pass

# -------------------------------
# Lệnh /xban (alias /block): BLOCK (ban) theo ID/username hoặc reply.
# Xoá tin nhắn nếu dùng reply. PM báo cáo cho các owner.
# -------------------------------
@app.on_message(filters.command(["xban", "block"]) & filters.group)
@owner_only
async def xban_user(client, message):
    args = message.text.split(maxsplit=3)
    if message.reply_to_message:
        try:
            await message.reply_to_message.delete()
        except Exception:
            pass
        user = message.reply_to_message.from_user
        maybe_time = args[1] if len(args) >= 2 and args[1][-1] in "smhdw" else None
        reason = args[2] if (maybe_time and len(args) >= 3) else (args[1] if len(args) >= 2 and not maybe_time else "Không có lý do")
    else:
        if len(args) < 2:
            await message.reply(random.choice(missing_target_messages))
            return
        user_identifier = args[1]
        if user_identifier.isdigit():
            user_identifier = int(user_identifier)
        try:
            user = await client.get_users(user_identifier)
        except Exception:
            await message.reply(f"❌ Không thể tìm thấy người dùng với thông tin {args[1]}")
            return
        maybe_time = args[2] if len(args) >= 3 and args[2][-1] in "smhdw" else None
        reason = args[3] if (maybe_time and len(args) >= 4) else (args[2] if len(args) >= 3 and not maybe_time else "Không có lý do")
    
    chat_id = message.chat.id
    try:
        member = await client.get_chat_member(chat_id, user.id)
        if member.status in ["administrator", "creator"]:
            await message.reply(random.choice(admin_protection_messages))
            return
    except Exception:
        await message.reply(random.choice(admin_protection_messages))
        return

    duration_seconds = convert_time_to_seconds(maybe_time) if maybe_time else None
    try:
        await client.ban_chat_member(chat_id, user.id)
    except Exception as e:
        await message.reply(f"❌ Không thể BLOCK người dùng! Lỗi: {e}")
        return

    ban_message = f"🚨 **Đã BLOCK người dùng!**\n" \
                  f"🆔 **ID:** `{user.id}`\n" \
                  f"👤 **Họ & Tên:** {user.first_name} {user.last_name if user.last_name else ''}\n" \
                  f"🔗 **Username:** {'@'+user.username if user.username else 'Không có'}\n" \
                  f"📌 **Hồ sơ:** [Nhấn vào đây](tg://user?id={user.id})\n" \
                  f"❌ **Lý do:** {reason}\n"
    if duration_seconds:
        ban_message += f"⏳ **Thời gian BLOCK:** {maybe_time}"
    else:
        ban_message += "🚷 **BLOCK vĩnh viễn!**"
    await message.reply(ban_message)

    pm_message = (f"[Ban Report]\nChat: {message.chat.title if message.chat.title else message.chat.id}\n"
                  f"User: {user.first_name} {user.last_name if user.last_name else ''} (ID: {user.id}, Username: {'@'+user.username if user.username else 'Không có'})\n"
                  f"Lý do: {reason}")
    for owner in OWNER_IDS:
        try:
            await client.send_message(owner, pm_message)
        except Exception:
            pass

    if duration_seconds:
        await asyncio.sleep(duration_seconds)
        try:
            await client.unban_chat_member(chat_id, user.id)
            await message.reply(f"✅ **{user.first_name} đã được mở BLOCK sau {maybe_time}!**\n" +
                                random.choice(funny_messages).format(name=user.first_name))
        except Exception as e:
            await message.reply(f"❌ Không thể mở BLOCK! Lỗi: {e}")

# -------------------------------
# Lệnh /xmute (alias /xtuhinh): MUTE theo ID/username hoặc reply.
# Xoá tin nhắn nếu dùng reply. PM báo cáo cho các owner.
# -------------------------------
@app.on_message(filters.command(["xmute", "xtuhinh"]) & filters.group)
@owner_only
async def xmute_user(client, message):
    args = message.text.split(maxsplit=3)
    if message.reply_to_message:
        try:
            await message.reply_to_message.delete()
        except Exception:
            pass
        user = message.reply_to_message.from_user
        maybe_time = args[1] if len(args) >= 2 and args[1][-1] in "smhdw" else None
        reason = args[2] if (maybe_time and len(args) >= 3) else (args[1] if len(args) >= 2 and not maybe_time else "Không có lý do")
    else:
        if len(args) < 2:
            await message.reply(random.choice(missing_target_messages))
            return
        user_identifier = args[1]
        if user_identifier.isdigit():
            user_identifier = int(user_identifier)
        try:
            user = await client.get_users(user_identifier)
        except Exception:
            await message.reply(f"❌ Không thể tìm thấy người dùng với thông tin {args[1]}")
            return
        maybe_time = args[2] if len(args) >= 3 and args[2][-1] in "smhdw" else None
        reason = args[3] if (maybe_time and len(args) >= 4) else (args[2] if len(args) >= 3 and not maybe_time else "Không có lý do")
    
    chat_id = message.chat.id
    try:
        member = await client.get_chat_member(chat_id, user.id)
        if member.status in ["administrator", "creator"]:
            await message.reply(random.choice(admin_protection_messages))
            return
    except Exception:
        await message.reply(random.choice(admin_protection_messages))
        return

    duration_seconds = convert_time_to_seconds(maybe_time) if maybe_time else None
    try:
        await client.restrict_chat_member(chat_id, user.id, 
            ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_invite_users=True
            )
        )
    except Exception as e:
        await message.reply(f"❌ Không thể MUTE người dùng! Lỗi: {e}")
        return

    mute_message = f"🔇 **Đã MUTE người dùng!**\n" \
                   f"🆔 **ID:** `{user.id}`\n" \
                   f"👤 **Họ & Tên:** {user.first_name} {user.last_name if user.last_name else ''}\n" \
                   f"🔗 **Username:** {'@'+user.username if user.username else 'Không có'}\n" \
                   f"📌 **Hồ sơ:** [Nhấn vào đây](tg://user?id={user.id})\n" \
                   f"❌ **Lý do:** {reason}\n"
    if duration_seconds:
        mute_message += f"⏳ **Thời gian MUTE:** {maybe_time}"
    else:
        mute_message += "🔕 **MUTE vĩnh viễn!**"
    await message.reply(mute_message)

    pm_message = (f"[Mute Report]\nChat: {message.chat.title if message.chat.title else message.chat.id}\n"
                  f"User: {user.first_name} {user.last_name if user.last_name else ''} (ID: {user.id}, Username: {'@'+user.username if user.username else 'Không có'})\n"
                  f"Lý do: {reason}")
    for owner in OWNER_IDS:
        try:
            await client.send_message(owner, pm_message)
        except Exception:
            pass

    if duration_seconds:
        await asyncio.sleep(duration_seconds)
        full_permissions = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_invite_users=True
        )
        try:
            await client.restrict_chat_member(chat_id, user.id, full_permissions)
            await message.reply(f"✅ **{user.first_name} đã được mở MUTE sau {maybe_time}!**\n" +
                                random.choice(funny_messages).format(name=user.first_name))
        except Exception as e:
            await message.reply(f"❌ Không thể mở MUTE! Lỗi: {e}")

# -------------------------------
# Lệnh /xanxa: Gỡ ban (unban) theo ID/username hoặc reply.
# -------------------------------
@app.on_message(filters.command("xanxa") & filters.group)
@owner_only
async def xanxa_user(client, message):
    args = message.text.split(maxsplit=2)
    if message.reply_to_message:
        user = message.reply_to_message.from_user
    else:
        if len(args) < 2:
            await message.reply(random.choice(missing_target_messages))
            return
        user_identifier = args[1]
        if user_identifier.isdigit():
            user_identifier = int(user_identifier)
        try:
            user = await client.get_users(user_identifier)
        except Exception:
            await message.reply(f"❌ Không thể tìm thấy người dùng với thông tin {args[1]}")
            return
    chat_id = message.chat.id
    try:
        await client.unban_chat_member(chat_id, user.id)
        await message.reply(f"🕊️ **{user.first_name} đã được xóa án BLOCK!**\n" +
                            random.choice(funny_messages).format(name=user.first_name))
    except Exception as e:
        await message.reply(f"❌ Không thể xóa án ban! Lỗi: {e}")

# -------------------------------
# Lệnh /xunmute: Mở mute và cấp lại đầy đủ quyền theo ID/username hoặc reply.
# (Các quyền được cấp lại bao gồm: gửi tin nhắn, ảnh, video, nhãn dán/GIF, nhạc, tệp, tin nhắn thoại, tin nhắn video, gửi liên kết nhúng)
# -------------------------------
@app.on_message(filters.command("xunmute") & filters.group)
@owner_only
async def xunmute_user(client, message):
    args = message.text.split(maxsplit=2)
    if message.reply_to_message:
        user = message.reply_to_message.from_user
    else:
        if len(args) < 2:
            await message.reply(random.choice(missing_target_messages))
            return
        user_identifier = args[1]
        if user_identifier.isdigit():
            user_identifier = int(user_identifier)
        try:
            user = await client.get_users(user_identifier)
        except Exception:
            await message.reply(f"❌ Không thể tìm thấy người dùng với thông tin {args[1]}")
            return
    chat_id = message.chat.id
    full_permissions = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_invite_users=True
    )
    try:
        await client.restrict_chat_member(chat_id, user.id, full_permissions)
        await message.reply(f"🎤 **{user.first_name} đã được XUNMUTE và được cấp lại đầy đủ quyền!**\n" +
                            random.choice(funny_messages).format(name=user.first_name))
    except Exception as e:
        await message.reply(f"❌ Không thể mở mute! Lỗi: {e}")

# -------------------------------
# Lệnh “shizuku”: Cho phép owner gọi bot bằng cụm “shizuku ơi” hoặc “shizuku,”.
# Nếu không có lệnh phụ, bot liệt kê các lệnh có sẵn.
# Nếu có lệnh: ban, block, mute, unban, unmute (hoặc ummute) sau cụm gọi,
# bot chuyển đổi thành lệnh tương ứng và thực thi (bao gồm thời gian và lý do).
# -------------------------------
@app.on_message(filters.regex(r"(?i)^shizuku(,| ơi)"))
async def shizuku_handler(client, message):
    if message.from_user.id not in OWNER_IDS:
        await message.reply("Bạn không có quyền sử dụng lệnh này.")
        return
    text = message.text.strip()
    if text.lower().startswith("shizuku ơi"):
        trigger_len = len("shizuku ơi")
    elif text.lower().startswith("shizuku,"):
        trigger_len = len("shizuku,")
    else:
        trigger_len = len("shizuku")
    command_text = text[trigger_len:].strip()
    if not command_text:
        await message.reply("Bạn có thể dùng:\n"
                            "shizuku ơi ban/block <ID/username> [thời gian] [lý do]\n"
                            "shizuku ơi mute <ID/username> [thời gian] [lý do]\n"
                            "shizuku ơi unban <ID/username>\n"
                            "shizuku ơi unmute/ummute <ID/username>")
        return
    parts = command_text.split()
    cmd = parts[0].lower()
    if cmd in ["ban", "block"]:
        new_text = "/xban " + " ".join(parts[1:])
        message.text = new_text
        await xban_user(client, message)
    elif cmd == "mute":
        new_text = "/xmute " + " ".join(parts[1:])
        message.text = new_text
        await xmute_user(client, message)
    elif cmd == "unban":
        new_text = "/xanxa " + " ".join(parts[1:])
        message.text = new_text
        await xanxa_user(client, message)
    elif cmd in ["unmute", "ummute"]:
        new_text = "/xunmute " + " ".join(parts[1:])
        message.text = new_text
        await xunmute_user(client, message)
    else:
        await message.reply("Lệnh không hợp lệ. Bạn có thể dùng: ban/block, mute, unban, unmute.")

# -------------------------------
# Lệnh /kickbot: Kick bot ra khỏi nhóm (chỉ dùng qua tin nhắn riêng với bot)
# -------------------------------
@app.on_message(filters.command("kickbot") & filters.private)
@owner_only
async def kickbot_handler(client, message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Vui lòng cung cấp ID nhóm cần kick bot ra.")
        return
    group_id = args[1]
    try:
        await client.leave_chat(group_id)
        await message.reply(f"Đã kick bot ra khỏi nhóm {group_id}.")
    except Exception as e:
        await message.reply(f"Không thể kick bot ra khỏi nhóm {group_id}. Lỗi: {e}")

# -------------------------------
# Lệnh /xinfo hoặc /kiemtra: Xem thông tin người dùng (Sổ Hộ Khẩu)
# -------------------------------
@app.on_message(filters.command(["xinfo", "kiemtra"]) & (filters.group | filters.private))
async def xinfo_handler(client, message):
    if message.reply_to_message:
        target = message.reply_to_message.from_user
        chat_id = message.chat.id
    else:
        args = message.text.split(maxsplit=1)
        if len(args) >= 2:
            identifier = args[1]
            if identifier.isdigit():
                identifier = int(identifier)
            try:
                target = await client.get_users(identifier)
            except Exception:
                await message.reply(f"❌ Không thể tìm thấy người dùng với thông tin {args[1]}")
                return
            chat_id = message.chat.id if message.chat else None
        else:
            target = message.from_user
            chat_id = message.chat.id if message.chat else None

    info = "🪪 **Sổ Hộ Khẩu:**\n"
    info += f"**Họ:** {target.last_name if target.last_name else 'Không có'}\n"
    info += f"**Tên:** {target.first_name}\n"
    info += f"**ID:** `{target.id}`\n"
    info += f"**Username:** {'@' + target.username if target.username else 'Không có'}\n"
    info += f"**Hồ sơ:** [Nhấn vào đây](tg://user?id={target.id})\n"
    
    # Xác định trạng thái theo vai trò:
    owner_statuses = ["Vua", "Trùm Cuối", "Hoàng Thượng", "Chủ Tịch", "Trùm Mafia", "Tổng Tư Lệnh", "Hiệu Trưởng"]
    admin_statuses = ["Cận Vệ", "Ăn Bám", "Lính Có Quyền Admin", "Quan Lớn", "Hộ Vệ", "Tay Sai"]
    member_statuses = ["Người Hầu", "Lính Lát", "Thực Tập Sinh", "Người Lạ", "Trẻ Sơ Sinh"]
    role = ""
    if chat_id:
        try:
            member = await client.get_chat_member(chat_id, target.id)
            if target.id in OWNER_IDS:
                role = random.choice(owner_statuses)
            elif member.status in ["administrator", "creator"]:
                role = random.choice(admin_statuses)
            else:
                role = random.choice(member_statuses)
        except Exception:
            role = random.choice(member_statuses)
    else:
        if target.id in OWNER_IDS:
            role = random.choice(owner_statuses)
        else:
            role = random.choice(member_statuses)
    icons = ["🔥", "💥", "✨", "🎉", "😎", "🚀", "🌟", "🥳", "💎", "🔔"]
    info += f"**Trạng thái:** {role} {random.choice(icons)}"
    await message.reply(info)

# -------------------------------
# Chạy bot
# -------------------------------
app.run()
