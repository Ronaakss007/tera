import os
import json
import aiohttp
import requests
import logging
import glob
import speedtest
from datetime import datetime
from urllib.parse import urlparse
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserIsBlocked, FloodWait, InputUserDeactivated

logger = logging.getLogger(__name__)
from terabox import *  # Adjust the import based on your project structure

OWNER_ID = 7560922302
ADMINS = [OWNER_ID]  # Add more admin IDs as needed








@app.on_message(filters.command("info"))
async def user_info_command(client: Client, message: Message):
    """Command to get information about a user"""
    # Check if admin is requesting info about another user
    is_admin = message.from_user.id in ADMINS
    target_user_id = None
    
    # If admin is requesting info about another user via reply
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user_id = message.reply_to_message.from_user.id
    # If user ID is provided in command
    elif len(message.command) > 1:
        try:
            target_user_id = int(message.command[1])
        except ValueError:
            await message.reply_text("❌ ɪɴᴠᴀʟɪᴅ ᴜsᴇʀ ɪᴅ ғᴏʀᴍᴀᴛ. ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ɴᴜᴍᴇʀɪᴄ ɪᴅ.")
            return
    # If admin and no ID provided, ask for user ID
    elif is_admin:
        # Create a message to ask for user ID
        ask_msg = await message.reply_text(
            "🔍 ᴘʟᴇᴀsᴇ ᴇɴᴛᴇʀ ᴛʜᴇ ᴜsᴇʀ ɪᴅ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴄʜᴇᴄᴋ:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel_info")]
            ])
        )
        
        # Store this in a global dictionary to track waiting states
        if not hasattr(app, 'waiting_for_input'):
            app.waiting_for_input = {}
        
        app.waiting_for_input[message.from_user.id] = {
            'type': 'info_user_id',
            'message_id': ask_msg.id,
            'chat_id': message.chat.id,
            'timestamp': time.time()
        }
        
        # We'll return here and handle the response in a separate handler
        return
    else:
        # User is requesting their own info
        target_user_id = message.from_user.id
    
    # Continue with displaying user info...
    await display_user_info(client, message, target_user_id)

# Add a handler for text messages that could be responses to our prompts
@app.on_message(filters.text & filters.private)
async def handle_text_input(client: Client, message: Message):
    # Check if this user is waiting for input
    if hasattr(app, 'waiting_for_input') and message.from_user.id in app.waiting_for_input:
        input_data = app.waiting_for_input[message.from_user.id]
        
        # Check if the input is still valid (not expired)
        if time.time() - input_data['timestamp'] > 60:  # 60 seconds timeout
            del app.waiting_for_input[message.from_user.id]
            try:
                await client.delete_messages(input_data['chat_id'], input_data['message_id'])
            except Exception as e:
                logger.error(f"Error deleting message: {e}")
            await message.reply_text("⏱️ ᴛɪᴍᴇᴏᴜᴛ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.")
            return
        
        # Handle different types of expected input
        if input_data['type'] == 'info_user_id':
            # Try to parse the user ID
            try:
                target_user_id = int(message.text.strip())
                
                # Clean up
                del app.waiting_for_input[message.from_user.id]
                try:
                    await client.delete_messages(input_data['chat_id'], input_data['message_id'])
                except Exception as e:
                    logger.error(f"Error deleting message: {e}")
                
                # Display user info
                await display_user_info(client, message, target_user_id)
            except ValueError:
                await message.reply_text("❌ ɪɴᴠᴀʟɪᴅ ᴜsᴇʀ ɪᴅ ғᴏʀᴍᴀᴛ. ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ɴᴜᴍᴇʀɪᴄ ɪᴅ.")
                return
        
        # Don't process this message further
        return

# Add a callback handler for the cancel button
@app.on_callback_query(filters.regex("^cancel_info$"))
async def cancel_info_request(client, callback_query):
    user_id = callback_query.from_user.id
    
    if hasattr(app, 'waiting_for_input') and user_id in app.waiting_for_input:
        del app.waiting_for_input[user_id]
    
    await callback_query.message.delete()
    await callback_query.answer("ᴏᴘᴇʀᴀᴛɪᴏɴ ᴄᴀɴᴄᴇʟʟᴇᴅ.")

