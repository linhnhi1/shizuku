import os
import random
import asyncio
import re
import subprocess
import json
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import ChatPermissions, ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton

# -------------------------------
# Import SQLAlchemy và thiết lập ORM
# -------------------------------
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# -------------------------------
# THÔNG TIN API – thay đổi theo thông tin của bạn
# -------------------------------
API_ID = 22286680
API_HASH = "a614a27fc39c3e54bf2e15da2a971e78"
BOT_TOKEN = "7573169920:AAFLHoWTkCQJLTyCqn9fpwMk_3iXm2FHiAc"

# Danh sách các owner (không chứa giá trị trùng lặp)
OWNER_IDS = [5867402532, 6370114941, 6922955912, 5161512205, 1906855234, 6247748448, 1829150726, 7021845241]

# -------------------------------
# CÀI ĐẶT DATABASE VỚI SQLALCHEMY
# -------------------------------
DATABASE_URL = "sqlite:///data.db"  # File database mới (tự tạo nếu chưa tồn tại)
engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    chat_id = Column(String, primary_key=True)
    user_id = Column(String, primary_key=True)
    first_name = Column(String)
    last_name = Column(String)
    username = Column(String)
    joined = Column(Integer)

    def __repr__(self):
        return f"<User(user_id={self.user_id}, first_name={self.first_name})>"

Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

def save_user_orm(chat_id, user, joined):
    """Lưu hoặc cập nhật thông tin người dùng vào DB."""
    db = SessionLocal()
    existing = db.query(User).filter_by(chat_id=str(chat_id), user_id=str(user.id)).first()
    if existing:
        existing.first_name = user.first_name
        existing.last_name = user.last_name
        existing.username = user.username
        existing.joined = int(joined)
    else:
        new_user = User(
            chat_id=str(chat_id),
            user_id=str(user.id),
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username,
            joined=int(joined)
        )
        db.add(new_user)
    db.commit()
    db.close()

def convert_time_to_seconds(time_str):
    """Chuyển đổi chuỗi thời gian (10s, 5m, 2h, 1d, 1w) thành số giây."""
    time_units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    match = re.match(r"(\d+)([smhdw])", time_str)
    if match:
        value, unit = match.groups()
        return int(value) * time_units[unit]
    return None

# -------------------------------
# DANH SÁCH THÔNG ĐIỆP & CÁC ROLE
# -------------------------------
admin_protection_messages = [
    "Sếp ơi, nó là admin đó bình tĩnh🐶.",
    "Này này, admin này còn giá trị lợi dụng đấy sếp🌚.",
    "Hãy vào cài đặt sa thải admin rồi ban hoặc mute nhé!",
    "Ôi, admin này làm sếp không vui, để em xử lý cho! 🐮"
]

funny_messages = [
    "🚀 {name} bay màu !",
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
    "chào mừng bạn! 😊", "xin chào, vui vẻ nhé! 😄", "chào, mừng gia nhập! 🌟", "hello, chào bạn! 😍"
]

# -------------------------------
# KHỞI TẠO LOCK CHO LỆNH /ytb
# -------------------------------
ytb_lock = asyncio.Lock()

# -------------------------------
# KHỞI TẠO CLIENT BOT
# -------------------------------
app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# -------------------------------
# Decorator: dành cho các lệnh quản trị (owner-only)
# -------------------------------
def owner_only(func):
    async def wrapper(client, message):
        if message.from_user.id not in OWNER_IDS:
            await message.reply(random.choice(missing_target_messages))
            return
        return await func(client, message)
    return wrapper

# -------------------------------
# Lệnh /dongbo: Đồng bộ toàn bộ thành viên trong nhóm (chỉ ID 5867402532 được dùng)
# -------------------------------
@app.on_message(filters.command("dongbo") & filters.group)
async def dongbo_handler(client, message):
    if message.from_user.id != 5867402532:
        await message.reply("Bạn không có quyền sử dụng lệnh này.")
        return
    chat_id = message.chat.id
    count = 0
    async for member in client.iter_chat_members(chat_id):
        save_user_orm(chat_id, member.user, message.date)
        count += 1
    await message.reply(f"Đã đồng bộ {count} thành viên từ nhóm.")

