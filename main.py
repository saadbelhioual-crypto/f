import threading
import jwt
import random
from threading import Thread
import json
import requests 
import google.protobuf
from protobuf_decoder.protobuf_decoder import Parser
import json
import datetime
from google.protobuf.json_format import MessageToJson
import my_message_pb2
import data_pb2
import base64
import logging
import re
import socket
from google.protobuf.timestamp_pb2 import Timestamp
import jwt_generator_pb2
import os
import binascii
import sys
import MajorLoginRes_pb2
from time import sleep
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import time
import urllib3
from important_zitado import*
from byte import*
from datetime import datetime, timedelta
import queue
import hashlib
import io
import gc
import html

# إعدادات السجلات
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_logs.log')
    ]
)
logger = logging.getLogger(__name__)


TELEGRAM_BOT_TOKEN = "هون توكن بوتك"
TELEGRAM_CHAT_ID = "هون ايدي مجموعتك"


GROUPS_FILE = "groups_data.json"
ACCOUNTS_FILE = "accounts.json"
ADMIN_ID = "هون ايديك على تلجرام"


RESTART_ON_DISCONNECT = True
MAX_RESTART_ATTEMPTS = 10
RESTART_DELAY = 5


MAX_CONCURRENT_REQUESTS = 10
MAX_ACCOUNTS = 10


ACCOUNT_RESTART_INTERVAL = 180

def restart_bot():
    """Restart the bot program"""
    print("🔄 Restarting bot...")
    os.execv(sys.executable, ['python'] + sys.argv)


tempid = None
sent_inv = False
start_par = False
pleaseaccept = False
nameinv = "none"
idinv = 0
senthi = False
statusinfo = False
tempdata1 = None
tempdata = None
leaveee = False
leaveee1 = False
data22 = None
isroom = False
isroom2 = False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


current_clients = []
command_queue = queue.Queue()
command_lock = threading.Lock()
command_processing = False
pending_messages = {}
threads = []


account_index = 0
accounts_loaded = []


last_connection_time = time.time()
CONNECTION_TIMEOUT = 300


bot_connected = False
telegram_ready = False
game_ready = False


active_requests_per_account = {}

# ==================== SPAM SYSTEM VARIABLES ====================
_target_owners = {}
_target_owners_lock = threading.Lock()
_spam_tasks = {}
_spam_active_semaphore = threading.BoundedSemaphore(15)

# ==================== FRIEND SYSTEM VARIABLES ====================
FRIENDS_DATA_FILE = "friends_data.json"
JWT_TOKEN = None
_ENCRYPTION_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
_ENCRYPTION_IV = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
_friends_data = {}
_friends_daily_usage = {}

# ==================== HELPER FUNCTION FOR JWT ====================
def get_jwt_token():
    """Get JWT token, fetch if not available"""
    global JWT_TOKEN
    if not JWT_TOKEN:
        JWT_TOKEN = _fetch_jwt_token()
    return JWT_TOKEN

def load_accounts():
    """تحميل الحسابات من ملف JSON"""
    global accounts_loaded
    
    try:
        if os.path.exists(ACCOUNTS_FILE):
            with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                accounts = json.load(f)
                logger.info(f"✅ تم تحميل {len(accounts)} حساب من {ACCOUNTS_FILE}")
                accounts_loaded = accounts[:MAX_ACCOUNTS]
                for account in accounts_loaded:
                    uid = str(account.get('uid', ''))
                    active_requests_per_account[uid] = 0
                return accounts_loaded
        else:
            logger.error(f"❌ ملف {ACCOUNTS_FILE} غير موجود")
            return []
    except Exception as e:
        logger.error(f"⚠️ خطأ في تحميل الحسابات: {e}")
        return []

def get_next_account():
    """الحصول على الحساب التالي في الدور"""
    global account_index
    if not accounts_loaded:
        accounts_loaded = load_accounts()
    
    if not accounts_loaded:
        return None
    
    account = accounts_loaded[account_index]
    account_index = (account_index + 1) % len(accounts_loaded)
    return account

def check_connection_health():
    """Check if connection is healthy and restart if needed"""
    global last_connection_time, restart_count, bot_connected
    
    if not bot_connected:
        return
        
    current_time = time.time()
    if current_time - last_connection_time > CONNECTION_TIMEOUT:
        logger.warning(f"⚠️ Connection timeout detected. Last activity: {current_time - last_connection_time:.0f} seconds ago")
        
        if RESTART_ON_DISCONNECT and restart_count < MAX_RESTART_ATTEMPTS:
            restart_count += 1
            logger.info(f"🔄 Attempting restart #{restart_count}")
            time.sleep(RESTART_DELAY)
            restart_bot()
    
    if restart_count > 0 and current_time - last_connection_time < 10:
        restart_count = 0

def update_connection_time():
    """Update last connection activity time"""
    global last_connection_time, bot_connected
    last_connection_time = time.time()
    bot_connected = True

# Group management functions
def load_groups_data():
    """Load groups data from JSON file"""
    try:
        if os.path.exists(GROUPS_FILE):
            with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"⚠️ Error loading groups data: {e}")
        return {}

def save_groups_data(groups_data):
    """Save groups data to JSON file"""
    try:
        with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
            json.dump(groups_data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        logger.error(f"⚠️ Error saving groups data: {e}")
        return False

def is_group_active(chat_id):
    """Check if group is active and valid"""
    groups_data = load_groups_data()
    chat_id_str = str(chat_id)
    
    if chat_id_str in groups_data:
        group_data = groups_data[chat_id_str]
        expiry_date = datetime.fromisoformat(group_data['expiry_date'])
        
        if datetime.now() < expiry_date:
            return True
        else:
            del groups_data[chat_id_str]
            save_groups_data(groups_data)
            return False
    return False

def activate_group(chat_id, days, admin_id):
    """Activate new group or renew existing"""
    if str(admin_id) != ADMIN_ID:
        return False, "❌ You don't have permission to activate the bot"
    
    groups_data = load_groups_data()
    chat_id_str = str(chat_id)
    
    expiry_date = datetime.now() + timedelta(days=days)
    
    groups_data[chat_id_str] = {
        'activated_by': admin_id,
        'activation_date': datetime.now().isoformat(),
        'expiry_date': expiry_date.isoformat(),
        'days': days
    }
    
    if save_groups_data(groups_data):
        return True, f"✅ Bot activated in group for {days} days\n⏰ Expires: {expiry_date.strftime('%Y-%m-%d %H:%M')}"
    else:
        return False, "❌ Error saving data"

def deactivate_group(chat_id, admin_id):
    """Deactivate group"""
    if str(admin_id) != ADMIN_ID:
        return False, "❌ You don't have permission to deactivate"
    
    groups_data = load_groups_data()
    chat_id_str = str(chat_id)
    
    if chat_id_str in groups_data:
        del groups_data[chat_id_str]
        if save_groups_data(groups_data):
            return True, "✅ Bot deactivated in this group"
        else:
            return False, "❌ Error saving data"
    else:
        return False, "❌ Group is not activated"

def get_group_info(chat_id):
    """Get group information"""
    groups_data = load_groups_data()
    chat_id_str = str(chat_id)
    
    if chat_id_str in groups_data:
        group_data = groups_data[chat_id_str]
        expiry_date = datetime.fromisoformat(group_data['expiry_date'])
        activation_date = datetime.fromisoformat(group_data['activation_date'])
        days_left = (expiry_date - datetime.now()).days
        
        if days_left > 0:
            return f"📊 Activation Information:\n├─ Activated: {activation_date.strftime('%Y-%m-%d %H:%M')}\n├─ Expires: {expiry_date.strftime('%Y-%m-%d %H:%M')}\n├─ Days left: {days_left} days\n└─ By: {group_data['activated_by']}"
        else:
            return "❌ Activation expired"
    else:
        return "❌ Group not activated"

def get_all_groups():
    """Get list of all activated groups"""
    groups_data = load_groups_data()
    if not groups_data:
        return "❌ No active groups"
    
    active_groups = []
    expired_groups = []
    
    for chat_id, group_data in groups_data.items():
        expiry_date = datetime.fromisoformat(group_data['expiry_date'])
        days_left = (expiry_date - datetime.now()).days
        
        group_info = f"• 🆔 `{chat_id}` | 📅 {days_left} days left"
        
        if days_left > 0:
            active_groups.append(group_info)
        else:
            expired_groups.append(group_info)
    
    result = "📊 Active Groups:\n"
    if active_groups:
        result += "\n".join(active_groups)
    else:
        result += "❌ No active groups\n"
    
    if expired_groups:
        result += "\n\n📊 Expired Groups:\n"
        result += "\n".join(expired_groups)
    
    return result

# Helper functions
def dec_to_hex(ask):
    """Convert decimal to hex"""
    ask_result = hex(ask)
    final_result = str(ask_result)[2:]
    if len(final_result) == 1:
        final_result = "0" + final_result
        return final_result
    else:
        return final_result

def send_telegram_message(message, parse_mode="HTML", chat_id=None, message_id=None, no_signature=False, reply_to_message_id=None):
    """Send message to Telegram with optional reply"""
    try:
        if chat_id is None:
            chat_id = TELEGRAM_CHAT_ID
        
        if not no_signature:
            signature = "\n\n────────────────────\n"
            signature += "👑 Developer: AlliFF"
            message_with_signature = message + signature
        else:
            message_with_signature = message
            
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message_with_signature,
            "parse_mode": parse_mode
        }
        
        if reply_to_message_id:
            data["reply_to_message_id"] = reply_to_message_id
            
        response = requests.post(url, data=data, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"⚠️ Error sending Telegram message: {e}")

def edit_telegram_message(chat_id, message_id, new_text, parse_mode="HTML"):
    """Edit existing Telegram message"""
    try:
        signature = "\n\n────────────────────\n"
        signature += "👑 Developer: AlliFF"
        
        new_text_with_signature = new_text + signature
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
        data = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": new_text_with_signature,
            "parse_mode": parse_mode
        }
        response = requests.post(url, data=data, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"⚠️ Error editing Telegram message: {e}")