# Separate function to display user info
async def display_user_info(client, message, target_user_id):
    """Display information about a user"""
    is_admin = message.from_user.id in ADMINS
    
    # Get user data from database
    user_data = collection.find_one({"user_id": target_user_id})
    
    if not user_data and not is_admin:
        # If no data found for self-lookup, create basic entry
        user_data = {
            "user_id": target_user_id,
            "created_at": datetime.now(),
            "token_status": "inactive",
            "downloads": 0,
            "total_download_size": 0
        }
        collection.insert_one(user_data)
    elif not user_data and is_admin:
        await message.reply_text(f"❌ ɴᴏ ᴅᴀᴛᴀ ғᴏᴜɴᴅ ғᴏʀ ᴜsᴇʀ ɪᴅ: `{target_user_id}`")
        return
    
    # Get user info from Telegram
    try:
        user = await client.get_users(target_user_id)
        username = f"@{user.username}" if user.username else "ɴᴏɴᴇ"
        full_name = f"{user.first_name} {user.last_name if user.last_name else ''}"
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        username = "ᴜɴᴋɴᴏᴡɴ"
        full_name = "ᴜɴᴋɴᴏᴡɴ ᴜsᴇʀ"
    
    # Format user information
    created_at = user_data.get("created_at", "ᴜɴᴋɴᴏᴡɴ")
    if isinstance(created_at, datetime):
        created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")
    
    token_status = user_data.get("token_status", "inactive")
    token_expiry = user_data.get("token_expiry")
    if token_expiry and isinstance(token_expiry, datetime):
        if token_expiry > datetime.now():
            token_expiry_str = f"ᴇxᴘɪʀᴇs: {token_expiry.strftime('%Y-%m-%d %H:%M:%S')}"
            time_left = token_expiry - datetime.now()
            hours, remainder = divmod(time_left.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            token_expiry_str += f" ({time_left.days}ᴅ {hours}ʜ {minutes}ᴍ ʟᴇғᴛ)"
        else:
            token_expiry_str = "ᴇxᴘɪʀᴇᴅ"
    else:
        token_expiry_str = "ɴ/ᴀ"
    
    downloads = user_data.get("downloads", 0)
    total_download_size = format_size(user_data.get("total_download_size", 0))
    last_download = user_data.get("last_download")
    if last_download and isinstance(last_download, datetime):
        last_download = last_download.strftime("%Y-%m-%d %H:%M:%S")
    else:
        last_download = "ɴᴇᴠᴇʀ"
    
    pending_requests = user_data.get("pending_requests", [])
    pending_count = len(pending_requests) if pending_requests else 0
    
    # Create info message with small caps
    info_text = (
        f"📊 <b>ᴜsᴇʀ ɪɴғᴏʀᴍᴀᴛɪᴏɴ</b> 📊\n\n"
        f"<b>🆔 ᴜsᴇʀ ɪᴅ:</b> <code>{target_user_id}</code>\n"
        f"<b>👤 ɴᴀᴍᴇ:</b> {full_name}\n"
        f"<b>🔖 ᴜsᴇʀɴᴀᴍᴇ:</b> {username}\n"
        f"<b>📅 ᴊᴏɪɴᴇᴅ:</b> {created_at}\n\n"
        
        f"<b>🔑 ᴛᴏᴋᴇɴ sᴛᴀᴛᴜs:</b> {'✅ ᴀᴄᴛɪᴠᴇ' if token_status == 'active' else '❌ ɪɴᴀᴄᴛɪᴠᴇ'}\n"
        f"<b>⏳ ᴛᴏᴋᴇɴ ᴇxᴘɪʀʏ:</b> {token_expiry_str}\n\n"
        
        f"<b>📈 ᴀᴄᴛɪᴠɪᴛʏ:</b>\n"
        f"<b>• ᴅᴏᴡɴʟᴏᴀᴅs:</b> {downloads}\n"
        f"<b>• ᴛᴏᴛᴀʟ sɪᴢᴇ:</b> {total_download_size}\n"
        f"<b>• ʟᴀsᴛ ᴅᴏᴡɴʟᴏᴀᴅ:</b> {last_download}\n"
        f"<b>• ᴘᴇɴᴅɪɴɢ ʀᴇǫᴜᴇsᴛs:</b> {pending_count}\n"
    )
    
    # Add admin options if admin is viewing another user
    if is_admin and target_user_id != message.from_user.id:
        keyboard = [
            [InlineKeyboardButton("🔄 ʀᴇғʀᴇsʜ", callback_data=f"refresh_info_{target_user_id}")],
            [
                InlineKeyboardButton("🔑 ᴀᴄᴛɪᴠᴀᴛᴇ ᴛᴏᴋᴇɴ", callback_data=f"activate_token_{target_user_id}"),
                InlineKeyboardButton("🚫 ᴅᴇᴀᴄᴛɪᴠᴀᴛᴇ ᴛᴏᴋᴇɴ", callback_data=f"deactivate_token_{target_user_id}")
            ],
            [InlineKeyboardButton("❌ ᴅᴇʟᴇᴛᴇ ᴜsᴇʀ", callback_data=f"delete_user_{target_user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
    else:
        reply_markup = None
    
    await message.reply_text(info_text, reply_markup=reply_markup)

@app.on_callback_query(filters.regex(r"^refresh_info_(\d+)$"))
async def refresh_info_callback(client, callback_query):
    if callback_query.from_user.id not in ADMINS:
        return await callback_query.answer("ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴅᴏ ᴛʜɪs.", show_alert=True)
    
    user_id = int(callback_query.data.split("_")[2])
    
    # Create a message object with the necessary attributes
    message = callback_query.message
    message.command = ["info", str(user_id)]
    message.from_user = callback_query.from_user
    
    # Call the display_user_info function directly
    await display_user_info(client, message, user_id)
    
    # Delete the original message to avoid clutter
    await callback_query.message.delete()

@app.on_callback_query(filters.regex(r"^activate_token_(\d+)$"))
async def activate_user_token(client, callback_query):
    if callback_query.from_user.id not in ADMINS:
        return await callback_query.answer("ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴅᴏ ᴛʜɪs.", show_alert=True)
    
    user_id = int(callback_query.data.split("_")[2])
    
    # Generate and activate token
    token = str(uuid.uuid4())
    expiry = datetime.now() + timedelta(hours=12)
    
    collection.update_one(
        {"user_id": user_id},
        {"$set": {"token": token, "token_status": "active", "token_expiry": expiry}},
        upsert=True
    )
    
    await callback_query.answer("ᴛᴏᴋᴇɴ ᴀᴄᴛɪᴠᴀᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!", show_alert=True)
    
    # Refresh the info display
    message = callback_query.message
    message.command = ["info", str(user_id)]
    message.from_user = callback_query.from_user
    await display_user_info(client, message, user_id)
    await callback_query.message.delete()

@app.on_callback_query(filters.regex(r"^deactivate_token_(\d+)$"))
async def deactivate_user_token(client, callback_query):
    if callback_query.from_user.id not in ADMINS:
        return await callback_query.answer("ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴅᴏ ᴛʜɪs.", show_alert=True)
    
    user_id = int(callback_query.data.split("_")[2])
    
    collection.update_one(
        {"user_id": user_id},
        {"$set": {"token_status": "inactive"}}
    )
    
    await callback_query.answer("ᴛᴏᴋᴇɴ ᴅᴇᴀᴄᴛɪᴠᴀᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!", show_alert=True)
    
    # Refresh the info display
    message = callback_query.message
    message.command = ["info", str(user_id)]
    message.from_user = callback_query.from_user
    await display_user_info(client, message, user_id)
    await callback_query.message.delete()

@app.on_callback_query(filters.regex(r"^delete_user_(\d+)$"))
async def delete_user_data(client, callback_query):
    if callback_query.from_user.id not in ADMINS:
        return await callback_query.answer("ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴅᴏ ᴛʜɪs.", show_alert=True)
    
    user_id = int(callback_query.data.split("_")[2])
    
    # Confirm deletion with a new keyboard
    confirm_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ ʏᴇs, ᴅᴇʟᴇᴛᴇ", callback_data=f"confirm_delete_{user_id}"),
            InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data=f"cancel_delete_{user_id}")
        ]
    ])
    
    await callback_query.message.edit_text(
        f"⚠️ ᴀʀᴇ ʏᴏᴜ sᴜʀᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴅᴇʟᴇᴛᴇ ᴀʟʟ ᴅᴀᴛᴀ ғᴏʀ ᴜsᴇʀ ɪᴅ: `{user_id}`?\n\n"
        "ᴛʜɪs ᴀᴄᴛɪᴏɴ ᴄᴀɴɴᴏᴛ ʙᴇ ᴜɴᴅᴏɴᴇ.",
        reply_markup=confirm_keyboard
    )