# -------------------------------
# Lệnh /list: Hiển thị danh sách lệnh của bot (mọi người đều có thể dùng)
# -------------------------------
@app.on_message(filters.command("list") & (filters.group | filters.private))
async def list_handler(client, message):
    commands = (
        "Tau không muốn chào đâu nhưng dev bắt tau chào đấy🐶\n"
        "Danh sách lệnh bên dưới:\n\n"
        "/batdau - Chào mừng người dùng\n"
        "/report - Báo cáo tin nhắn cần report (reply tin cần báo cáo)\n"
        "/xinfo hoặc /kiemtra - Kiểm tra thông tin người dùng tại nhóm (trạng thái thật)\n"
        "/dongbo - Đồng bộ toàn bộ thành viên (chỉ ID 5867402532 dùng)\n"
        "/xban hoặc /block - Ban người dùng (owner dùng)\n"
        "/xmute hoặc /xtuhinh - Mute người dùng (owner dùng)\n"
        "/xanxa - Unban người dùng (owner dùng)\n"
        "/xunmute - Unmute người dùng (owner dùng)\n"
        "/ytb - Tìm kiếm bài hát trên YouTube, hiển thị danh sách lựa chọn\n"
        "shizuku ơi ... - Gọi lệnh qua 'shizuku'\n"
        "/list - Hiển thị danh sách lệnh"
    )
    await message.reply_text(commands)

# -------------------------------
# Lệnh /batdau: Gửi lời chào ngẫu nhiên (mọi người đều có thể dùng)
# -------------------------------
@app.on_message(filters.command("batdau") & (filters.group | filters.private))
async def batdau_command(client, message):
    await message.reply(random.choice(welcome_messages))

# -------------------------------
# Lệnh /report: Báo cáo tin nhắn cần report (mọi người đều có thể dùng)
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
    group_report_message = (
        f"{reporter_fullname} đã gửi báo cáo đoạn chat của thành viên cho quản trị viên, "
        "đề nghị @OverFlowVIP kiểm tra và xử lý."
    )
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
        f"👤 Người bị báo cáo: {reported_fullname} (ID: {reported_user.id}, Username: "
        f"{'@' + reported_user.username if reported_user.username else 'Không có'})\n"
        f"💬 Nội dung: {reported_msg.text if reported_msg.text else '[Không có nội dung]'}\n"
        f"🔗 Link: {message_link}"
    )
    for owner in OWNER_IDS:
        try:
            await client.send_message(owner, report_details)
        except Exception:
            pass

# -------------------------------
# Lệnh /xinfo hoặc /kiemtra: Kiểm tra thông tin người dùng tại nhóm (trạng thái thật)
# -------------------------------
@app.on_message(filters.command(["xinfo", "kiemtra"]) & (filters.group | filters.private))
async def xinfo_handler(client, message):
    if message.reply_to_message:
        target = message.reply_to_message.from_user
    else:
        args = message.text.split(maxsplit=1)
        if len(args) >= 2:
            try:
                target = await client.get_users(args[1])
            except Exception:
                await message.reply(f"❌ Không thể tìm thấy người dùng với thông tin {args[1]}")
                return
        else:
            target = message.from_user

    info = "🪪 Thông tin người dùng:\n"
    info += f"Họ: {target.last_name if target.last_name else 'Không có'}\n"
    info += f"Tên: {target.first_name}\n"
    info += f"ID: {target.id}\n"
    info += f"Username: {'@' + target.username if target.username else 'Không có'}\n"
    info += f"Hồ sơ: [Nhấn vào đây](tg://user?id={target.id})\n"

    if message.chat and message.chat.type != "private":
        try:
            member = await client.get_chat_member(message.chat.id, target.id)
            status = member.status  # creator, administrator, member, restricted, left, kicked
        except Exception:
            status = "Không xác định"
        info += f"Trạng thái trong nhóm: {status}\n"
    else:
        info += "Trạng thái trong nhóm: Không có thông tin nhóm\n"

    await message.reply(info)