def delete_telegram_message(chat_id, message_id):
    """Delete Telegram message"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteMessage"
        data = {
            "chat_id": chat_id,
            "message_id": message_id
        }
        response = requests.post(url, data=data, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"⚠️ Error deleting Telegram message: {e}")

def send_private_message(user_id, message, parse_mode="HTML"):
    """Send private message to user"""
    try:
        signature = "\n\n────────────────────\n"
        signature += "👑 Developer: AlliFF"
        
        message_with_signature = message + signature
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": user_id,
            "text": message_with_signature,
            "parse_mode": parse_mode
        }
        response = requests.post(url, data=data, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"⚠️ Error sending private message: {e}")

def encrypt_packet(plain_text, key, iv):
    plain_text = bytes.fromhex(plain_text)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    cipher_text = cipher.encrypt(pad(plain_text, AES.block_size))
    return cipher_text.hex()
    
def gethashteam(hexxx):
    a = zitado_get_proto(hexxx)
    if not a:
        raise ValueError("Invalid hex format or empty response from zitado_get_proto")
    data = json.loads(a)
    return data['5']['7']

def getownteam(hexxx):
    a = zitado_get_proto(hexxx)
    if not a:
        raise ValueError("Invalid hex format or empty response from zitado_get_proto")
    data = json.loads(a)
    return data['5']['1']

def get_player_status(packet):
    json_result = get_available_room(packet)
    parsed_data = json.loads(json_result)

    if "5" not in parsed_data or "data" not in parsed_data["5"]:
        return "OFFLINE"

    json_data = parsed_data["5"]["data"]

    if "1" not in json_data or "data" not in json_data["1"]:
        return "OFFLINE"

    data = json_data["1"]["data"]

    if "3" not in data:
        return "OFFLINE"

    status_data = data["3"]

    if "data" not in status_data:
        return "OFFLINE"

    status = status_data["data"]

    if status == 1:
        return "SOLO"
    
    if status == 2:
        if "9" in data and "data" in data["9"]:
            group_count = data["9"]["data"]
            countmax1 = data["10"]["data"]
            countmax = countmax1 + 1
            return f"INSQUAD ({group_count}/{countmax})"

        return "INSQUAD"
    
    if status in [3, 5]:
        return "INGAME"
    if status == 4:
        return "IN ROOM"
    
    if status in [6, 7]:
        return "IN SOCIAL ISLAND MODE"

def get_random_avatar():
    avatar_list = [
        '902000061', '902000060', '902000064', '902000065', '902000066', 
        '902000074', '902000075', '902000077', '902000078', '902000084', 
        '902000085', '902000087', '902000091', '902000094', '902000306',
        '902000091','902000208','902000209','902000210','902000211',
        '902047016','902047016','902000347'
    ]
    return random.choice(avatar_list)

def convert_to_hex(PAYLOAD):
    hex_payload = ''.join([f'{byte:02x}' for byte in PAYLOAD])
    return hex_payload

def convert_to_bytes(PAYLOAD):
    payload = bytes.fromhex(PAYLOAD)
    return payload

def time_to_seconds(hours, minutes, seconds):
    return (hours * 3600) + (minutes * 60) + seconds

def seconds_to_hex(seconds):
    return format(seconds, '04x')

def extract_time_from_timestamp(timestamp):
    dt = datetime.fromtimestamp(timestamp)
    h = dt.hour
    m = dt.minute
    s = dt.second
    return h, m, s

def encrypt_message(plaintext):
    key = b'Yg&tc%DEuh6%Zc^8'
    iv = b'6oyZDr22E3ychjM%'
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_message = pad(plaintext, AES.block_size)
    encrypted_message = cipher.encrypt(padded_message)
    return binascii.hexlify(encrypted_message).decode('utf-8')

def encrypt_api(plain_text):
    plain_text = bytes.fromhex(plain_text)
    key = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
    iv = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
    cipher = AES.new(key, AES.MODE_CBC, iv)
    cipher_text = cipher.encrypt(pad(plain_text, AES.block_size))
    return cipher_text.hex()

def extract_jwt_from_hex(hex):
    byte_data = binascii.unhexlify(hex)
    message = jwt_generator_pb2.Garena_420()
    message.ParseFromString(byte_data)
    json_output = MessageToJson(message)
    token_data = json.loads(json_output)
    return token_data

def format_timestamp(timestamp):
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

def get_available_room(input_text):
    try:
        parsed_results = Parser().parse(input_text)
        parsed_results_objects = parsed_results
        parsed_results_dict = parse_results(parsed_results_objects)
        json_data = json.dumps(parsed_results_dict)
        return json_data
    except Exception as e:
        logger.error(f"error {e}")
        return None

def parse_results(parsed_results):
    result_dict = {}
    for result in parsed_results:
        field_data = {}
        field_data["wire_type"] = result.wire_type
        if result.wire_type == "varint":
            field_data["data"] = result.data
        if result.wire_type == "string":
            field_data["data"] = result.data
        if result.wire_type == "bytes":
            field_data["data"] = result.data
        elif result.wire_type == "length_delimited":
            field_data["data"] = parse_results(result.data.results)
        result_dict[result.field] = field_data
    return result_dict

# ==================== FRIEND SYSTEM CORE FUNCTIONS ====================

def _encode_varint(number):
    """تشفير رقم إلى Varint"""
    if number < 0:
        raise ValueError("Number must be non-negative")
    encoded_bytes = []
    while True:
        byte = number & 0x7F
        number >>= 7
        if number:
            byte |= 0x80
        encoded_bytes.append(byte)
        if not number:
            break
    return bytes(encoded_bytes)

def _encrypt_id(number):
    """تشفير ID اللاعب"""
    number = int(number)
    encoded_bytes = []
    while True:
        byte = number & 0x7F
        number >>= 7
        if number:
            byte |= 0x80
        encoded_bytes.append(byte)
        if not number:
            break
    return bytes(encoded_bytes).hex()

def _encrypt_friend_packet(plain_text):
    """تشفير حزمة طلب الصداقة"""
    plain_text_bytes = bytes.fromhex(plain_text)
    cipher = AES.new(_ENCRYPTION_KEY, AES.MODE_CBC, _ENCRYPTION_IV)
    cipher_text = cipher.encrypt(pad(plain_text_bytes, AES.block_size))
    return cipher_text.hex()

def _fetch_jwt_token():
    """جلب التوكن من API"""
    global JWT_TOKEN
    try:
        uid = "4803659572"
        password = "E556FC705B78E6EF0290D937386442EBD95B9AD603EAFC79F3D96DC312DC203A"
        
        url = "https://100067.connect.garena.com/oauth/guest/token/grant"
        headers = {
            "Host": "100067.connect.garena.com",
            "User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 9;en;US;)",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "uid": f"{uid}",
            "password": f"{password}",
            "response_type": "token",
            "client_type": "2",
            "client_secret": "",
            "client_id": "100067",
        }
        
        response = requests.post(url, headers=headers, data=data, timeout=15, verify=False)
        resp_data = response.json()
        
        if "access_token" not in resp_data or "open_id" not in resp_data:
            logger.error("Failed to get access_token or open_id")
            return None
        
        NEW_ACCESS_TOKEN = resp_data['access_token']
        NEW_OPEN_ID = resp_data['open_id']
        OLD_ACCESS_TOKEN = "c69ae208fad72738b674b2847b50a3a1dfa25d1a19fae745fc76ac4a0e414c94"
        OLD_OPEN_ID = "4306245793de86da425a52caadf21eed"
        
        data_bytes = bytes.fromhex('1a13323032352d31312d32362030313a35313a3238220966726565206669726528013a07312e3132332e314232416e64726f6964204f532039202f204150492d3238202850492f72656c2e636a772e32303232303531382e313134313333294a0848616e6468656c64520c4d544e2f537061636574656c5a045749464960800a68d00572033234307a2d7838362d3634205353453320535345342e3120535345342e32204156582041565832207c2032343030207c20348001e61e8a010f416472656e6f2028544d292036343092010d4f70656e474c20455320332e329a012b476f6f676c657c36323566373136662d393161372d343935622d396631362d303866653964336336353333a2010e3137362e32382e3133392e313835aa01026172b201203433303632343537393364653836646134323561353263616164663231656564ba010134c2010848616e6468656c64ca010d4f6e65506c7573204135303130ea014063363961653230386661643732373338623637346232383437623530613361316466613235643161313966616537343566633736616334613065343134633934f00101ca020c4d544e2f537061636574656cd2020457494649ca03203161633462383065636630343738613434323033626638666163363132306635e003b5ee02e8039a8002f003af13f80384078004a78f028804b5ee029004a78f029804b5ee02b00404c80401d2043d2f646174612f6170702f636f6d2e6474732e667265656669726574682d66705843537068495636644b43376a4c2d574f7952413d3d2f6c69622f61726de00401ea045f65363261623933353464386662356662303831646233333861636233333439317c2f646174612f6170702f636f6d2e6474732e667265656669726574682d66705843537068495636644b43376a4c2d574f7952413d3d2f626173652e61706bf00406f804018a050233329a050a32303139313139303236a80503b205094f70656e474c455332b805ff01c00504e005be7eea05093372645f7061727479f205704b717348543857393347646347335a6f7a454e6646775648746d377171316552554e6149444e67526f626f7a4942744c4f695943633459367a767670634943787a514632734f453463627974774c7334785a62526e70524d706d5752514b6d654f35766373386e51594268777148374bf805e7e4068806019006019a060134a2060134b2062213521146500e590349510e460900115843395f005b510f685b560a6107576d0f0366')
        
        data_bytes = data_bytes.replace(OLD_OPEN_ID.encode(), NEW_OPEN_ID.encode())
        data_bytes = data_bytes.replace(OLD_ACCESS_TOKEN.encode(), NEW_ACCESS_TOKEN.encode())
        
        encrypted = _encrypt_friend_packet(data_bytes.hex())
        
        headers = {
            "Host": "loginbp.ggpolarbear.com",
            "X-Unity-Version": "2018.4.11f1",
            "ReleaseVersion": "OB53",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-GA": "v1 1",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; G011A Build/PI)",
            "Connection": "Keep-Alive",
        }
        
        response = requests.post("https://loginbp.ggpolarbear.com/MajorLogin", 
                                headers=headers, data=bytes.fromhex(encrypted), timeout=15, verify=False)
        
        if response.status_code == 200:
            text = response.text
            start_idx = text.find("eyJhbGciOiJIUzI1NiIsInN2ciI6IjEiLCJ0eXAiOiJKV1QifQ")
            if start_idx != -1:
                second_dot = text.find(".", text.find(".", start_idx) + 1)
                token = text[start_idx:second_dot + 44]
                return token
        
        return None
    except Exception as e:
        logger.error(f"Error fetching JWT token: {e}")
        return None

def _get_player_info(uid):
    """جلب معلومات اللاعب من API"""
    try:
        url = f"https://otman-info.vercel.app/player-info?uid={uid}"
        response = requests.get(url, timeout=10)
        data = response.json()
        info = data.get("basicInfo", {})
        name = info.get("nickname", "Unknown")
        region = info.get("region", "N/A")
        level = info.get("level", "N/A")
        return name, region, level
    except Exception as e:
        logger.error(f"Error fetching player info: {e}")
        return "Unknown", "N/A", "N/A"

def _send_friend_request(player_id, jwt_token):
    """إرسال طلب صداقة"""
    if not jwt_token:
        return False, "⚠️ Token not available"
    
    try:
        enc_id = _encrypt_id(player_id)
        payload = f"08a7c4839f1e10{enc_id}1801"
        encrypted_payload = _encrypt_friend_packet(payload)
        
        url = "https://clientbp.ggpolarbear.com/RequestAddingFriend"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "X-Unity-Version": "2018.4.11f1",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB53",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Dalvik/2.1.0 (Linux; Android 9)",
        }
        
        response = requests.post(url, headers=headers, data=bytes.fromhex(encrypted_payload), timeout=15, verify=False)
        
        if response.status_code == 200:
            if "BR_FRIEND_NOT_SAME_REGION" in response.text:
                return False, "❌ Player is not in the same region"
            return True, "✅ Friend request sent successfully!"
        elif response.status_code == 401:
            return False, "⚠️ Token expired, please try again"
        else:
            return False, f"❌ Failed with status code: {response.status_code}"
            
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def _remove_friend(player_id, jwt_token):
    """حذف صديق"""
    if not jwt_token:
        return False, "⚠️ Token not available"
    
    try:
        enc_id = _encrypt_id(player_id)
        payload = f"08a7c4839f1e10{enc_id}1802"
        encrypted_payload = _encrypt_friend_packet(payload)
        
        url = "https://clientbp.ggpolarbear.com/RemoveFriend"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "X-Unity-Version": "2018.4.11f1",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB53",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Dalvik/2.1.0 (Linux; Android 9)",
        }
        
        response = requests.post(url, headers=headers, data=bytes.fromhex(encrypted_payload), timeout=15, verify=False)
        
        if response.status_code == 200:
            return True, "✅ Friend removed successfully!"
        elif response.status_code == 401:
            return False, "⚠️ Token expired, please try again"
        else:
            return False, f"❌ Failed with status code: {response.status_code}"
            
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def _load_friends_data():
    """تحميل بيانات الأصدقاء من ملف JSON"""
    global _friends_data
    try:
        if os.path.exists(FRIENDS_DATA_FILE):
            with open(FRIENDS_DATA_FILE, 'r', encoding='utf-8') as f:
                _friends_data = json.load(f)
        else:
            _friends_data = {}
    except Exception as e:
        logger.error(f"Error loading friends data: {e}")
        _friends_data = {}

def _save_friends_data():
    """حفظ بيانات الأصدقاء إلى ملف JSON"""
    try:
        with open(FRIENDS_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(_friends_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Error saving friends data: {e}")

def _get_friends_count():
    """الحصول على عدد الأصدقاء المضافين"""
    return len([uid for uid, data in _friends_data.items() if isinstance(data, dict) and "name" in data])

def _format_remaining_time(expiry_timestamp):
    """تنسيق الوقت المتبقي"""
    remaining = int(expiry_timestamp - time.time())
    if remaining <= 0:
        return "⛔ Expired"
    
    days = remaining // 86400
    hours = (remaining % 86400) // 3600
    minutes = ((remaining % 86400) % 3600) // 60
    seconds = remaining % 60
    
    if days > 0:
        return f"{days}d {hours}h"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def _update_jwt_periodically():
    """تحديث التوكن بشكل دوري"""
    global JWT_TOKEN
    while True:
        new_token = _fetch_jwt_token()
        if new_token:
            JWT_TOKEN = new_token
            logger.info("🔄 JWT token updated successfully")
        time.sleep(5 * 3600)  # كل 5 ساعات

def _remove_expired_friends():
    """إزالة الأصدقاء منتهي الصلاحية"""
    while True:
        now = time.time()
        expired = [uid for uid, data in _friends_data.items() 
                  if isinstance(data, dict) and data.get("expiry", 0) <= now]
        
        for uid in expired:
            if uid in _friends_data:
                del _friends_data[uid]
        
        if expired:
            _save_friends_data()
            logger.info(f"🗑️ Removed {len(expired)} expired friends")
        
        time.sleep(60)

# ==================== INFO COMMAND FUNCTIONS ====================

def format_player_info(data: dict) -> str:
    """تنسيق بيانات اللاعب بالشكل المطلوب"""
    
    info = data.get("basicInfo", {})
    clan = data.get("clanBasicInfo", {})
    captain = data.get("captainBasicInfo", {})
    pet = data.get("petInfo", {})
    social = data.get("socialInfo", {})
    credit = data.get("creditScoreInfo", {})
    diamond = data.get("diamondCostRes", {})
    
    formatted_text = (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "ACCOUNT INFO\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"NAME => {info.get('nickname', 'N/A')}\n"
        f"UID => {info.get('accountId', 'N/A')}\n"
        f"Region => {info.get('region', 'N/A')}\n"
        f"Level => {info.get('level', 'N/A')} | EXP => {info.get('exp', 0):,}\n\n"
        "RANK INFO\n"
        f"• BR Rank => {info.get('rank', 'N/A')} | {info.get('rankingPoints', 0)} pts\n"
        f"• Max Rank => {info.get('maxRank', 'N/A')}\n"
        f"• CS Rank => {info.get('csRank', 'N/A')} | {info.get('csRankingPoints', 0)} pts\n\n"
        "ACCOUNT DETAILS\n"
        f"• Badges => {info.get('badgeCnt', 0)}\n"
        f"• Likes => {info.get('liked', 0):,}\n"
        "• Elite Pass => No\n"
        f"• Season => {info.get('seasonId', 'N/A')}\n"
        f"• Version => {info.get('releaseVersion', 'N/A')}\n\n"
        f"Diamond Cost : {diamond.get('diamondCost', 0)}\n\n"
        "CREDIT SCORE\n"
        f"• Score => {credit.get('creditScore', 0)}\n"
        "• From => N/A\n\n"
        "CLAN INFO\n"
        f"• Name => {clan.get('clanName', 'N/A')}\n"
        f"• ID => {clan.get('clanId', 'N/A')}\n"
        f"• Level => {clan.get('clanLevel', 'N/A')}\n\n"
        "LEADER INFO\n"
        f"• Nickname => {captain.get('nickname', 'N/A')}\n"
        f"• Level => {captain.get('level', 'N/A')}\n"
        f"• Likes => {captain.get('liked', 0):,}\n\n"
        "PET INFO\n"
        f"• Level => {pet.get('level', 'N/A')}\n"
        f"• EXP => {pet.get('exp', 0)}\n"
        f"• Pet ID => {pet.get('id', 'N/A')}\n"
        f"• Skill ID => {pet.get('selectedSkillId', 'N/A')}\n\n"
        "SOCIAL INFO\n"
        f"• Language => {social.get('language', 'N/A')}\n"
        f"• Signature =>\n{social.get('signature', 'No signature')}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "𝗝𝗔𝗚𝗪𝗔𝗥\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    return formatted_text

def fetch_player_image(uid: str):
    """جلب صورة اللاعب من API"""
    try:
        image_url = f"https://jagwar-outfit.vercel.app/outfit-image?uid={uid}&key=JOT-TEAM"
        response = requests.get(image_url, timeout=20)
        
        if response.status_code == 200:
            return True, response.content
        else:
            return False, None
    except Exception as e:
        logger.error(f"Error fetching player image: {e}")
        return False, None

def get_player_info_data(uid: str):
    """جلب معلومات اللاعب من API"""
    try:
        info_url = f"https://otman-info.vercel.app/player-info?uid={uid}"
        info_response = requests.get(info_url, timeout=15)
        
        if info_response.status_code != 200:
            return None, "Player not found"
        
        info_data = info_response.json()
        
        if not info_data or "basicInfo" not in info_data:
            return None, "Player not found"
        
        return info_data, None
    except Exception as e:
        return None, str(e)
# ==================== SPAM CORE FUNCTIONS ====================
def create_spam_room_packet(key, iv):
    """إنشاء حزمة فتح غرفة للسبام"""
    try:
        fields = {
            1: 2,
            2: {
                1: 1,
                2: 15,
                3: 5,
                4: "[FF0000]SPAM",
                5: "1",
                6: 12,
                7: 1,
                8: 1,
                9: 1,
                11: 1,
                12: 2,
                14: 36981056,
                15: {
                    1: "IDC3",
                    2: 126,
                    3: "ME"
                },
                16: "\u0001\u0003\u0004\u0007\t\n\u000b\u0012\u000f\u000e\u0016\u0019\u001a \u001d",
                18: 2368584,
                27: 1,
                34: "\u0000\u0001",
                40: "en",
                48: 1,
                49: {1: 21},
                50: {1: 36981056, 2: 2368584, 5: 2}
            }
        }
        
        packet = create_protobuf_packet(fields)
        packet = packet.hex()
        header_lenth = len(encrypt_packet(packet, key, iv))//2
        header_lenth_final = dec_to_hex(header_lenth)
        
        if len(header_lenth_final) == 2:
            final_packet = "0E15000000" + header_lenth_final + encrypt_packet(packet, key, iv)
        elif len(header_lenth_final) == 3:
            final_packet = "0E1500000" + header_lenth_final + encrypt_packet(packet, key, iv)
        elif len(header_lenth_final) == 4:
            final_packet = "0E150000" + header_lenth_final + encrypt_packet(packet, key, iv)
        elif len(header_lenth_final) == 5:
            final_packet = "0E15000" + header_lenth_final + encrypt_packet(packet, key, iv)
        
        return bytes.fromhex(final_packet)
    except Exception as e:
        logger.error(f"Error creating spam room packet: {e}")
        return None

def create_spam_invite_packet(key, iv, target_uid):
    """إنشاء حزمة دعوة للسبام"""
    try:
        fields = {
            1: 22,
            2: {
                1: int(target_uid)
            }
        }
        
        packet = create_protobuf_packet(fields)
        packet = packet.hex()
        header_lenth = len(encrypt_packet(packet, key, iv))//2
        header_lenth_final = dec_to_hex(header_lenth)
        
        if len(header_lenth_final) == 2:
            final_packet = "0E15000000" + header_lenth_final + encrypt_packet(packet, key, iv)
        elif len(header_lenth_final) == 3:
            final_packet = "0E1500000" + header_lenth_final + encrypt_packet(packet, key, iv)
        elif len(header_lenth_final) == 4:
            final_packet = "0E150000" + header_lenth_final + encrypt_packet(packet, key, iv)
        elif len(header_lenth_final) == 5:
            final_packet = "0E15000" + header_lenth_final + encrypt_packet(packet, key, iv)
        
        return bytes.fromhex(final_packet)
    except Exception as e:
        logger.error(f"Error creating spam invite packet: {e}")
        return None

def spam_attack_loop(target_uid, stop_event, requester_id, requester_name):
    """حلقة هجوم السبام الرئيسية"""
    while not stop_event.is_set():
        try:
            with command_lock:
                active_clients = [c for c in current_clients if c.is_connected and c.socket_client and c.key and c.iv]
            
            if not active_clients:
                stop_event.wait(2)
                continue
            
            for client in active_clients[:5]:
                if stop_event.is_set():
                    break
                    
                try:
                    room_packet = create_spam_room_packet(client.key, client.iv)
                    if room_packet:
                        client.socket_client.send(room_packet)
                        time.sleep(0.2)
                    
                    for _ in range(5):
                        if stop_event.is_set():
                            break
                        invite_packet = create_spam_invite_packet(client.key, client.iv, target_uid)
                        if invite_packet:
                            client.socket_client.send(invite_packet)
                            time.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Spam client error: {e}")
                    continue
                    
            stop_event.wait(0.5)
            
        except Exception as e:
            logger.error(f"Spam attack loop error: {e}")
            stop_event.wait(1)

def start_spam(target_uid, requester_id, requester_name, chat_id=None, user_message_id=None):
    """بدء هجوم السبام على هدف"""
    global _spam_tasks
    
    target_uid_str = str(target_uid)
    
    if target_uid_str in _spam_tasks:
        if chat_id and user_message_id:
            send_telegram_message(
                f"❌ Spam already active on ID: `{target_uid_str}`",
                chat_id=chat_id,
                reply_to_message_id=user_message_id
            )
        return False
    
    with _target_owners_lock:
        _target_owners[target_uid_str] = (requester_id, requester_name)
    
    stop_event = threading.Event()
    spam_thread = threading.Thread(
        target=spam_attack_loop,
        args=(target_uid_str, stop_event, requester_id, requester_name),
        daemon=True
    )
    spam_thread.start()
    
    _spam_tasks[target_uid_str] = (spam_thread, stop_event)
    
    logger.info(f"🎯 Spam started on {target_uid_str} by {requester_name}")
    
    if chat_id and user_message_id:
        send_telegram_message(
            f"✅ Spam attack started!\n"
            f"├─ Target ID: `{target_uid_str}`\n"
            f"├─ Started by: {requester_name}\n"
            f"└─ Status: 🚀 Running",
            chat_id=chat_id,
            reply_to_message_id=user_message_id
        )
    
    return True

def stop_spam(target_uid, requester_id, chat_id=None, user_message_id=None):
    """إيقاف هجوم السبام على هدف"""
    global _spam_tasks
    
    target_uid_str = str(target_uid)
    
    if target_uid_str not in _spam_tasks:
        if chat_id and user_message_id:
            send_telegram_message(
                f"❌ No spam attack found on ID: `{target_uid_str}`",
                chat_id=chat_id,
                reply_to_message_id=user_message_id
            )
        return False
    
    with _target_owners_lock:
        owner_id, owner_name = _target_owners.get(target_uid_str, (None, "unknown"))
    
    if str(requester_id) != str(owner_id) and str(requester_id) != ADMIN_ID:
        if chat_id and user_message_id:
            send_telegram_message(
                f"❌ Permission denied!\n"
                f"├─ This spam was started by: @{owner_name}\n"
                f"└─ Only the owner or admin can stop it.",
                chat_id=chat_id,
                reply_to_message_id=user_message_id
            )
        return False
    
    thread, stop_event = _spam_tasks.pop(target_uid_str)
    stop_event.set()
    
    if thread.is_alive():
        thread.join(timeout=3)
    
    with _target_owners_lock:
        if target_uid_str in _target_owners:
            del _target_owners[target_uid_str]
    
    logger.info(f"🛑 Spam stopped on {target_uid_str} by {requester_id}")
    
    if chat_id and user_message_id:
        send_telegram_message(
            f"✅ Spam attack stopped!\n"
            f"├─ Target ID: `{target_uid_str}`\n"
            f"└─ Status: ⏹️ Stopped",
            chat_id=chat_id,
            reply_to_message_id=user_message_id
        )
    
    return True

def get_active_spam_targets():
    """الحصول على قائمة الأهداف النشطة للسبام"""
    if not _spam_tasks:
        return []
    
    with _target_owners_lock:
        result = []
        for uid, (_, _) in _spam_tasks.items():
            owner_id, owner_name = _target_owners.get(uid, (None, "unknown"))
            result.append({
                'uid': uid,
                'owner_name': owner_name,
                'owner_id': owner_id
            })
    return result

def cleanup_threads():
    """إزالة الثريدات المنتهية"""
    global threads
    threads = [t for t in threads if t.is_alive()]
    logger.info(f"🧹 Cleaned threads: {len(threads)} active")

class HealthManager:
    def __init__(self):
        self.client_status = {}
    
    def check_client_health(self, client):
        """فحص صحة العميل"""
        client_id = client.client_id
        
        if not client.is_connected and not client.is_connecting:
            if client_id not in self.client_status:
                self.client_status[client_id] = {
                    'last_seen': time.time(),
                    'reconnect_count': 0
                }
            
            last_seen = self.client_status[client_id].get('last_seen', 0)
            if time.time() - last_seen > 60:
                logger.info(f"🔄 Health Manager: Reconnecting client #{client_id}")
                threading.Thread(target=client.reconnect, daemon=True).start()
                self.client_status[client_id]['last_seen'] = time.time()
                self.client_status[client_id]['reconnect_count'] += 1
    
    def monitor_all_clients(self, clients):
        """مراقبة كل العملاء"""
        while True:
            try:
                for client in clients:
                    self.check_client_health(client)
                
                time.sleep(10)
                
            except Exception as e:
                logger.error(f"Health Manager error: {e}")
                time.sleep(30)

class FF_CLIENT(threading.Thread):
    def __init__(self, account_data):
        super().__init__()
        self.name = account_data.get('name', 'Unknown')
        self.id = str(account_data.get('uid', ''))
        self.password = account_data.get('password', '')
        self.region = account_data.get('region', 'ME')
        self.key = None
        self.iv = None
        self.socket_client = None
        self.clients = None
        self.is_connected = False
        self.is_connecting = False
        self.client_id = len(current_clients) + 1
        self.last_restart_time = time.time()
        self.active_requests = 0
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 10
        self.session_id = hashlib.md5(f"{self.id}{self.password}{time.time()}".encode()).hexdigest()[:8]
        
        current_clients.append(self)
        
        logger.info(f"🕹️ Game bot #{self.client_id} ({self.name}) initialized, waiting for Telegram to be ready...")

    def safe_connect(self, func, *args, **kwargs):
        """توصيل آمن مع إعادة محاولة"""
        for attempt in range(3):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Client #{self.client_id}: Attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    time.sleep(2)
        return None

    def reconnect(self):
        """إعادة الاتصال التلقائي"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Client #{self.client_id}: Max reconnection attempts reached")
            return False
        
        self.reconnect_attempts += 1
        delay = self.reconnect_delay * self.reconnect_attempts
        logger.info(f"Client #{self.client_id}: Reconnecting in {delay} seconds (attempt {self.reconnect_attempts})")
        
        time.sleep(delay)
        
        try:
            if self.socket_client:
                try:
                    self.socket_client.close()
                except:
                    pass
            
            if self.clients:
                try:
                    self.clients.close()
                except:
                    pass
            
            self.is_connected = False
            time.sleep(2)
            
            success = self.get_tok()
            if success:
                self.reconnect_attempts = 0
                return True
            
        except Exception as e:
            logger.error(f"Client #{self.client_id}: Reconnection error: {e}")
        
        return False

    def create_ping_packet(self):
        """إنشاء باقة ping للتحقق"""
        try:
            fields = {
                1: 100,
                2: {
                    1: 1
                }
            }
            
            packet = create_protobuf_packet(fields)
            packet = packet.hex()
            header_lenth = len(encrypt_packet(packet, self.key, self.iv))//2
            header_lenth_final = dec_to_hex(header_lenth)
            
            if len(header_lenth_final) == 2:
                final_packet = "0515000000" + header_lenth_final + self.nmnmmmmn(packet)
            elif len(header_lenth_final) == 3:
                final_packet = "051500000" + header_lenth_final + self.nmnmmmmn(packet)
            elif len(header_lenth_final) == 4:
                final_packet = "05150000" + header_lenth_final + self.nmnmmmmn(packet)
            elif len(header_lenth_final) == 5:
                final_packet = "0515000" + header_lenth_final + self.nmnmmmmn(packet)
            
            return bytes.fromhex(final_packet)
        except:
            return None

    def health_check_loop(self):
        """حلقة فحص الصحة"""
        while self.is_connected:
            try:
                time.sleep(30)
                
                if self.socket_client:
                    try:
                        ping_packet = self.create_ping_packet()
                        if ping_packet:
                            self.socket_client.send(ping_packet)
                    except:
                        logger.error(f"Client #{self.client_id}: Health check failed, reconnecting...")
                        self.is_connected = False
                        self.reconnect()
                        break
                
            except Exception as e:
                logger.error(f"Client #{self.client_id}: Health check error: {e}")

    def parse_my_message(self, serialized_data):
        MajorLogRes = MajorLoginRes_pb2.MajorLoginRes()
        MajorLogRes.ParseFromString(serialized_data)
        
        timestamp = MajorLogRes.kts
        key = MajorLogRes.ak
        iv = MajorLogRes.aiv
        BASE64_TOKEN = MajorLogRes.token
        timestamp_obj = Timestamp()
        timestamp_obj.FromNanoseconds(timestamp)
        timestamp_seconds = timestamp_obj.seconds
        timestamp_nanos = timestamp_obj.nanos
        combined_timestamp = timestamp_seconds * 1_000_000_000 + timestamp_nanos
        return combined_timestamp, key, iv, BASE64_TOKEN

    def GET_PAYLOAD_BY_DATA(self, JWT_TOKEN, NEW_ACCESS_TOKEN, date):
        token_payload_base64 = JWT_TOKEN.split('.')[1]
        token_payload_base64 += '=' * ((4 - len(token_payload_base64) % 4) % 4)
        decoded_payload = base64.urlsafe_b64decode(token_payload_base64).decode('utf-8')
        decoded_payload = json.loads(decoded_payload)
        NEW_EXTERNAL_ID = decoded_payload['external_id']
        SIGNATURE_MD5 = decoded_payload['signature_md5']
        now = datetime.now()
        now =str(now)[:len(str(now))-7]
        formatted_time = date
        

        payload = bytes.fromhex("1a13323032352d31312d32362030313a35313a3238220966726565206669726528013a07312e3132302e314232416e64726f6964204f532039202f204150492d3238202850492f72656c2e636a772e32303232303531382e313134313333294a0848616e6468656c64520c4d544e2f537061636574656c5a045749464960800a68d00572033234307a2d7838362d3634205353453320535345342e3120535345342e32204156582041565832207c2032343030207c20348001e61e8a010f416472656e6f2028544d292036343092010d4f70656e474c20455320332e329a012b476f6f676c657c36323566373136662d393161372d343935622d396631362d303866653964336336353333a2010e3137362e32382e3133392e313835aa01026172b201203433303632343537393364653836646134323561353263616164663231656564ba010134c2010848616e6468656c64ca010d4f6e65506c7573204135303130ea014063363961653230386661643732373338623637346232383437623530613361316466613235643161313966616537343566633736616334613065343134633934f00101ca020c4d544e2f537061636574656cd2020457494649ca03203161633462383065636630343738613434323033626638666163363132306635e003b5ee02e8039a8002f003af13f80384078004a78f028804b5ee029004a78f029804b5ee02b00404c80401d2043d2f646174612f6170702f636f6d2e6474732e667265656669726574682d66705843537068495636644b43376a4c2d574f7952413d3d2f6c69622f61726de00401ea045f65363261623933353464386662356662303831646233333861636233333439317c2f646174612f6170702f636f6d2e6474732e667265656669726574682d66705843537068495636644b43376a4c2d574f7952413d3d2f626173652e61706bf00406f804018a050233329a050a32303139313139303236a80503b205094f70656e474c455332b805ff01c00504e005be7eea05093372645f7061727479f205704b717348543857393347646347335a6f7a454e6646775648746d377171316552554e6149444e67526f626f7a4942744c4f695943633459367a767670634943787a514632734f453463627974774c7334785a62526e70524d706d5752514b6d654f35766373386e51594268777148374bf805e7e4068806019006019a060134a2060134b2062213521146500e590349510e460900115843395f005b510f685b560a6107576d0f0366")
        
        payload = payload.replace(b"2026-01-14 12:19:02", str(now).encode())
        payload = payload.replace(b"c69ae208fad72738b674b2847b50a3a1dfa25d1a19fae745fc76ac4a0e414c94", NEW_ACCESS_TOKEN.encode("UTF-8"))
        payload = payload.replace(b"4306245793de86da425a52caadf21eed", NEW_EXTERNAL_ID.encode("UTF-8"))
        payload = payload.replace(b"1ac4b80ecf0478a44203bf8fac6120f5", SIGNATURE_MD5.encode("UTF-8"))
        
        PAYLOAD = payload.hex()
        PAYLOAD = encrypt_api(PAYLOAD)
        PAYLOAD = bytes.fromhex(PAYLOAD)
        whisper_ip, whisper_port, online_ip, online_port = self.GET_LOGIN_DATA(JWT_TOKEN, PAYLOAD)
        return whisper_ip, whisper_port, online_ip, online_port
    
    def GET_LOGIN_DATA(self, JWT_TOKEN, PAYLOAD):
        url = "https://clientbp.ggpolarbear.com/GetLoginData"
        headers = {
            'Expect': '100-continue',
            'Authorization': f'Bearer {JWT_TOKEN}',
            'X-Unity-Version': '2018.4.11f1',
            'X-GA': 'v1 1',
            'ReleaseVersion': 'OB53',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; G011A Build/PI)',
            'Host': 'clientbp.ggpolarbear.com',
            'Connection': 'close',
            'Accept-Encoding': 'gzip, deflate, br',
        }
        
        max_retries = 3
        attempt = 0

        while attempt < max_retries:
            try:
                response = requests.post(url, headers=headers, data=PAYLOAD, verify=False)
                response.raise_for_status()
                x = response.content.hex()
                json_result = get_available_room(x)
                parsed_data = json.loads(json_result)
                logger.info(f"📡 Client #{self.client_id}: Login data received")
                
                whisper_address = parsed_data['32']['data']
                online_address = parsed_data['14']['data']
                online_ip = online_address[:len(online_address) - 6]
                whisper_ip = whisper_address[:len(whisper_address) - 6]
                online_port = int(online_address[len(online_address) - 5:])
                whisper_port = int(whisper_address[len(whisper_address) - 5:])
                return whisper_ip, whisper_port, online_ip, online_port
            
            except requests.RequestException as e:
                logger.error(f"Client #{self.client_id}: Request failed: {e}. Attempt {attempt + 1} of {max_retries}. Retrying...")
                attempt += 1
                time.sleep(2)

        logger.error(f"Client #{self.client_id}: Failed to get login data after multiple attempts.")
        return None, None, None, None

    def guest_token(self, uid, password):
        url = "https://100067.connect.garena.com/oauth/guest/token/grant"
        headers = {
            "Host": "100067.connect.garena.com",
            "User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 10;en;EN;)",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "close",
        }
        data = {
            "uid": f"{uid}",
            "password": f"{password}",
            "response_type": "token",
            "client_type": "2",
            "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
            "client_id": "100067",
        }
        response = requests.post(url, headers=headers, data=data)
        data = response.json()
        NEW_ACCESS_TOKEN = data['access_token']
        NEW_OPEN_ID = data['open_id']
        OLD_ACCESS_TOKEN = "c69ae208fad72738b674b2847b50a3a1dfa25d1a19fae745fc76ac4a0e414c94"
        OLD_OPEN_ID = "4306245793de86da425a52caadf21eed"
        time.sleep(0.2)
        result = self.TOKEN_MAKER(OLD_ACCESS_TOKEN, NEW_ACCESS_TOKEN, OLD_OPEN_ID, NEW_OPEN_ID, uid)
        return result
        
    def TOKEN_MAKER(self, OLD_ACCESS_TOKEN, NEW_ACCESS_TOKEN, OLD_OPEN_ID, NEW_OPEN_ID, id):
        headers = {
            'X-Unity-Version': '2018.4.11f1',
            'ReleaseVersion': 'OB53',
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-GA': 'v1 1',
            'Content-Length': '928',
            'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 7.1.2; ASUS_Z01QD Build/QKQ1.190825.002)',
            'Host': 'loginbp.ggwhitehawk.com',
            'Connection': 'Keep-Alive',
            'Accept-Encoding': 'gzip'
        }
        
        
        data = bytes.fromhex('1a13323032352d31312d32362030313a35313a3238220966726565206669726528013a07312e3132332e314232416e64726f6964204f532039202f204150492d3238202850492f72656c2e636a772e32303232303531382e313134313333294a0848616e6468656c64520c4d544e2f537061636574656c5a045749464960800a68d00572033234307a2d7838362d3634205353453320535345342e3120535345342e32204156582041565832207c2032343030207c20348001e61e8a010f416472656e6f2028544d292036343092010d4f70656e474c20455320332e329a012b476f6f676c657c36323566373136662d393161372d343935622d396631362d303866653964336336353333a2010e3137362e32382e3133392e313835aa01026172b201203433303632343537393364653836646134323561353263616164663231656564ba010134c2010848616e6468656c64ca010d4f6e65506c7573204135303130ea014063363961653230386661643732373338623637346232383437623530613361316466613235643161313966616537343566633736616334613065343134633934f00101ca020c4d544e2f537061636574656cd2020457494649ca03203161633462383065636630343738613434323033626638666163363132306635e003b5ee02e8039a8002f003af13f80384078004a78f028804b5ee029004a78f029804b5ee02b00404c80401d2043d2f646174612f6170702f636f6d2e6474732e667265656669726574682d66705843537068495636644b43376a4c2d574f7952413d3d2f6c69622f61726de00401ea045f65363261623933353464386662356662303831646233333861636233333439317c2f646174612f6170702f636f6d2e6474732e667265656669726574682d66705843537068495636644b43376a4c2d574f7952413d3d2f626173652e61706bf00406f804018a050233329a050a32303139313139303236a80503b205094f70656e474c455332b805ff01c00504e005be7eea05093372645f7061727479f205704b717348543857393347646347335a6f7a454e6646775648746d377171316552554e6149444e67526f626f7a4942744c4f695943633459367a767670634943787a514632734f453463627974774c7334785a62526e70524d706d5752514b6d654f35766373386e51594268777148374bf805e7e4068806019006019a060134a2060134b2062213521146500e590349510e460900115843395f005b510f685b560a6107576d0f0366')
        
       
        data = data.replace(OLD_OPEN_ID.encode(), NEW_OPEN_ID.encode())
        data = data.replace(OLD_ACCESS_TOKEN.encode(), NEW_ACCESS_TOKEN.encode())
        
        hex = data.hex()
        d = encrypt_api(data.hex())
        Final_Payload = bytes.fromhex(d)
        URL = "https://loginbp.ggpolarbear.com/MajorLogin"

        try:
            RESPONSE = requests.post(URL, headers=headers, data=Final_Payload, verify=False)
            RESPONSE.raise_for_status()
            
            combined_timestamp, key, iv, BASE64_TOKEN = self.parse_my_message(RESPONSE.content)
            if RESPONSE.status_code == 200:
                if len(RESPONSE.content) < 10:
                    logger.error(f"Client #{self.client_id}: Empty response from server")
                    return False
                whisper_ip, whisper_port, online_ip, online_port = self.GET_PAYLOAD_BY_DATA(BASE64_TOKEN, NEW_ACCESS_TOKEN, 1)
                self.key = key
                self.iv = iv
                logger.info(f"✅ Client #{self.client_id}: Token obtained")
                return (BASE64_TOKEN, key, iv, combined_timestamp, whisper_ip, whisper_port, online_ip, online_port)
            else:
                logger.error(f"❌ Client #{self.client_id}: Failed to get token - Error code: {RESPONSE.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Client #{self.client_id}: Exception getting token: {str(e)}")
            return False

    def nmnmmmmn(self, data):
        if not self.key or not self.iv:
            return ""
        try:
            key = self.key if isinstance(self.key, bytes) else bytes.fromhex(self.key)
            iv = self.iv if isinstance(self.iv, bytes) else bytes.fromhex(self.iv)
            data = bytes.fromhex(data)
            cipher = AES.new(key, AES.MODE_CBC, iv)
            cipher_text = cipher.encrypt(pad(data, AES.block_size))
            return cipher_text.hex()
        except Exception as e:
            logger.error(f"Client #{self.client_id}: Error in nmnmmmmn: {e}")
            return ""

    def skwad_maker(self):
        fields = {
        1: 1,
        2: {
            2: "\u0001",
            3: 1,
            4: 1,
            5: "en",
            9: 1,
            11: 1,
            13: 1,
            14: {
            2: 5756,
            6: 11,
            8: "1.109.5",
            9: 3,
            10: 2
            },
        }
        }

        packet = create_protobuf_packet(fields)
        packet = packet.hex()
        header_lenth = len(encrypt_packet(packet, self.key, self.iv))//2
        header_lenth_final = dec_to_hex(header_lenth)
        if len(header_lenth_final) == 2:
            final_packet = "0515000000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 3:
            final_packet = "051500000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 4:
            final_packet = "05150000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 5:
            final_packet = "0515000" + header_lenth_final + self.nmnmmmmn(packet)
        return bytes.fromhex(final_packet)

    def changes(self, num):
        fields = {
        1: 17,
        2: {
            1: 11371687918,
            2: 1,
            3: int(num),
            4: 62,
            5: "\u001a",
            8: 5,
            13: 329
        }
        }

        packet = create_protobuf_packet(fields)
        packet = packet.hex()
        header_lenth = len(encrypt_packet(packet, self.key, self.iv))//2
        header_lenth_final = dec_to_hex(header_lenth)
        if len(header_lenth_final) == 2:
            final_packet = "0515000000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 3:
            final_packet = "051500000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 4:
            final_packet = "05150000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 5:
            final_packet = "0515000" + header_lenth_final + self.nmnmmmmn(packet)
        return bytes.fromhex(final_packet)

    def start_autooo(self):
        fields = {
        1: 9,
        2: {
            1: 11371687918
        }
        }
        packet = create_protobuf_packet(fields)
        packet = packet.hex()
        header_lenth = len(encrypt_packet(packet, self.key, self.iv))//2
        header_lenth_final = dec_to_hex(header_lenth)
        if len(header_lenth_final) == 2:
            final_packet = "0515000000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 3:
            final_packet = "051500000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 4:
            final_packet = "05150000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 5:
            final_packet = "0515000" + header_lenth_final + self.nmnmmmmn(packet)
        return bytes.fromhex(final_packet)

    def invite_skwad(self, idplayer):
        fields = {
        1: 2,
        2: {
            1: int(idplayer),
            2: "ME",
            4: 1
        }
        }
        packet = create_protobuf_packet(fields)
        packet = packet.hex()
        header_lenth = len(encrypt_packet(packet, self.key, self.iv))//2
        header_lenth_final = dec_to_hex(header_lenth)
        if len(header_lenth_final) == 2:
            final_packet = "0515000000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 3:
            final_packet = "051500000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 4:
            final_packet = "05150000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 5:
            final_packet = "0515000" + header_lenth_final + self.nmnmmmmn(packet)
        return bytes.fromhex(final_packet)

    def leave_s(self):
        fields = {
        1: 7,
        2: {
            1: 11371687918
        }
        }

        packet = create_protobuf_packet(fields)
        packet = packet.hex()
        header_lenth = len(encrypt_packet(packet, self.key, self.iv))//2
        header_lenth_final = dec_to_hex(header_lenth)
        if len(header_lenth_final) == 2:
            final_packet = "0515000000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 3:
            final_packet = "051500000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 4:
            final_packet = "05150000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 5:
            final_packet = "0515000" + header_lenth_final + self.nmnmmmmn(packet)
        return bytes.fromhex(final_packet)

    def accept_sq(self, hash, target, owner):
        fields = {
            1: 3,
            2: {
                1: int(owner),
                2: hash,
                3: int(target),
                5: 1,
                6: 0,
                7: 1
            }
        }

        packet = create_protobuf_packet(fields)
        packet = packet.hex()
        header_lenth = len(encrypt_packet(packet, self.key, self.iv))//2
        header_lenth_final = dec_to_hex(header_lenth)
        if len(header_lenth_final) == 2:
            final_packet = "0515000000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 3:
            final_packet = "051500000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 4:
            final_packet = "05150000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 5:
            final_packet = "0515000" + header_lenth_final + self.nmnmmmmn(packet)
        return bytes.fromhex(final_packet)

    def GenResponsMsg(self, msg, uid):
        fields = {
            1: 12,
            2: {
                1: int(uid),
                2: msg
            }
        }
        packet = create_protobuf_packet(fields)
        packet = packet.hex()
        header_lenth = len(encrypt_packet(packet, self.key, self.iv))//2
        header_lenth_final = dec_to_hex(header_lenth)
        if len(header_lenth_final) == 2:
            final_packet = "0515000000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 3:
            final_packet = "051500000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 4:
            final_packet = "05150000" + header_lenth_final + self.nmnmmmmn(packet)
        elif len(header_lenth_final) == 5:
            final_packet = "0515000" + header_lenth_final + self.nmnmmmmn(packet)
        return bytes.fromhex(final_packet)

    def check_restart_needed(self):
        """Check if account needs restart (every 3 minutes)"""
        current_time = time.time()
        if current_time - self.last_restart_time > ACCOUNT_RESTART_INTERVAL:
            logger.info(f"🔄 Client #{self.client_id}: Restarting connection after 3 minutes")
            self.last_restart_time = current_time
            self.restart_connection()
            
    def restart_connection(self):
        """Restart the game connection"""
        try:
            if self.socket_client:
                self.socket_client.close()
            if self.clients:
                self.clients.close()
            
            self.is_connected = False
            logger.info(f"🔄 Client #{self.client_id}: Restarting connection...")
            self.get_tok()
        except Exception as e:
            logger.error(f"❌ Client #{self.client_id}: Error restarting connection: {e}")

    
    def execute_lag_command(self, team_code, duration=1, chat_id=None, user_message_id=None):
        """Execute lag command - نظام تعليق الفريق"""
        try:
            self.active_requests += 1
            active_requests_per_account[self.id] = active_requests_per_account.get(self.id, 0) + 1
            
            if not self.is_connected or not self.socket_client:
                logger.error(f"Client #{self.client_id}: Not connected, cannot execute lag")
                return False

            
            if duration == 1:
                total_requests = 1000
                repeat_count = 1
            elif duration == 2:
                total_requests = 2000
                repeat_count = 2
            elif duration >= 3:
                total_requests = 3000
                repeat_count = 3
            else:
                total_requests = 1000
                repeat_count = 1
                
            logger.info(f"🚀 Client #{self.client_id}: Starting lag attack on team {team_code}")
            logger.info(f"├─ Duration: {duration}")
            logger.info(f"├─ Batches: {repeat_count}")
            logger.info(f"└─ Total requests: {total_requests}")
            
           
            if chat_id and user_message_id:
                start_msg = send_telegram_message(
                    f"⏸️ Starting team suspension\n"
                    f"├─ Target: {team_code}\n"
                    f"├─ Duration level: {duration}\n"
                    f"├─ Total batches: {repeat_count}\n"
                    f"└─ Total requests: {total_requests}",
                    chat_id=chat_id,
                    reply_to_message_id=user_message_id
                )
                start_msg_id = start_msg.get('result', {}).get('message_id') if start_msg else None
            
           
            request_counter = 0
            for batch in range(repeat_count):
                batch_num = batch + 1
                
               
                if repeat_count > 1 and chat_id and user_message_id:
                    batch_msg = send_telegram_message(
                        f"🔄 Suspension batch {batch_num} of {repeat_count}...",
                        chat_id=chat_id,
                        reply_to_message_id=user_message_id
                    )
                    batch_msg_id = batch_msg.get('result', {}).get('message_id') if batch_msg else None
                
                logger.info(f"Client #{self.client_id}: Starting lag batch {batch_num}/{repeat_count}")
                
                
                for request_num in range(1000):
                    try:
                        join_teamcode(self.socket_client, team_code, self.key, self.iv)
                        time.sleep(0.001)
                        leave_packet = self.leave_s()
                        self.socket_client.send(leave_packet)
                        time.sleep(0.0001)
                        request_counter += 1
                        
                    except Exception as e:
                        logger.error(f"Client #{self.client_id}: Error in lag request {request_counter}: {e}")
                        continue
                
                
                if repeat_count > 1 and batch_num < repeat_count:
                    time.sleep(0.1)
                
             
                if repeat_count > 1 and chat_id and batch_msg_id:
                    try:
                        delete_telegram_message(chat_id, batch_msg_id)
                    except:
                        pass
            

            if chat_id and user_message_id:
                send_telegram_message(
                    f"✅ Team suspension completed!\n"
                    f"├─ Target: {team_code}\n"
                    f"├─ Duration level: {duration}\n"
                    f"├─ Total batches: {repeat_count}\n"
                    f"└─ Total requests: {request_counter}",
                    chat_id=chat_id,
                    reply_to_message_id=user_message_id
                )
            
            logger.info(f"✅ Client #{self.client_id}: Lag attack completed!")
            logger.info(f"├─ Team: {team_code}")
            logger.info(f"├─ Duration: {duration}")
            logger.info(f"└─ Requests sent: {request_counter}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Client #{self.client_id}: Error in execute_lag_command: {e}")
            return False
        finally:
            self.active_requests -= 1
            active_requests_per_account[self.id] = max(0, active_requests_per_account.get(self.id, 0) - 1)

    
    def execute_attack_command(self, team_code, chat_id=None, user_message_id=None):
        """Execute attack command (forced start)"""
        try:
            self.active_requests += 1
            active_requests_per_account[self.id] = active_requests_per_account.get(self.id, 0) + 1
            
            if not self.is_connected or not self.socket_client:
                logger.error(f"Client #{self.client_id}: Not connected, cannot execute attack")
                return False

            start_packet = self.start_autooo()
            leave_packet = self.leave_s()

            logger.info(f"🚀 Client #{self.client_id}: Starting forced attack on team {team_code}")
            
            attack_start_time = time.time()
            while time.time() - attack_start_time < 45:
                join_teamcode(self.socket_client, team_code, self.key, self.iv)
                self.socket_client.send(start_packet)
                self.socket_client.send(leave_packet)
                time.sleep(0.15)

            logger.info(f"✅ Client #{self.client_id}: Forced attack completed on team {team_code}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Client #{self.client_id}: Error in execute_attack_command: {e}")
            return False
        finally:
            self.active_requests -= 1
            active_requests_per_account[self.id] = max(0, active_requests_per_account.get(self.id, 0) - 1)

    
    def execute_invite_command(self, player_id, squad_type, chat_id=None, user_message_id=None):
        """Execute invite command in game"""
        try:
            self.active_requests += 1
            active_requests_per_account[self.id] = active_requests_per_account.get(self.id, 0) + 1
            
            if not self.is_connected or not self.socket_client:
                logger.error(f"Client #{self.client_id}: Not connected, cannot execute invite")
                return False

            numsc = int(squad_type) - 1
            
            packetmaker = self.skwad_maker()
            self.socket_client.send(packetmaker)
            sleep(0.5)
            
            packetfinal = self.changes(int(numsc))
            self.socket_client.send(packetfinal)
            sleep(0.5)
            
            invite_packet = self.invite_skwad(player_id)
            self.socket_client.send(invite_packet)
            
            sleep(5)
            
            leave_packet = self.leave_s()
            self.socket_client.send(leave_packet)
            sleep(0.5)
            
            solo_packet = self.changes(1)
            self.socket_client.send(solo_packet)
            
            logger.info(f"✅ Client #{self.client_id}: Invite sent to player {player_id} (squad: {squad_type})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Client #{self.client_id}: Error in execute_invite_command: {e}")
            return False
        finally:
            self.active_requests -= 1
            active_requests_per_account[self.id] = max(0, active_requests_per_account.get(self.id, 0) - 1)

    def sockf1(self, tok, online_ip, online_port, packet, key, iv):
        global sent_inv, tempid, start_par, pleaseaccept, tempdata1, nameinv, idinv
        global senthi, statusinfo, tempdata, data22, leaveee, isroom, isroom2, game_ready
        
        try:
            self.socket_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            online_port = int(online_port)

            self.socket_client.connect((online_ip, online_port))
            self.is_connected = True
            game_ready = True
            logger.info(f"🎮 Client #{self.client_id}: Connected to game server {online_ip}:{online_port}")
            
            update_connection_time()
            self.socket_client.send(bytes.fromhex(tok))
            
            while True:
                try:
                    self.check_restart_needed()
                    
                    data2 = self.socket_client.recv(9999)
                    if not data2:
                        self.is_connected = False
                        game_ready = False
                        logger.error(f"❌ Client #{self.client_id}: Game connection closed by server")
                        break
                    
                    update_connection_time()
                    
                    if "0500" in data2.hex()[0:4]:
                        accept_packet = f'08{data2.hex().split("08", 1)[1]}'
                        kk = get_available_room(accept_packet)
                        parsed_data = json.loads(kk)
                        fark = parsed_data.get("4", {}).get("data", None)
                        if fark is not None:
                            if fark == 18:
                                if sent_inv:
                                    accept_packet = f'08{data2.hex().split("08", 1)[1]}'
                                    aa = gethashteam(accept_packet)
                                    ownerid = getownteam(accept_packet)
                                    ss = self.accept_sq(aa, tempid, int(ownerid))
                                    self.socket_client.send(ss)
                                    sleep(1)
                                    startauto = self.start_autooo()
                                    self.socket_client.send(startauto)
                                    start_par = False
                                    sent_inv = False

                    if "0600" in data2.hex()[0:4] and len(data2.hex()) > 700:
                            accept_packet = f'08{data2.hex().split("08", 1)[1]}'
                            kk = get_available_room(accept_packet)
                            parsed_data = json.loads(kk)
                            idinv = parsed_data["5"]["data"]["1"]["data"]
                            nameinv = parsed_data["5"]["data"]["3"]["data"]
                            senthi = True
                            
                except Exception as e:
                    logger.error(f"Client #{self.client_id}: Error in sockf1 recv: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"❌ Client #{self.client_id}: Error connecting to game server: {e}")
            game_ready = False
            self.is_connected = False

    def connect(self, tok, packet, key, iv, whisper_ip, whisper_port, online_ip, online_port):
        global clients, sent_inv, tempid, leaveee, start_par, nameinv, idinv
        global senthi, statusinfo, tempdata, pleaseaccept, tempdata1, data22, game_ready
        
        try:
            self.clients = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.clients.connect((whisper_ip, whisper_port))
            self.clients.send(bytes.fromhex(tok))
            logger.info(f"🔗 Client #{self.client_id}: Connected to whisper server {whisper_ip}:{whisper_port}")
            
            thread = threading.Thread(
                target=self.sockf1, args=(tok, online_ip, online_port, "anything", key, iv)
            )
            threads.append(thread)
            thread.start()

            while True:
                try:
                    self.check_restart_needed()
                    
                    data = self.clients.recv(9999)

                    if data == b"":
                        self.is_connected = False
                        game_ready = False
                        logger.error(f"❌ Client #{self.client_id}: Whisper connection closed")
                        break

                    if senthi == True:
                        self.clients.send(
                            self.GenResponsMsg(
                                """[C][B][1E90FF]╔══════════════════════════╗
[FFFFFF]Hello! Thanks for adding me.
[FFFFFF]To see available commands,
[FFFFFF]send any message or emoji.
[1E90FF]╠══════════════════════════╣
[FFFFFF] Auto-restart on disconnect
[FFFFFF] ..............................
[FFD700]Telegram:@AlliFF_BOT
[1E90FF]╚══════════════════════════╝""", idinv
                            )
                        )
                        senthi = False

                    if "1200" in data.hex()[0:4]:
                        json_result = get_available_room(data.hex()[10:])
                        parsed_data = json.loads(json_result)
                        try:
                            uid = parsed_data["5"]["data"]["1"]["data"]
                        except KeyError:
                            uid = None
                            
                except Exception as e:
                    logger.error(f"Client #{self.client_id}: Error in connect loop: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"❌ Client #{self.client_id}: Error connecting to whisper server: {e}")
            game_ready = False

    def get_tok(self):
        global g_token, game_ready
        
        logger.info(f"🔐 Client #{self.client_id}: Starting connection ({self.name})...")
        self.is_connecting = True
        
        try:
            result = self.safe_connect(self.guest_token, self.id, self.password)
            if not result:
                logger.error(f"❌ Client #{self.client_id}: Complete failure getting token")
                self.is_connecting = False
                return False
                
            token, key, iv, Timestamp, whisper_ip, whisper_port, online_ip, online_port = result
            g_token = token
            
            logger.info(f"✅ Client #{self.client_id}: Game credentials obtained")
            
            try:
                decoded = jwt.decode(token, options={"verify_signature": False})
                account_id = decoded.get('account_id')
                encoded_acc = hex(account_id)[2:]
                hex_value = dec_to_hex(Timestamp)
                time_hex = hex_value
                BASE64_TOKEN_ = token.encode().hex()
            except Exception as e:
                logger.error(f"Client #{self.client_id}: Error processing token: {e}")
                return False

            try:
                head = hex(len(encrypt_packet(BASE64_TOKEN_, key, iv)) // 2)[2:]
                length = len(encoded_acc)
                zeros = '00000000'

                if length == 9:
                    zeros = '0000000'
                elif length == 8:
                    zeros = '00000000'
                elif length == 10:
                    zeros = '000000'
                elif length == 7:
                    zeros = '000000000'
                else:
                    logger.error(f'Client #{self.client_id}: Unexpected length encountered')
                head = f'0115{zeros}{encoded_acc}{time_hex}00000{head}'
                final_token = head + encrypt_packet(BASE64_TOKEN_, key, iv)
            except Exception as e:
                logger.error(f"Client #{self.client_id}: Error constructing final token: {e}")
                return None, None
                
            token = final_token
            self.connect(token, 'anything', key, iv, whisper_ip, whisper_port, online_ip, online_port)
            
            self.is_connected = True
            game_ready = True
            self.is_connecting = False
            self.reconnect_attempts = 0
            
            threading.Thread(target=self.health_check_loop, daemon=True).start()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Client #{self.client_id}: Final connection error: {str(e)}")
            self.is_connecting = False
            return False
    
    def run(self):
        """Override run method to start game bot"""
        global game_ready
        
        while not telegram_ready:
            logger.info(f"⏳ Client #{self.client_id}: Waiting for Telegram bot to be ready...")
            time.sleep(2)
        
        logger.info(f"🚀 Client #{self.client_id}: Starting connection...")
        self.get_tok()


class CommandProcessor(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.active_commands = 0
        
    def run(self):
        """معالجة الطلبات من الطابور"""
        while True:
            try:
                if self.active_commands < MAX_CONCURRENT_REQUESTS:
                    try:
                        command = command_queue.get(timeout=1)
                        self.active_commands += 1
                        threading.Thread(
                            target=self.process_command,
                            args=(command,),
                            daemon=True
                        ).start()
                        
                    except queue.Empty:
                        pass
                
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"❌ Error in command processor: {e}")
                time.sleep(1)
    
    def process_command(self, command):
        """معالجة أمر واحد"""
        try:
            chat_id = command.get('chat_id')
            user_message_id = command.get('user_message_id')
            
            available_client = None
            min_requests = float('inf')
            
            for client in current_clients:
                if client.is_connected:
                    client_requests = active_requests_per_account.get(client.id, 0)
                    if client_requests < min_requests:
                        min_requests = client_requests
                        available_client = client
            
            if not available_client and command['type'] not in ['info', 'add_friend', 'remove_friend', 'my_friends']:
                send_telegram_message(
                    "❌ No connected game clients available",
                    chat_id=chat_id,
                    reply_to_message_id=user_message_id
                )
                return
            
            processing_msg = send_telegram_message(
                "🔄 Processing your request...",
                chat_id=chat_id,
                reply_to_message_id=user_message_id
            )
            
            squad_names = {
                "2": "2 Players",
                "3": "3 Players",  
                "4": "4 Players",
                "5": "5 Players",
                "6": "6 Players"
            }
            
            if command['type'] == 'invite':
                player_id = command['player_id']
                squad_type = command['squad_type']
                squad_name = squad_names.get(squad_type, f"{squad_type} Players")
                
                edit_telegram_message(
                    chat_id,
                    processing_msg['result']['message_id'],
                    f"🔄 Processing {squad_name} Squad Invite\n"
                    f"├─ Player ID: `{player_id}`\n"
                    f"└─ Status: Sending invitation..."
                )
                
                success = available_client.execute_invite_command(player_id, squad_type, chat_id, user_message_id)
                
                if processing_msg and 'result' in processing_msg:
                    delete_telegram_message(chat_id, processing_msg['result']['message_id'])
                
                if success:
                    send_telegram_message(
                        f"✅ Squad Invite Sent Successfully\n"
                        f"├─ Type: {squad_name}\n"
                        f"├─ To Player: <code>{player_id}</code>\n"
                        f"└─ Status: ✅ Delivered",
                        chat_id=chat_id,
                        reply_to_message_id=user_message_id
                    )
                else:
                    send_telegram_message(
                        f"❌ Failed to Send Invite\n"
                        f"├─ Type: {squad_name}\n"
                        f"├─ To Player: <code>{player_id}</code>\n"
                        f"└─ Status: ❌ Connection error",
                        chat_id=chat_id,
                        reply_to_message_id=user_message_id
                    )
            
            elif command['type'] == 'attack':
                team_code = command['team_code']
                
                edit_telegram_message(
                    chat_id,
                    processing_msg['result']['message_id'],
                    f"⚡ Initiating Attack Protocol\n"
                    f"├─ Target: `{team_code}`\n"
                    f"└─ Status: Loading attack module..."
                )
                
                success = available_client.execute_attack_command(team_code, chat_id, user_message_id)
                
                if processing_msg and 'result' in processing_msg:
                    delete_telegram_message(chat_id, processing_msg['result']['message_id'])
                
                if success:
                    send_telegram_message(
                        f"🎯 Attack Completed Successfully\n"
                        f"├─ Target: <code>{team_code}</code>\n"
                        f"├─ Duration: 45 seconds\n"
                        f"└─ Status: ✅ Forced start executed",
                        chat_id=chat_id,
                        reply_to_message_id=user_message_id
                    )
                else:
                    send_telegram_message(
                        f"❌ Attack Failed\n"
                        f"├─ Target: <code>{team_code}</code>\n"
                        f"└─ Status: ❌ System error",
                        chat_id=chat_id,
                        reply_to_message_id=user_message_id
                    )
            
            elif command['type'] == 'lag':
                team_code = command['team_code']
                duration = command.get('duration', 1)
                
                edit_telegram_message(
                    chat_id,
                    processing_msg['result']['message_id'],
                    f"⏸️ Initializing Team Suspension\n"
                    f"├─ Team Code: `{team_code}`\n"
                    f"├─ Duration: {duration} minute(s)\n"
                    f"└─ Status: Loading suspension module..."
                )
                
                success = available_client.execute_lag_command(team_code, duration, chat_id, user_message_id)
                
                if processing_msg and 'result' in processing_msg:
                    delete_telegram_message(chat_id, processing_msg['result']['message_id'])
                
                if success:
                    send_telegram_message(
                        f"⏸️ Team Suspended Successfully\n"
                        f"├─ Target: <code>{team_code}</code>\n"
                        f"├─ Duration: {duration} minute(s)\n"
                        f"└─ Status: ✅ Team suspended",
                        chat_id=chat_id,
                        reply_to_message_id=user_message_id
                    )
                else:
                    send_telegram_message(
                        f"❌ Team Suspension Failed\n"
                        f"├─ Target: <code>{team_code}</code>\n"
                        f"└─ Status: ❌ System error",
                        chat_id=chat_id,
                        reply_to_message_id=user_message_id
                    )
            
            # ==================== SPAM COMMAND HANDLING ====================
            elif command['type'] == 'spam':
                target_uid = command['target_uid']
                
                edit_telegram_message(
                    chat_id,
                    processing_msg['result']['message_id'],
                    f"🎯 Initializing Spam Attack\n"
                    f"├─ Target ID: `{target_uid}`\n"
                    f"├─ Status: Loading spam module..."
                )
                
                requester_name = command.get('requester_name', 'user')
                success = start_spam(target_uid, command['user_id'], requester_name, chat_id, user_message_id)
                
                if processing_msg and 'result' in processing_msg:
                    delete_telegram_message(chat_id, processing_msg['result']['message_id'])
                
                if not success and command.get('chat_id'):
                    pass
                    
            elif command['type'] == 'stop_spam':
                target_uid = command['target_uid']
                
                edit_telegram_message(
                    chat_id,
                    processing_msg['result']['message_id'],
                    f"⏹️ Stopping Spam Attack\n"
                    f"├─ Target ID: `{target_uid}`\n"
                    f"└─ Status: Stopping..."
                )
                
                success = stop_spam(target_uid, command['user_id'], chat_id, user_message_id)
                
                if processing_msg and 'result' in processing_msg:
                    delete_telegram_message(chat_id, processing_msg['result']['message_id'])
                    
            elif command['type'] == 'spam_list':
                active_targets = get_active_spam_targets()
                
                if processing_msg and 'result' in processing_msg:
                    delete_telegram_message(chat_id, processing_msg['result']['message_id'])
                
                if active_targets:
                    lines = [f"🎯 Active Spam Targets:"]
                    for target in active_targets:
                        lines.append(f"├─ `{target['uid']}` (by @{target['owner_name']})")
                    send_telegram_message(
                        "\n".join(lines),
                        chat_id=chat_id,
                        reply_to_message_id=user_message_id
                    )
                else:
                    send_telegram_message(
                        "⚠️ No active spam targets",
                        chat_id=chat_id,
                        reply_to_message_id=user_message_id
                    )
            
            # ==================== INFO COMMAND HANDLING ====================
            elif command['type'] == 'info':
                target_uid = command['target_uid']
                
                edit_telegram_message(
                    chat_id,
                    processing_msg['result']['message_id'],
                    f"🔍 Fetching player info...\n"
                    f"├─ UID: `{target_uid}`\n"
                    f"└─ Status: Loading..."
                )
                
                info_data, error = get_player_info_data(target_uid)
                
                if not info_data:
                    if processing_msg and 'result' in processing_msg:
                        delete_telegram_message(chat_id, processing_msg['result']['message_id'])
                    send_telegram_message(
                        f"❌ {error}\nUID: `{target_uid}`",
                        chat_id=chat_id,
                        reply_to_message_id=user_message_id
                    )
                    return
                
                caption = format_player_info(info_data)
                
                image_success, image_bytes = fetch_player_image(target_uid)
                
                if processing_msg and 'result' in processing_msg:
                    delete_telegram_message(chat_id, processing_msg['result']['message_id'])
                
                if image_success and image_bytes:
                    files = {'photo': (f"{target_uid}.png", image_bytes, 'image/png')}
                    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
                    data = {
                        "chat_id": chat_id,
                        "caption": caption,
                        "parse_mode": "HTML",
                        "reply_to_message_id": user_message_id
                    }
                    try:
                        response = requests.post(url, data=data, files=files, timeout=30)
                        if response.status_code != 200:
                            send_telegram_message(
                                caption,
                                chat_id=chat_id,
                                reply_to_message_id=user_message_id
                            )
                    except:
                        send_telegram_message(
                            caption,
                            chat_id=chat_id,
                            reply_to_message_id=user_message_id
                        )
                else:
                    send_telegram_message(
                        caption,
                        chat_id=chat_id,
                        reply_to_message_id=user_message_id
                    )
            
            # ==================== FRIEND SYSTEM COMMANDS (للمستخدمين فقط) ====================
            elif command['type'] == 'add_friend':
                target_uid = command['target_uid']
                user_tele_id = str(command['user_id'])
                
                # التحقق من الحد الأقصى (100 صديق)
                current_count = _get_friends_count()
                if current_count >= 100:
                    if processing_msg and 'result' in processing_msg:
                        delete_telegram_message(chat_id, processing_msg['result']['message_id'])
                    send_telegram_message(
                        f"❌ Maximum friends limit reached (100 friends).\nPlease wait for some to expire before adding more.",
                        chat_id=chat_id,
                        reply_to_message_id=user_message_id
                    )
                    return
                
                # التحقق من الحد اليومي للمستخدم (2 إضافات في اليوم)
                now = datetime.now()
                today_str = now.strftime("%Y-%m-%d")
                
                if user_tele_id not in _friends_daily_usage:
                    _friends_daily_usage[user_tele_id] = {"count": 0, "date": today_str}
                elif _friends_daily_usage[user_tele_id]["date"] != today_str:
                    _friends_daily_usage[user_tele_id] = {"count": 0, "date": today_str}
                
                if _friends_daily_usage[user_tele_id]["count"] >= 2:
                    if processing_msg and 'result' in processing_msg:
                        delete_telegram_message(chat_id, processing_msg['result']['message_id'])
                    send_telegram_message(
                        f"⚠️ Daily limit reached (2 friends per day).\nPlease try again tomorrow.",
                        chat_id=chat_id,
                        reply_to_message_id=user_message_id
                    )
                    return
                
                # التحقق من أن اللاعب غير مضاف مسبقاً
                if target_uid in _friends_data:
                    if processing_msg and 'result' in processing_msg:
                        delete_telegram_message(chat_id, processing_msg['result']['message_id'])
                    send_telegram_message(
                        f"❌ Player `{target_uid}` is already in your friends list.",
                        chat_id=chat_id,
                        reply_to_message_id=user_message_id
                    )
                    return
                
                edit_telegram_message(
                    chat_id,
                    processing_msg['result']['message_id'],
                    f"👤 Sending friend request to `{target_uid}`...\n└─ Status: Please wait..."
                )
                
                # إرسال طلب الصداقة - استخدام الدالة المساعدة get_jwt_token()
                jwt_token = get_jwt_token()
                
                success, message = _send_friend_request(target_uid, jwt_token)
                
                if success:
                    # جلب معلومات اللاعب
                    name, region, level = _get_player_info(target_uid)
                    
                    # إضافة إلى القائمة (مدة 4 ساعات = 4*3600 ثانية)
                    _friends_data[target_uid] = {
                        "name": name,
                        "region": region,
                        "level": level,
                        "added_by": user_tele_id,
                        "added_date": now.strftime("%Y-%m-%d %H:%M:%S"),
                        "expiry": time.time() + (4 * 3600)
                    }
                    _save_friends_data()
                    
                    # تحديث الاستخدام اليومي
                    _friends_daily_usage[user_tele_id]["count"] += 1
                    
                    if processing_msg and 'result' in processing_msg:
                        delete_telegram_message(chat_id, processing_msg['result']['message_id'])
                    
                    send_telegram_message(
                        f"✅ Friend request sent successfully!\n\n"
                        f"👤 Name: {html.unescape(name)}\n"
                        f"🆔 UID: {target_uid}\n"
                        f"🌍 Region: {region}\n"
                        f"⭐ Level: {level}\n"
                        f"⏳ Duration: 4 hours\n\n"
                        f"💡 Please accept the friend request in game.",
                        chat_id=chat_id,
                        reply_to_message_id=user_message_id
                    )
                else:
                    if processing_msg and 'result' in processing_msg:
                        delete_telegram_message(chat_id, processing_msg['result']['message_id'])
                    send_telegram_message(
                        f"❌ Failed to send friend request.\n"
                        f"📩 Error: {message}\n\n"
                        f"💡 Possible reasons:\n"
                        f"├─ Player not found\n"
                        f"├─ Different region/server\n"
                        f"└─ Server error, please try again",
                        chat_id=chat_id,
                        reply_to_message_id=user_message_id
                    )
            
            elif command['type'] == 'remove_friend':
                target_uid = command['target_uid']
                user_tele_id = str(command['user_id'])
                
                if target_uid not in _friends_data:
                    if processing_msg and 'result' in processing_msg:
                        delete_telegram_message(chat_id, processing_msg['result']['message_id'])
                    send_telegram_message(
                        f"❌ Player `{target_uid}` not found in your friends list.",
                        chat_id=chat_id,
                        reply_to_message_id=user_message_id
                    )
                    return
                
                # التحقق من ملكية اللاعب (الشخص الذي أضافه فقط يمكنه حذفه)
                if _friends_data[target_uid].get("added_by") != user_tele_id:
                    if processing_msg and 'result' in processing_msg:
                        delete_telegram_message(chat_id, processing_msg['result']['message_id'])
                    send_telegram_message(
                        f"❌ You are not allowed to remove this friend.\n"
                        f"└─ Only the person who added it can remove it.",
                        chat_id=chat_id,
                        reply_to_message_id=user_message_id
                    )
                    return
                
                edit_telegram_message(
                    chat_id,
                    processing_msg['result']['message_id'],
                    f"🗑️ Removing friend `{target_uid}`...\n└─ Status: Please wait..."
                )
                
                # حذف الصديق - استخدام الدالة المساعدة get_jwt_token()
                jwt_token = get_jwt_token()
                
                success, message = _remove_friend(target_uid, jwt_token)
                
                if success:
                    name = _friends_data[target_uid].get("name", "Unknown")
                    del _friends_data[target_uid]
                    _save_friends_data()
                    
                    if processing_msg and 'result' in processing_msg:
                        delete_telegram_message(chat_id, processing_msg['result']['message_id'])
                    
                    send_telegram_message(
                        f"✅ Friend removed successfully!\n\n"
                        f"👤 Name: {html.unescape(name)}\n"
                        f"🆔 UID: {target_uid}",
                        chat_id=chat_id,
                        reply_to_message_id=user_message_id
                    )
                else:
                    if processing_msg and 'result' in processing_msg:
                        delete_telegram_message(chat_id, processing_msg['result']['message_id'])
                    send_telegram_message(
                        f"❌ Failed to remove friend.\n"
                        f"📩 Error: {message}",
                        chat_id=chat_id,
                        reply_to_message_id=user_message_id
                    )
            
            elif command['type'] == 'my_friends':
                user_tele_id = str(command['user_id'])
                
                # تصفية الأصدقاء التي أضافها هذا المستخدم فقط
                my_friends = {uid: data for uid, data in _friends_data.items() 
                             if data.get("added_by") == user_tele_id}
                
                if not my_friends:
                    if processing_msg and 'result' in processing_msg:
                        delete_telegram_message(chat_id, processing_msg['result']['message_id'])
                    send_telegram_message(
                        f"📭 You have no friends added.\n\n"
                        f"💡 Use `/add [UID]` to add friends.\n"
                        f"⏳ Each friend lasts for 4 hours.\n"
                        f"📊 Max: 100 friends total, 2 per day.",
                        chat_id=chat_id,
                        reply_to_message_id=user_message_id
                    )
                    return
                
                lines = [f"📋 Your Friends List ({len(my_friends)}/100):\n"]
                for uid, data in my_friends.items():
                    remaining = _format_remaining_time(data.get("expiry", 0))
                    name = html.unescape(data.get("name", "Unknown"))
                    lines.append(f"├─ 👤 {name}\n├─ 🆔 `{uid}`\n├─ ⏳ {remaining}\n│")
                
                lines.append(f"\n💡 Tips:\n"
                            f"├─ `/remove [UID]` ➝ Remove a friend\n"
                            f"├─ Each friend lasts 4 hours\n"
                            f"└─ Max 2 friends per day")
                
                final_text = "\n".join(lines)
                
                if processing_msg and 'result' in processing_msg:
                    delete_telegram_message(chat_id, processing_msg['result']['message_id'])
                
                if len(final_text) > 4000:
                    for i in range(0, len(final_text), 4000):
                        send_telegram_message(
                            final_text[i:i+4000],
                            chat_id=chat_id,
                            reply_to_message_id=user_message_id
                        )
                else:
                    send_telegram_message(
                        final_text,
                        chat_id=chat_id,
                        reply_to_message_id=user_message_id
                    )
                    
        except Exception as e:
            logger.error(f"❌ Error processing command: {e}")
        finally:
            self.active_commands -= 1

def add_command_to_queue(command_type, player_id=None, squad_type=None, team_code=None, duration=1, target_uid=None, chat_id=None, user_message_id=None, user_id=None, requester_name=None):
    """إضافة أمر إلى طابور التنفيذ"""
    command = {
        'type': command_type,
        'player_id': player_id,
        'squad_type': squad_type,
        'team_code': team_code,
        'duration': duration,
        'target_uid': target_uid,
        'chat_id': chat_id,
        'user_message_id': user_message_id,
        'user_id': user_id,
        'requester_name': requester_name,
        'timestamp': time.time()
    }
    command_queue.put(command)
    return True

def execute_telegram_command(command, player_id=None, squad_type=None, team_code=None, duration=1, target_uid=None, chat_id=None, user_id=None, user_message_id=None):
    """Execute commands from Telegram"""
    try:
        if str(chat_id).startswith('-') is False:
            if str(user_id) == ADMIN_ID:
                pass
            else:
                send_telegram_message("🙂🖕", chat_id=user_id, no_signature=True, reply_to_message_id=user_message_id)
                return ""
            return ""

        if not is_group_active(chat_id):
            send_telegram_message(
                "⚠️ Bot Activation Expired\n"
                "This group's bot activation has expired.\n"
                "Please contact @AlliFF_BOT for reactivation.", 
                chat_id=chat_id,
                reply_to_message_id=user_message_id
            )
            return ""

        if command in ["2", "3", "4", "5", "6"] and player_id:
            if add_command_to_queue('invite', player_id=player_id, squad_type=command, chat_id=chat_id, user_message_id=user_message_id):
                return ""
            else:
                return "❌ Failed to add command"
        
        elif command == "attack" and team_code:
            if add_command_to_queue('attack', team_code=team_code, chat_id=chat_id, user_message_id=user_message_id):
                return ""
            else:
                return "❌ Failed to add command"
        
        elif command == "lag" and team_code:
            if add_command_to_queue('lag', team_code=team_code, duration=duration, chat_id=chat_id, user_message_id=user_message_id):
                return ""
            else:
                return "❌ Failed to add command"
        
        # ==================== SPAM COMMANDS ====================
        elif command == "spam" and target_uid:
            username = f"user_{user_id}"
            if add_command_to_queue('spam', target_uid=target_uid, chat_id=chat_id, user_message_id=user_message_id, user_id=user_id, requester_name=username):
                return ""
            else:
                return "❌ Failed to add spam command"
        
        elif command == "stop_spam" and target_uid:
            if add_command_to_queue('stop_spam', target_uid=target_uid, chat_id=chat_id, user_message_id=user_message_id, user_id=user_id):
                return ""
            else:
                return "❌ Failed to add stop command"
        
        elif command == "spam_list":
            if add_command_to_queue('spam_list', chat_id=chat_id, user_message_id=user_message_id):
                return ""
            else:
                return "❌ Failed to add list command"
        
        # ==================== INFO COMMAND ====================
        elif command == "info" and target_uid:
            if add_command_to_queue('info', target_uid=target_uid, chat_id=chat_id, user_message_id=user_message_id, user_id=user_id):
                return ""
            else:
                return "❌ Failed to add info command"
        
        # ==================== FRIEND SYSTEM COMMANDS ====================
        elif command == "add" and target_uid:
            if add_command_to_queue('add_friend', target_uid=target_uid, chat_id=chat_id, user_message_id=user_message_id, user_id=user_id):
                return ""
            else:
                return "❌ Failed to add friend command"
        
        elif command == "remove" and target_uid:
            if add_command_to_queue('remove_friend', target_uid=target_uid, chat_id=chat_id, user_message_id=user_message_id, user_id=user_id):
                return ""
            else:
                return "❌ Failed to remove friend command"
        
        elif command == "friends":
            if add_command_to_queue('my_friends', chat_id=chat_id, user_message_id=user_message_id, user_id=user_id):
                return ""
            else:
                return "❌ Failed to get friends list"
        
        else:
            return ""
        
    except Exception as e:
        logger.error(f"Error in execute_telegram_command: {e}")
        return ""

def show_start_menu(chat_id, user_id, user_message_id=None):
    """قائمة الأوامر مع كل أمر في سطر وميزة النسخ"""
    user_id_str = str(user_id)
    admin_id_str = str(ADMIN_ID)
    
    menu = "📋 <b>SQUAD INVITES</b>\n"
    menu += "━━━━━━━━━━━━━━━━━━━━\n"
    menu += "├─ <code>/2 </code> (ID)\n"
    menu += "├─ <code>/3 </code> (ID)\n"
    menu += "├─ <code>/4 </code> (ID)\n"
    menu += "├─ <code>/5 </code> (ID)\n"
    menu += "└─ <code>/6 </code> (ID)\n\n"

    menu += "⚡ <b>ATTACK COMMANDS</b>\n"
    menu += "━━━━━━━━━━━━━━━━━━━━\n"
    menu += "├─ <code>/attack </code> (TEAM CODE)\n"
    menu += "└─ <code>/lag </code> (CODE) (MIN)\n\n"
    
    menu += "🎯 <b>SPAM COMMANDS</b>\n"
    menu += "━━━━━━━━━━━━━━━━━━━━\n"
    menu += "├─ <code>/spam </code> (UID)\n"
    menu += "├─ <code>/stop </code> (UID)\n"
    menu += "└─ <code>/spam_list</code>\n\n"
    
    menu += "ℹ️ <b>INFO COMMAND</b>\n"
    menu += "━━━━━━━━━━━━━━━━━━━━\n"
    menu += "└─ <code>/info </code> (UID)\n\n"
    
    menu += "👥 <b>FRIEND SYSTEM</b>\n"
    menu += "━━━━━━━━━━━━━━━━━━━━\n"
    menu += "├─ <code>/add </code> (UID) ➝ Add friend (4 hours)\n"
    menu += "├─ <code>/remove </code> (UID) ➝ Remove friend\n"
    menu += "└─ <code>/friends</code> ➝ Your friends list\n\n"

    menu += "📝 <b>EXAMPLES:</b>\n"
    menu += "<code>/attack 123456</code>\n"
    menu += "<code>/3 100021345</code>\n"
    menu += "<code>/spam 123456789</code>\n"
    menu += "<code>/stop 123456789</code>\n"
    menu += "<code>/info 123456789</code>\n"
    menu += "<code>/add 123456789</code>\n"
    menu += "<code>/friends</code>\n\n"

    menu += "⏰ <b>FRIEND SYSTEM INFO:</b>\n"
    menu += "━━━━━━━━━━━━━━━━━━━━\n"
    menu += "├─ Each friend lasts: 4 hours\n"
    menu += "├─ Max friends total: 100\n"
    menu += "└─ Max per day: 2 friends\n\n"

    if user_id_str == admin_id_str:
        menu += "🔑 <b>ADMIN PANEL:</b>\n"
        menu += "━━━━━━━━━━━━━━━━━━━━\n"
        menu += "├─ <code>/sid 30</code>\n"
        menu += "├─ <code>/stop</code>\n"
        menu += "└─ <code>/allgroups</code>\n\n"

    is_private = not str(chat_id).startswith('-')
    if is_private and user_id_str != admin_id_str:
        return "🙂🖕"

    return menu

def process_admin_command(command, parts, chat_id, user_id, user_message_id):
    """Process admin commands"""
    if str(user_id) != ADMIN_ID:
        if str(chat_id).startswith('-'):  # Group
            send_telegram_message("❌ Permission denied", chat_id=chat_id, reply_to_message_id=user_message_id)
        else:  # Private
            send_telegram_message("🙂🖕", chat_id=user_id, no_signature=True, reply_to_message_id=user_message_id)
        return
    
    if command == "sid" and len(parts) >= 2:
        try:
            days = int(parts[1])
            success, message = activate_group(chat_id, days, user_id)
            send_telegram_message(message, chat_id=chat_id, reply_to_message_id=user_message_id)
        except ValueError:
            send_telegram_message("❌ Days must be a number", chat_id=chat_id, reply_to_message_id=user_message_id)
    
    elif command == "stop" and len(parts) == 1:
        success, message = deactivate_group(chat_id, user_id)
        send_telegram_message(message, chat_id=chat_id, reply_to_message_id=user_message_id)
    
    elif command == "ginfo":
        info = get_group_info(chat_id)
        send_telegram_message(info, chat_id=chat_id, reply_to_message_id=user_message_id)
    
    elif command == "allgroups":
        groups_info = get_all_groups()
        send_telegram_message(groups_info, chat_id=chat_id, reply_to_message_id=user_message_id)

def monitor_telegram():
    """Monitor Telegram messages continuously"""
    global telegram_ready
    
    last_update_id = 0
    telegram_ready = True
    logger.info("🤖 Telegram bot monitoring started")
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            params = {"offset": last_update_id + 1, "timeout": 10}
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if data["ok"] and data["result"]:
                    for update in data["result"]:
                        last_update_id = update["update_id"]
                        
                        if "message" in update:
                            message = update["message"]
                            chat_id = message["chat"]["id"]
                            user_id = message["from"]["id"]
                            message_id = message["message_id"]
                            username = message["from"].get("username", f"user_{user_id}")
                            
                            if "text" in message:
                                text = message["text"]
                                process_telegram_message(text, chat_id, user_id, message_id, username)
                                
        except Exception as e:
            logger.error(f"Error in telegram monitor: {e}")
            time.sleep(3)

def process_telegram_message(message, chat_id, user_id, message_id, username=None):
    """Process Telegram messages"""
    try:
        raw_text = str(message).strip()
        m_text_lower = raw_text.lower()
        
        u_id = str(user_id)
        c_id = str(chat_id)
        a_id = str(ADMIN_ID)
        is_private = not c_id.startswith('-')

        if m_text_lower.startswith('/start'):
            if is_private and u_id != a_id:
                send_telegram_message("🙂🖕", chat_id=chat_id, no_signature=True)
                return

            menu = show_start_menu(chat_id, user_id, message_id)
            send_telegram_message(menu, chat_id=chat_id, reply_to_message_id=message_id)
            return

        if raw_text.startswith('/'):
            parts = raw_text.split()
            command = parts[0][1:].lower() 
            
            # ==================== FRIEND SYSTEM COMMANDS ====================
            if command == "add":
                if len(parts) < 2:
                    send_telegram_message(
                        "❌ Usage: /add [UID]\nExample: /add 123456789\n\n"
                        "💡 Friend will last for 4 hours\n"
                        "📊 Max 2 friends per day, 100 total",
                        chat_id=chat_id,
                        reply_to_message_id=message_id
                    )
                    return
                target_uid = parts[1]
                if not target_uid.isdigit():
                    send_telegram_message(
                        "❌ UID must be numbers only",
                        chat_id=chat_id,
                        reply_to_message_id=message_id
                    )
                    return
                execute_telegram_command(
                    "add",
                    target_uid=target_uid,
                    chat_id=chat_id,
                    user_id=user_id,
                    user_message_id=message_id
                )
                return
            
            elif command == "remove":
                if len(parts) < 2:
                    send_telegram_message(
                        "❌ Usage: /remove [UID]\nExample: /remove 123456789",
                        chat_id=chat_id,
                        reply_to_message_id=message_id
                    )
                    return
                target_uid = parts[1]
                if not target_uid.isdigit():
                    send_telegram_message(
                        "❌ UID must be numbers only",
                        chat_id=chat_id,
                        reply_to_message_id=message_id
                    )
                    return
                execute_telegram_command(
                    "remove",
                    target_uid=target_uid,
                    chat_id=chat_id,
                    user_id=user_id,
                    user_message_id=message_id
                )
                return
            
            elif command == "friends":
                execute_telegram_command(
                    "friends",
                    chat_id=chat_id,
                    user_id=user_id,
                    user_message_id=message_id
                )
                return
            
            # ==================== INFO COMMAND ====================
            if command == "info":
                if len(parts) < 2:
                    send_telegram_message(
                        "❌ Usage: /info [UID]\nExample: /info 9933949869",
                        chat_id=chat_id,
                        reply_to_message_id=message_id
                    )
                    return
                target_uid = parts[1]
                if not target_uid.isdigit():
                    send_telegram_message(
                        "❌ UID must be numbers only",
                        chat_id=chat_id,
                        reply_to_message_id=message_id
                    )
                    return
                execute_telegram_command(
                    "info",
                    target_uid=target_uid,
                    chat_id=chat_id,
                    user_id=user_id,
                    user_message_id=message_id
                )
                return
            
            # ==================== SPAM COMMANDS ====================
            if command == "spam":
                if len(parts) < 2:
                    send_telegram_message("❌ Usage: /spam [UID]", chat_id=chat_id, reply_to_message_id=message_id)
                    return
                target_uid = parts[1]
                if not target_uid.isdigit():
                    send_telegram_message("❌ UID must be a number", chat_id=chat_id, reply_to_message_id=message_id)
                    return
                execute_telegram_command(
                    "spam",
                    target_uid=target_uid,
                    chat_id=chat_id,
                    user_id=user_id,
                    user_message_id=message_id
                )
                return
            
            elif command == "stop":
                # إذا كان الأمر stop ومعه رقم، فهو إيقاف سبام
                if len(parts) >= 2 and parts[1].isdigit():
                    target_uid = parts[1]
                    execute_telegram_command(
                        "stop_spam",
                        target_uid=target_uid,
                        chat_id=chat_id,
                        user_id=user_id,
                        user_message_id=message_id
                    )
                    return
                # إذا كان الأمر stop بدون رقم، فهو إيقاف المجموعة (للمطور فقط)
                elif len(parts) == 1:
                    process_admin_command(command, parts, chat_id, user_id, message_id)
                    return
                else:
                    send_telegram_message("❌ Usage: /stop [UID] or /stop (for admins)", chat_id=chat_id, reply_to_message_id=message_id)
                    return
            
            elif command == "spam_list" or command == "spamlist":
                execute_telegram_command(
                    "spam_list",
                    chat_id=chat_id,
                    user_id=user_id,
                    user_message_id=message_id
                )
                return

            # ==================== ADMIN COMMANDS ====================
            if command in ["sid", "ginfo", "allgroups"]:
                process_admin_command(command, parts, chat_id, user_id, message_id)
                return

            # ==================== ORIGINAL ATTACK COMMANDS ====================
            if command in ["2", "3", "4", "5", "6"]:
                if len(parts) < 2:
                    send_telegram_message(f"❌ Usage: /{command} [Player ID]", chat_id=chat_id, reply_to_message_id=message_id)
                    return
                target_data = parts[1]
                execute_telegram_command(
                    command, 
                    player_id=target_data,
                    chat_id=chat_id, 
                    user_id=user_id, 
                    user_message_id=message_id
                )
            
            elif command in ["attack", "lag"]:
                if len(parts) < 2:
                    send_telegram_message(f"❌ Usage: /{command} [Team Code]", chat_id=chat_id, reply_to_message_id=message_id)
                    return
                target_data = parts[1]
                duration = int(parts[2]) if len(parts) > 2 and command == "lag" and parts[2].isdigit() else 1
                execute_telegram_command(
                    command, 
                    team_code=target_data,
                    duration=duration,
                    chat_id=chat_id, 
                    user_id=user_id, 
                    user_message_id=message_id
                )

    except Exception as e:
        logger.error(f"Error in process_telegram_message: {e}")

def start_game_clients():
    """تشغيل جميع الحسابات من ملف JSON"""
    accounts = load_accounts()
    if not accounts:
        logger.error("❌ لا توجد حسابات لبدء التشغيل")
        return []
    
    clients = []
    for i, account_data in enumerate(accounts[:MAX_ACCOUNTS]):
        logger.info(f"🚀 بدء تشغيل الحساب #{i+1}: {account_data.get('name', 'Unknown')}")
        client = FF_CLIENT(account_data)
        client.start()
        clients.append(client)
        time.sleep(2)
    
    logger.info(f"✅ تم بدء تشغيل {len(clients)} حساب")
    return clients

def health_monitor():
    """Monitor bot health and restart if needed"""
    while True:
        try:
            check_connection_health()
            cleanup_threads()
            gc.collect()
            time.sleep(300)
        except Exception as e:
            logger.error(f"Error in health monitor: {e}")
            time.sleep(10)

def init_friend_system():
    """تهيئة نظام الأصدقاء"""
    global JWT_TOKEN
    
    _load_friends_data()
    
    # بدء تجديد التوكن
    threading.Thread(target=_update_jwt_periodically, daemon=True).start()
    
    # بدء إزالة الأصدقاء منتهي الصلاحية
    threading.Thread(target=_remove_expired_friends, daemon=True).start()
    
    # جلب التوكن أول مرة
    JWT_TOKEN = _fetch_jwt_token()
    if JWT_TOKEN:
        logger.info("✅ Friend system initialized with valid JWT token")
    else:
        logger.warning("⚠️ Friend system initialized but JWT token is invalid")

# Main
if __name__ == "__main__":
    try:
        logger.info("🚀 Starting Free Fire Bot System...")
        logger.info("=" * 50)
        
        logger.info("0️⃣ Initializing Friend System...")
        init_friend_system()
        
        logger.info("1️⃣ Starting Telegram Bot...")
        telegram_thread = threading.Thread(target=monitor_telegram)
        telegram_thread.daemon = True
        telegram_thread.start()
        
        time.sleep(3)
        
        logger.info("2️⃣ Starting Command Processor...")
        command_processor = CommandProcessor()
        command_processor.start()
        
        logger.info("3️⃣ Starting Health Manager...")
        health_manager = HealthManager()
        health_thread = threading.Thread(
            target=health_manager.monitor_all_clients, 
            args=(current_clients,), 
            daemon=True
        )
        health_thread.start()
        
        logger.info("4️⃣ Starting Connection Health Monitor...")
        connection_health_thread = threading.Thread(target=health_monitor, daemon=True)
        connection_health_thread.start()
        
        logger.info("5️⃣ Starting Game Clients from accounts.json...")
        game_clients = start_game_clients()
        
        logger.info("=" * 50)
        logger.info("✅ All systems started successfully!")
        logger.info(f"📱 Telegram: Ready")
        logger.info(f"🎮 Free Fire: {len(game_clients)} accounts loaded")
        logger.info(f"⚡ Max concurrent requests: {MAX_CONCURRENT_REQUESTS}")
        logger.info(f"🎯 Spam System: Active")
        logger.info(f"ℹ️ Info Command: Active")
        logger.info(f"👥 Friend System: Active")
        logger.info("=" * 50)
        
        while True:
            try:
                time.sleep(30)
                connected_clients = sum(1 for client in current_clients if client.is_connected)
                connecting_clients = sum(1 for client in current_clients if client.is_connecting)
                total_requests = sum(active_requests_per_account.values())
                active_spam = len(get_active_spam_targets())
                total_friends = _get_friends_count()
                
                status_msg = (f"📊 Status: Telegram=✅ | Game Clients={connected_clients}/{len(game_clients)} | "
                             f"Connecting={connecting_clients} | Active Requests={total_requests} | "
                             f"Queue={command_queue.qsize()} | Spam Targets={active_spam} | Friends={total_friends}")
                logger.info(status_msg)
                
            except KeyboardInterrupt:
                logger.info("\n🛑 Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(10)
            
    except Exception as e:
        logger.error(f"❌ Main bot error: {str(e)}")
        logger.info("🔄 Restarting in 5 seconds...")
        time.sleep(RESTART_DELAY)
        restart_bot()
