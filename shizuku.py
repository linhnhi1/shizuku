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

# Danh sách các owner
OWNER_IDS = [
    5867402532, 6370114941, 6922955912, 5161512205,
    1906855234, 6247748448, 1829150726, 7021845241
]

# -------------------------------
# CÀI ĐẶT DATABASE VỚI SQLALCHEMY
# -------------------------------
DATABASE_URL = "sqlite:///data.db"  # File database mới (sẽ được tạo nếu chưa tồn tại)
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

# Model lưu lịch sử đổi tên/username
class NameChange(Base):
    __tablename__ = 'name_changes'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String)
    old_name = Column(String)
    new_name = Column(String)
    old_username = Column(String)
    new_username = Column(String)
    changed_at = Column(Integer)  # lưu timestamp

# Model lưu global ban
class GlobalBan(Base):
    __tablename__ = 'global_bans'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, unique=True)
    banned_at = Column(Integer)

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
    "chào mừng bạn! 😊", "xin chào, vui vẻ nhé! 😄",
    "chào, mừng gia nhập! 🌟", "hello, chào bạn! 😍"
]

GLOBAL_BANS_FILE = "global_bans.json"

def load_global_bans_sync():
    if not os.path.exists(GLOBAL_BANS_FILE):
        return []
    try:
        with open(GLOBAL_BANS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_global_bans_sync(bans):
    with open(GLOBAL_BANS_FILE, "w") as f:
        json.dump(bans, f, indent=4)

global_bans = load_global_bans_sync()

app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def owner_only(func):
    async def wrapper(client, message):
        if message.from_user.id not in OWNER_IDS:
            await message.reply(random.choice(missing_target_messages))
            return
        return await func(client, message)
    return wrapper

# -------------------------------
# Lệnh /dongbo: Đồng bộ thành viên (chỉ ID 5867402532 dùng)
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
# Lệnh /list: Hiển thị danh sách lệnh
# -------------------------------
@app.on_message(filters.command("list") & (filters.group | filters.private))
async def list_handler(client, message):
    commands = (
        "Tau không muốn chào đâu nhưng dev bắt tau chào đấy🐶\n"
        "Danh sách lệnh bên dưới:\n\n"
        "/batdau - Chào mừng người dùng\n"
        "/report - Báo cáo tin nhắn cần report (reply tin cần báo cáo)\n"
        "/xinfo hoặc /kiemtra - Kiểm tra thông tin người dùng tại nhóm (trạng thái thật)\n"
        "/dongbo - Đồng bộ thành viên (chỉ ID 5867402532 dùng)\n"
        "/xban hoặc /block - Ban người dùng (owner dùng)\n"
        "/xmute hoặc /xtuhinh - Mute người dùng (owner dùng)\n"
        "/xanxa - Unban người dùng (owner dùng)\n"
        "/xunmute - Unmute người dùng (owner dùng)\n"
        "/fban - Global ban (chỉ ID 5867402532 được dùng)\n"
        "/funban - Global unban (chỉ ID 5867402532 được dùng)\n"
        "shizuku ơi globan ban/unban <ID/username> - Gọi lệnh global ban/unban qua 'shizuku'\n"
        "/list - Hiển thị danh sách lệnh"
    )
    await message.reply_text(commands)

# -------------------------------
# Lệnh /batdau: Gửi lời chào ngẫu nhiên
# -------------------------------
@app.on_message(filters.command("batdau") & (filters.group | filters.private))
async def batdau_command(client, message):
    await message.reply(random.choice(welcome_messages))

# -------------------------------
# Lệnh /report: Báo cáo tin nhắn cần report
# -------------------------------
@app.on_message(filters.command("report"))
async def report_handler(client, message):
    if not message.reply_to_message:
        await message.reply("Vui lòng trả lời lại tin nhắn cần báo cáo.")
        return
    reported_msg = message.reply_to_message
    reporter = message.from_user
    reported_user = reported_msg.from_user
    reporter_fullname = reporter.first_name + (" " + reporter.last_name if reporter.last_name else "")
    group_report_message = (
        f"{reporter_fullname} đã gửi báo cáo đoạn chat của thành viên cho quản trị viên, đề nghị @OverFlowVIP kiểm tra và xử lý."
    )
    await message.reply(group_report_message)
    if message.chat.username:
        message_link = f"https://t.me/{message.chat.username}/{reported_msg.message_id}"
    else:
        chat_id_str = str(message.chat.id)
        chat_link_id = chat_id_str.replace("-100", "") if chat_id_str.startswith("-100") else chat_id_str
        message_link = f"https://t.me/c/{chat_link_id}/{reported_msg.message_id}"
    reported_fullname = reported_user.first_name + (" " + reported_user.last_name if reported_user.last_name else "")
    report_details = (
        f"📝 Báo cáo từ: {reporter_fullname} (ID: {reporter.id})\n"
        f"👤 Người bị báo cáo: {reported_fullname} (ID: {reported_user.id}, Username: {'@' + reported_user.username if reported_user.username else 'Không có'})\n"
        f"💬 Nội dung: {reported_msg.text if reported_msg.text else '[Không có nội dung]'}\n"
        f"🔗 Link: {message_link}"
    )
    for owner in OWNER_IDS:
        try:
            await client.send_message(owner, report_details)
        except Exception:
            pass

# -------------------------------
# Lệnh /xinfo hoặc /kiemtra: Kiểm tra thông tin người dùng (plain text)
# -------------------------------
@app.on_message(filters.command(["xinfo", "kiemtra"]) & (filters.group | filters.private))
async def xinfo_handler(client, message):
    try:
        if message.reply_to_message:
            target = message.reply_to_message.from_user
        else:
            args = message.text.split(maxsplit=1)
            if len(args) >= 2:
                query = args[1].strip()
                if query.startswith("@"):
                    query = query[1:]
                try:
                    query_int = int(query)
                    target = await client.get_users(query_int)
                except ValueError:
                    target = await client.get_users(query)
            else:
                target = message.from_user

        user_id = target.id
        first_name = target.first_name if target.first_name else "Không có"
        last_name = target.last_name if target.last_name else "Không có"
        username = target.username if target.username else "Không có"

        if message.chat and message.chat.type != "private":
            try:
                member = await client.get_chat_member(message.chat.id, user_id)
                if user_id in OWNER_IDS:
                    status = "Owner/Hoàng thượng"
                elif member.status in ["administrator", "creator"]:
                    status = "Admin/Tể tướng"
                else:
                    status = "member/thường dân"
            except Exception:
                status = "Không xác định"
        else:
            status = "Không có thông tin nhóm"

        info = (
            "Thông tin người dùng:\n"
            f"Họ: {last_name}\n"
            f"Tên: {first_name}\n"
            f"ID: {user_id}\n"
            f"Username: @{username}\n"
            f"Trạng thái: {status}"
        )
        await message.reply(info)
    except Exception as ex:
        await message.reply(f"❌ Đã xảy ra lỗi: {ex}")

# -------------------------------
# Lệnh /fban: Global ban (chỉ ID 5867402532 dùng) và lưu vào DB
# -------------------------------
@app.on_message(filters.command("fban") & filters.group)
async def fban_user(client, message):
    if message.from_user.id != 5867402532:
        await message.reply("Bạn không có quyền sử dụng lệnh này!")
        return
    if message.reply_to_message:
        target = message.reply_to_message.from_user
    else:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply("Vui lòng cung cấp User ID hoặc reply tin nhắn cần global ban.")
            return
        try:
            target = await client.get_users(int(parts[1]))
        except ValueError:
            await message.reply("User ID không hợp lệ.")
            return
    user_id = target.id
    if user_id in global_bans:
        await message.reply("Người dùng này đã nằm trong danh sách global ban.")
        return
    global_bans.append(user_id)
    save_global_bans_sync(global_bans)
    from sqlalchemy.exc import IntegrityError
    db = SessionLocal()
    try:
        exists = db.query(GlobalBan).filter_by(user_id=str(user_id)).first()
        if not exists:
            new_global_ban = GlobalBan(user_id=str(user_id), banned_at=int(datetime.now().timestamp()))
            db.add(new_global_ban)
            db.commit()
    except IntegrityError:
        db.rollback()
    finally:
        db.close()
    await message.reply(f"✅ Global ban đã được áp dụng cho user ID {user_id}. Đang ban ở các nhóm.")
    dialogs = [d.chat for d in await client.get_dialogs()]
    count = 0
    for chat in dialogs:
        if chat.type in ["group", "supergroup"]:
            try:
                await client.ban_chat_member(chat.id, user_id)
                count += 1
            except Exception:
                pass
    await message.reply(f"✅ Đã thực hiện global ban ở {count} nhóm.")

# -------------------------------
# Lệnh /funban: Global unban (chỉ ID 5867402532 dùng) và xóa khỏi DB
# -------------------------------
@app.on_message(filters.command("funban") & filters.group)
async def funban_user(client, message):
    if message.from_user.id != 5867402532:
        await message.reply("Bạn không có quyền sử dụng lệnh này!")
        return
    if message.reply_to_message:
        target = message.reply_to_message.from_user
    else:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply("Vui lòng cung cấp User ID hoặc reply tin nhắn cần gỡ global ban.")
            return
        try:
            target = await client.get_users(int(parts[1]))
        except ValueError:
            await message.reply("User ID không hợp lệ.")
            return
    user_id = target.id
    if user_id not in global_bans:
        await message.reply("Người dùng này không nằm trong danh sách global ban.")
        return
    global_bans.remove(user_id)
    save_global_bans_sync(global_bans)
    db = SessionLocal()
    record = db.query(GlobalBan).filter_by(user_id=str(user_id)).first()
    if record:
        db.delete(record)
        db.commit()
    db.close()
    await message.reply(f"✅ Global ban đã được gỡ cho user ID {user_id}. Đang unban ở các nhóm.")
    dialogs = [d.chat for d in await client.get_dialogs()]
    count = 0
    for chat in dialogs:
        if chat.type in ["group", "supergroup"]:
            try:
                await client.unban_chat_member(chat.id, user_id)
                count += 1
            except Exception:
                pass
    await message.reply(f"✅ Đã gỡ global ban ở {count} nhóm.")

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
        f"🚨 Đã BLOCK người dùng!\n"
        f"ID: {user.id}\n"
        f"Họ & Tên: {user.last_name if user.last_name else 'Không có'} {user.first_name if user.first_name else 'Không có'}\n"
        f"Username: {'@' + user.username if user.username else 'Không có'}\n"
        f"Hồ sơ: tg://user?id={user.id}\n"
        f"Lý do: {reason}\n"
    )
    if duration_seconds:
        ban_message += f"Thời gian BLOCK: {maybe_time}"
    else:
        ban_message += "BLOCK vĩnh viễn!"
    await message.reply(ban_message)
    pm_message = (
        f"[Ban Report]\n"
        f"Chat: {message.chat.title if message.chat.title else message.chat.id}\n"
        f"User: {user.first_name} {user.last_name if user.last_name else ''} (ID: {user.id}, Username: {'@' + user.username if user.username else 'Không có'})\n"
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
            await message.reply(f"✅ {user.first_name} đã được mở BLOCK sau {maybe_time}!\n" +
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
        f"🔇 Đã MUTE người dùng!\n"
        f"ID: {user.id}\n"
        f"Họ & Tên: {user.last_name if user.last_name else 'Không có'} {user.first_name if user.first_name else 'Không có'}\n"
        f"Username: {'@' + user.username if user.username else 'Không có'}\n"
        f"Hồ sơ: tg://user?id={user.id}\n"
        f"Lý do: {reason}\n"
    )
    if duration_seconds:
        mute_message += f"Thời gian MUTE: {maybe_time}"
    else:
        mute_message += "MUTE vĩnh viễn!"
    await message.reply(mute_message)
    pm_message = (
        f"[Mute Report]\nChat: {message.chat.title if message.chat.title else message.chat.id}\n"
        f"User: {user.first_name} {user.last_name if user.last_name else ''} (ID: {user.id}, Username: {'@' + user.username if user.username else 'Không có'})\n"
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
            await message.reply(
                f"✅ {user.first_name} đã được mở MUTE sau {maybe_time}!\n" +
                random.choice(funny_messages).format(name=user.first_name)
            )
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
        await message.reply(
            f"🕊️ {user.first_name} đã được xóa án Tử!\n" +
            random.choice(funny_messages).format(name=user.first_name)
        )
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
        await message.reply(
            f"🎤 {user.first_name} đã được XUNmute và được cấp lại đầy đủ quyền!\n" +
            random.choice(funny_messages).format(name=user.first_name)
        )
    except Exception as e:
        await message.reply(f"❌ Không thể mở mute! Lỗi: {e}")

# -------------------------------
# Lệnh “shizuku”: Chuyển đổi lệnh (ban, mute, unban, unmute, globan ban/unban)
# -------------------------------
@app.on_message(filters.regex(r"(?i)^shizuku(,| ơi)"))
async def shizuku_handler(client, message):
    if message.from_user.id not in OWNER_IDS:
        await message.reply("🚫 Bạn không có quyền sử dụng lệnh này.")
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
        await message.reply(
            "Bạn có thể dùng:\n"
            "shizuku ơi ban/block <ID/username> [thời gian] [lý do]\n"
            "shizuku ơi mute <ID/username> [thời gian] [lý do]\n"
            "shizuku ơi unban <ID/username>\n"
            "shizuku ơi unmute/ummute <ID/username>\n"
            "shizuku ơi globan ban <ID/username> (global ban chỉ ID 5867402532)\n"
            "shizuku ơi globan unban <ID/username> (global unban chỉ ID 5867402532)\n"
            "shizuku, bạn được ai tạo ra?"
        )
        return
    parts = command_text.split()
    cmd = parts[0].lower()
    if "globan ban" in command_text.lower():
        if message.from_user.id != 5867402532:
            await message.reply("🚫 Bạn không có quyền sử dụng lệnh global ban này!")
            return
        new_text = "/fban " + " ".join(parts[2:]) if len(parts) > 2 else "/fban"
        message.text = new_text
        await fban_user(client, message)
    elif "globan unban" in command_text.lower():
        if message.from_user.id != 5867402532:
            await message.reply("🚫 Bạn không có quyền sử dụng lệnh global unban này!")
            return
        new_text = "/funban " + " ".join(parts[2:]) if len(parts) > 2 else "/funban"
        message.text = new_text
        await funban_user(client, message)
    elif cmd in ["ban", "block"]:
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
        await message.reply("Lệnh không hợp lệ. Bạn có thể dùng: ban/block, mute, unban, unmute, globan ban/unban, hoặc 'shizuku, bạn được ai tạo ra'.")

# -------------------------------
# THÊM: TỰ ĐỘNG PHÁT HIỆN VÀ THÔNG BÁO ĐỔI TÊN/USERNAME
# Khi người dùng đổi tên hoặc username, bot sẽ gửi thông báo và lưu lại thông tin mới vào DB.
# -------------------------------
@app.on_chat_member_updated()
async def name_change_handler(client, event: ChatMemberUpdated):
    try:
        old_user = event.old_chat_member.user
        new_user = event.new_chat_member.user
        if old_user.id != new_user.id:
            return

        old_first = old_user.first_name or "Không có"
        new_first = new_user.first_name or "Không có"
        old_last = old_user.last_name or "Không có"
        new_last = new_user.last_name or "Không có"
        old_username = old_user.username or "Không có"
        new_username = new_user.username or "Không có"

        if old_first == new_first and old_last == new_last and old_username == new_username:
            return

        msg = (
            "Shizuku check🪪:\n"
            f"ID: {new_user.id} đã đổi thông tin✍️\n"
            f"🐮 Họ cũ: {old_last}\n"
            f"🐶 Tên cũ: {old_first}\n"
            f"🐒 Username cũ: {('@' + old_username) if old_username != 'Không có' else old_username}\n"
            "------------------\n"
            f"👤 Họ mới: {new_last}\n"
            f"🐱 Tên mới: {new_first}\n"
            f"🐳 Username mới: {('@' + new_username) if new_username != 'Không có' else new_username}"
        )
        await client.send_message(event.chat.id, msg)
        save_user_orm(event.chat.id, new_user, int(datetime.now().timestamp()))
    except Exception as e:
        print(f"Error in name_change_handler: {e}")

# -------------------------------
# Sự kiện: Khi thành viên rời nhóm, gửi lời tạm biệt.
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
                    f"👋 {user.first_name} {user.last_name or ''} vừa rời khỏi nhóm.\n"
                    f"ID: {user.id}\n"
                    f"Username: {'@' + user.username if user.username else 'Không có'}\n"
                    f"Tham gia từ: {join_time}"
                )
            else:
                farewell_message = (
                    f"👋 {user.first_name} {user.last_name or ''} vừa rời khỏi nhóm.\n"
                    f"ID: {user.id}\n"
                    f"Username: {'@' + user.username if user.username else 'Không có'}"
                )
            await client.send_message(chat_id, farewell_message)

# -------------------------------
# CHẠY BOT
# -------------------------------
if __name__ == "__main__":
    app.run()