# -------------------------------
# Lệnh /xban (alias /block): Ban người dùng (chỉ owner dùng)
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
    ban_message = (
        f"🚨 **Đã BLOCK người dùng!**\n"
        f"🆔 **ID:** {user.id}\n"
        f"👤 **Họ & Tên:** {user.first_name} {user.last_name if user.last_name else ''}\n"
        f"🔗 **Username:** {'@' + user.username if user.username else 'Không có'}\n"
        f"📌 **Hồ sơ:** [Nhấn vào đây](tg://user?id={user.id})\n"
        f"❌ **Lý do:** {reason}\n"
    )
    if duration_seconds:
        ban_message += f"⏳ **Thời gian BLOCK:** {maybe_time}"
    else:
        ban_message += "🚷 **BLOCK vĩnh viễn!**"
    await message.reply(ban_message)
    pm_message = (
        f"[Ban Report]\nChat: {message.chat.title if message.chat.title else message.chat.id}\n"
        f"User: {user.first_name} {user.last_name if user.last_name else ''} (ID: {user.id}, Username: "
        f"{'@' + user.username if user.username else 'Không có'})\n"
        f"Lý do: {reason}"
    )
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
# Lệnh /xmute (alias /xtuhinh): Mute người dùng (chỉ owner dùng)
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
    mute_permissions = ChatPermissions(
        can_send_messages=False,
        can_send_media_messages=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
        can_invite_users=False
    )
    try:
        await client.restrict_chat_member(chat_id, user.id, mute_permissions)
    except Exception as e:
        await message.reply(f"❌ Không thể MUTE người dùng! Lỗi: {e}")
        return
    mute_message = (
        f"🔇 **Đã MUTE người dùng!**\n"
        f"🆔 **ID:** {user.id}\n"
        f"👤 **Họ & Tên:** {user.first_name} {user.last_name if user.last_name else ''}\n"
        f"🔗 **Username:** {'@' + user.username if user.username else 'Không có'}\n"
        f"📌 **Hồ sơ:** [Nhấn vào đây](tg://user?id={user.id})\n"
        f"❌ **Lý do:** {reason}\n"
    )
    if duration_seconds:
        mute_message += f"⏳ **Thời gian MUTE:** {maybe_time}"
    else:
        mute_message += "🔕 **MUTE vĩnh viễn!**"
    await message.reply(mute_message)
    pm_message = (
        f"[Mute Report]\nChat: {message.chat.title if message.chat.title else message.chat.id}\n"
        f"User: {user.first_name} {user.last_name if user.last_name else ''} (ID: {user.id}, Username: "
        f"{'@' + user.username if user.username else 'Không có'})\n"
        f"Lý do: {reason}"
    )
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
# Lệnh /xanxa: Unban người dùng (chỉ owner dùng)
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
# Lệnh /xunmute: Unmute người dùng (chỉ owner dùng)
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
        await message.reply(f"🎤 **{user.first_name} đã được XUNmute và được cấp lại đầy đủ quyền!**\n" +
                            random.choice(funny_messages).format(name=user.first_name))
    except Exception as e:
        await message.reply(f"❌ Không thể mở mute! Lỗi: {e}")

# -------------------------------
# Lệnh “shizuku”: Cho phép owner gọi lệnh qua cụm “shizuku ơi” hoặc “shizuku,”.
# Chuyển đổi lệnh tương ứng (ban, mute, unban, unmute) và xử lý; nếu gửi “shizuku, bạn được ai tạo ra?” trả lời mặc định.
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
                            "shizuku ơi unmute/ummute <ID/username>\n"
                            "shizuku, bạn được ai tạo ra?")
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
    elif "được ai tạo ra" in command_text.lower():
        await message.reply("Tôi được @OverFlowVIP và (Chat GPT plus) tạo ra🐶")
    else:
        await message.reply("Lệnh không hợp lệ. Bạn có thể dùng: ban/block, mute, unban, unmute, hoặc 'shizuku, bạn được ai tạo ra'.")

