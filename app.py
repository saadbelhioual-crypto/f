from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from functools import wraps
import os
import json
import subprocess
import threading
import time
import uuid
import shutil
import sys
import re
from datetime import datetime
import psutil

app = Flask(__name__)
app.secret_key = 'jagwar_super_secret_key_2026_secure'

# ============== البيانات والتكوين ==============
DATA_FILE = 'data.json'
SERVERS_DIR = 'servers'

def init_data():
    if not os.path.exists(DATA_FILE):
        default_data = {
            'users': {},
            'servers': {},
            'login_logs': [],
            'failed_logins': [],
            'signup_logs': []
        }
        # إضافة الأدمن الافتراضي
        default_data['users']['JAGWARGG'] = {
            'password': 'JAGWAR12345',
            'email': 'admin@jagwar.host',
            'is_admin': True,
            'is_premium': True,
            'servers': [],
            'created_at': datetime.now().isoformat(),
            'max_servers': 5
        }
        save_data(default_data)
    
    if not os.path.exists(SERVERS_DIR):
        os.makedirs(SERVERS_DIR)

def load_data():
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

init_data()

# ============== دوال المساعدة ==============
def validate_username(username):
    """التحقق من صحة اسم المستخدم"""
    if len(username) < 3 or len(username) > 20:
        return False, "Username must be between 3 and 20 characters"
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "Username can only contain letters, numbers, and underscore"
    return True, "OK"

def validate_password(password):
    """التحقق من صحة كلمة المرور"""
    if len(password) < 6:
        return False, "Password must be at least 6 characters"
    if len(password) > 50:
        return False, "Password too long"
    return True, "OK"

def validate_email(email):
    """التحقق من صحة البريد الإلكتروني"""
    if not email:
        return True, "OK"  # Email optional
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return False, "Invalid email format"
    return True, "OK"

# ============== إدارة السيرفرات ==============
server_processes = {}

def get_user_server_path(username, server_id):
    return os.path.join(SERVERS_DIR, username, server_id)

def create_server_folder(username, server_name, language, description):
    data = load_data()
    user = data['users'].get(username)
    
    if not user:
        return None, "User not found"
    
    max_servers = user.get('max_servers', 1)
    current_servers = len(user.get('servers', []))
    
    if current_servers >= max_servers:
        return None, f"Maximum servers reached ({max_servers})"
    
    server_id = str(uuid.uuid4())[:8]
    server_path = get_user_server_path(username, server_id)
    
    os.makedirs(server_path, exist_ok=True)
    
    with open(os.path.join(server_path, 'main.py'), 'w') as f:
        f.write('"""\nWelcome to JAGWAR HOST\nYour Python server is running!\n"""\n\nprint("Server is running on JAGWAR HOST!")\n\n# Your code here\n')
    
    with open(os.path.join(server_path, 'requirements.txt'), 'w') as f:
        f.write('# Add your Python packages here\n# Example:\n# flask\n# requests\n# numpy\n')
    
    server_info = {
        'id': server_id,
        'name': server_name,
        'language': language,
        'description': description,
        'created_at': datetime.now().isoformat(),
        'status': 'stopped',
        'owner': username,
        'usage_cpu': 0,
        'usage_memory': 0,
        'usage_disk': 0
    }
    
    data['servers'][server_id] = server_info
    user['servers'].append(server_id)
    save_data(data)
    
    return server_id, "Server created successfully"

# ============== Routes ==============
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')
    
    data = load_data()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    email = request.form.get('email', '').strip()
    confirm_password = request.form.get('confirm_password', '')
    
    ip = request.remote_addr
    browser = request.headers.get('User-Agent', 'Unknown')
    
    # التحقق من صحة البيانات
    valid, msg = validate_username(username)
    if not valid:
        return render_template('signup.html', error=msg, username=username, email=email)
    
    valid, msg = validate_password(password)
    if not valid:
        return render_template('signup.html', error=msg, username=username, email=email)
    
    if password != confirm_password:
        return render_template('signup.html', error="Passwords do not match", username=username, email=email)
    
    valid, msg = validate_email(email)
    if not valid:
        return render_template('signup.html', error=msg, username=username, email=email)
    
    # التحقق من وجود المستخدم
    if username in data['users']:
        return render_template('signup.html', error="Username already exists. Please choose another.", username=username, email=email)
    
    # إنشاء مستخدم جديد
    data['users'][username] = {
        'password': password,
        'email': email,
        'is_admin': False,
        'is_premium': False,
        'servers': [],
        'created_at': datetime.now().isoformat(),
        'max_servers': 1
    }
    
    # تسجيل عملية التسجيل
    data['signup_logs'].append({
        'username': username,
        'email': email,
        'ip': ip,
        'browser': browser,
        'timestamp': datetime.now().isoformat()
    })
    
    save_data(data)
    
    # تسجيل الدخول تلقائياً بعد التسجيل
    session['username'] = username
    session['is_admin'] = False
    
    return redirect(url_for('dashboard'))

@app.route('/signin', methods=['POST'])
def signin():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    ip = request.remote_addr
    browser = request.headers.get('User-Agent', 'Unknown')
    timestamp = datetime.now().isoformat()
    
    data = load_data()
    user = data['users'].get(username)
    
    # التحقق من صحة اسم المستخدم وكلمة المرور
    if user and user['password'] == password:
        session['username'] = username
        session['is_admin'] = user.get('is_admin', False)
        
        # تسجيل الدخول الناجح
        data['login_logs'].append({
            'username': username,
            'ip': ip,
            'browser': browser,
            'timestamp': timestamp,
            'status': 'success'
        })
        save_data(data)
        
        if user.get('is_admin'):
            return redirect(url_for('admin_panel'))
        return redirect(url_for('dashboard'))
    else:
        # تسجيل فاشل
        data['failed_logins'].append({
            'username': username,
            'password': password,
            'ip': ip,
            'browser': browser,
            'timestamp': timestamp
        })
        save_data(data)
        return render_template('index.html', error="Invalid username or password")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    data = load_data()
    user = data['users'].get(session['username'], {})
    user_servers = [data['servers'][sid] for sid in user.get('servers', []) if sid in data['servers']]
    
    max_servers = user.get('max_servers', 1)
    remaining = max_servers - len(user_servers)
    
    return render_template('dashboard.html',
                         user=user,
                         servers=user_servers,
                         max_servers=max_servers,
                         remaining=remaining)

# إضافة باقي الـ routes (admin, server control, etc.) مثل ما ذكرنا سابقاً...

# ============== ديكوراتورات المصادقة ==============
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('index'))
        user_data = load_data().get('users', {}).get(session['username'], {})
        if not user_data.get('is_admin', False):
            return "Access denied", 403
        return f(*args, **kwargs)
    return decorated_function

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