@app.on_callback_query(filters.regex(r"^confirm_delete_(\d+)$"))
async def confirm_delete_user(client, callback_query):
    if callback_query.from_user.id not in ADMINS:
        return await callback_query.answer("ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴅᴏ ᴛʜɪs.", show_alert=True)
    
    user_id = int(callback_query.data.split("_")[2])
    
    # Delete user data
    result = collection.delete_one({"user_id": user_id})
    
    if result.deleted_count > 0:
        await callback_query.message.edit_text(f"✅ ᴜsᴇʀ ᴅᴀᴛᴀ ғᴏʀ ɪᴅ: `{user_id}` ʜᴀs ʙᴇᴇɴ ᴅᴇʟᴇᴛᴇᴅ.")
    else:
        await callback_query.message.edit_text(f"❌ ɴᴏ ᴅᴀᴛᴀ ғᴏᴜɴᴅ ғᴏʀ ᴜsᴇʀ ɪᴅ: `{user_id}`.")

@app.on_callback_query(filters.regex(r"^cancel_delete_(\d+)$"))
async def cancel_delete_user(client, callback_query):
    if callback_query.from_user.id not in ADMINS:
        return await callback_query.answer("ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴅᴏ ᴛʜɪs.", show_alert=True)
    
    user_id = int(callback_query.data.split("_")[2])
    
    # Go back to user info display
    message = callback_query.message
    message.command = ["info", str(user_id)]
    message.from_user = callback_query.from_user
    await display_user_info(client, message, user_id)
    await callback_query.message.delete()