# -------------------------------
# Lệnh /ytb: Tìm kiếm bài hát trên YouTube, liệt kê danh sách chi tiết dưới dạng button
# Mọi người đều có thể sử dụng.
# -------------------------------
@app.on_message(filters.command("ytb") & filters.group)
async def ytb_handler(client, message):
    if len(message.text.split(maxsplit=1)) < 2:
        await message.reply("Vui lòng nhập tên bài hát sau lệnh /ytb.")
        return
    query = message.text.split(maxsplit=1)[1]
    temp_msg = await message.reply("Đang tìm kiếm bài hát trên YouTube...")
    
    # Sử dụng yt-dlp để tìm kiếm 5 kết quả dưới dạng JSON (sử dụng subprocess bất đồng bộ)
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp", "-j", f"ytsearch5:{query}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        await temp_msg.edit_text(f"Không thể tìm kiếm bài hát. Lỗi: {stderr.decode().strip()}")
        return
    result = stdout.decode()
    
    results = []
    for line in result.strip().split("\n"):
        try:
            obj = json.loads(line)
            results.append(obj)
        except Exception:
            continue

    if not results:
        await temp_msg.edit_text("Không tìm thấy bài hát nào.")
        return

    buttons = []
    for obj in results:
        video_id = obj.get("id")
        title = obj.get("title", "Không xác định")
        duration = obj.get("duration", 0)
        minutes = duration // 60
        seconds = duration % 60
        btn_text = f"{title} ({minutes}:{seconds:02d})"
        sanitized_title = "".join(c for c in title if c.isalnum() or c in (" ", "_")).rstrip().replace(" ", "_")
        # Callback data format: ytb|video_id|sanitized_title
        callback_data = f"ytb|{video_id}|{sanitized_title}"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])
    reply_markup = InlineKeyboardMarkup(buttons)
    await temp_msg.edit_text("Chọn bài hát:", reply_markup=reply_markup)

# -------------------------------
# Callback Query Handler cho lệnh /ytb
# -------------------------------
@app.on_callback_query(filters.regex(r"^ytb\|"))
async def ytb_callback_handler(client, callback_query):
    data = callback_query.data  # format: ytb|video_id|sanitized_title
    parts = data.split("|", 2)
    if len(parts) < 3:
        await callback_query.answer("Dữ liệu không hợp lệ.", show_alert=True)
        return
    video_id = parts[1]
    sanitized_title = parts[2]
    await callback_query.answer("Đang tải bài hát, vui lòng chờ...", show_alert=True)
    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--output", f"{sanitized_title}.%(ext)s",
        f"https://www.youtube.com/watch?v={video_id}"
    ]
    try:
        subprocess.run(cmd, check=True)
    except Exception as e:
        await callback_query.edit_message_text(f"Không thể tải bài hát. Lỗi: {e}")
        return
    mp3_filename = f"{sanitized_title}.mp3"
    if not os.path.exists(mp3_filename):
        possible_files = [f for f in os.listdir() if f.startswith(sanitized_title) and f.endswith(".mp3")]
        if possible_files:
            mp3_filename = possible_files[0]
        else:
            await callback_query.edit_message_text("Không tìm thấy file MP3 sau khi tải.")
            return
    try:
        await client.send_audio(callback_query.message.chat.id, audio=mp3_filename, caption=f"Bài hát: {sanitized_title}")
        await callback_query.edit_message_text("Bài hát đã được gửi!")
    except Exception as e:
        await callback_query.edit_message_text(f"Không thể gửi bài hát. Lỗi: {e}")
    finally:
        if os.path.exists(mp3_filename):
            os.remove(mp3_filename)

# -------------------------------
# Sự kiện: Khi thành viên rời nhóm, lấy thông tin từ DB và gửi lời tạm biệt.
# -------------------------------
@app.on_chat_member_updated()
async def member_left_handler(client, event: ChatMemberUpdated):
    if event.old_chat_member and event.new_chat_member:
        if event.old_chat_member.status not in ["left", "kicked"] and event.new_chat_member.status in ["left", "kicked"]:
            chat_id = event.chat.id
            user = event.old_chat_member.user
            db = SessionLocal()
            user_record = db.query(User).filter_by(chat_id=str(chat_id), user_id=str(user.id)).first()
            db.close()
            if user_record:
                try:
                    join_time = datetime.fromtimestamp(user_record.joined).strftime("%d/%m/%Y %H:%M:%S")
                except Exception:
                    join_time = "Không xác định"
                farewell_message = (
                    f"👋 **{user.first_name} {user.last_name or ''}** vừa rời khỏi nhóm.\n"
                    f"🆔 ID: {user.id}\n"
                    f"🔗 Username: {'@' + user.username if user.username else 'Không có'}\n"
                    f"📅 Tham gia từ: {join_time}"
                )
            else:
                farewell_message = (
                    f"👋 **{user.first_name} {user.last_name or ''}** vừa rời khỏi nhóm.\n"
                    f"🆔 ID: {user.id}\n"
                    f"🔗 Username: {'@' + user.username if user.username else 'Không có'}"
                )
            await client.send_message(chat_id, farewell_message)

# -------------------------------
# CHẠY BOT
# -------------------------------
if __name__ == "__main__":
    app.run()