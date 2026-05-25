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
import secrets
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
            'is_premium': False,
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

# ============== إدارة السيرفرات والبيئات ==============
server_processes = {}

def get_user_server_path(username, server_id):
    """الحصول على مسار مجلد السيرفر"""
    return os.path.join(SERVERS_DIR, username, server_id)

def create_server_folder(username, server_name, language, description):
    """إنشاء مجلدات السيرفر"""
    data = load_data()
    user = data['users'].get(username)
    
    if not user:
        return None, "User not found"
    
    max_servers = 5 if user.get('is_premium', False) else 1
    current_servers = len(user.get('servers', []))
    
    if current_servers >= max_servers:
        return None, f"Maximum servers reached ({max_servers})"
    
    server_id = str(uuid.uuid4())[:8]
    server_path = get_user_server_path(username, server_id)
    
    os.makedirs(server_path, exist_ok=True)
    
    # إنشاء ملفات افتراضية
    with open(os.path.join(server_path, 'main.py'), 'w') as f:
        f.write('# Welcome to JAGWAR HOST\nprint("Server is running!")\n')
    
    with open(os.path.join(server_path, 'requirements.txt'), 'w') as f:
        f.write('# Add your requirements here\n# flask\n# requests\n')
    
    # حفظ معلومات السيرفر
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

def start_server(server_id):
    """بدء تشغيل السيرفر"""
    data = load_data()
    server = data['servers'].get(server_id)
    
    if not server:
        return False, "Server not found"
    
    server_path = get_user_server_path(server['owner'], server_id)
    main_file = os.path.join(server_path, 'main.py')
    
    if not os.path.exists(main_file):
        return False, "main.py not found"
    
    # تثبيت المتطلبات
    req_file = os.path.join(server_path, 'requirements.txt')
    install_output = ""
    
    if os.path.exists(req_file):
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', req_file],
                               capture_output=True, text=True, cwd=server_path)
        install_output = result.stdout + result.stderr
    
    # بدء العملية
    process = subprocess.Popen([sys.executable, 'main.py'],
                              cwd=server_path,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              text=True,
                              bufsize=1)
    
    server_processes[server_id] = {
        'process': process,
        'start_time': time.time(),
        'install_output': install_output
    }
    
    server['status'] = 'running'
    save_data(data)
    
    return True, "Server started successfully\n" + install_output

def stop_server(server_id):
    """إيقاف السيرفر"""
    if server_id in server_processes:
        process = server_processes[server_id]['process']
        process.terminate()
        process.wait(timeout=5)
        del server_processes[server_id]
    
    data = load_data()
    if server_id in data['servers']:
        data['servers'][server_id]['status'] = 'stopped'
        save_data(data)
    
    return True, "Server stopped"

def restart_server(server_id):
    """إعادة تشغيل السيرفر"""
    stop_server(server_id)
    time.sleep(1)
    return start_server(server_id)

def get_server_console(server_id):
    """الحصول على مخرجات الكونسول"""
    if server_id not in server_processes:
        return "Server is not running. Start the server to see console output."
    
    process_info = server_processes[server_id]
    process = process_info['process']
    output = process_info.get('install_output', '')
    
    # محاولة قراءة المخرجات
    try:
        import select
        if select.select([process.stdout], [], [], 0)[0]:
            output += process.stdout.read()
        if select.select([process.stderr], [], [], 0)[0]:
            output += process.stderr.read()
    except:
        pass
    
    return output if output else "Console ready - waiting for output..."

def update_server_stats():
    """تحديث إحصائيات السيرفرات"""
    for server_id, process_info in server_processes.items():
        process = process_info['process']
        if process.poll() is not None:
            # العملية انتهت
            data = load_data()
            if server_id in data['servers']:
                data['servers'][server_id]['status'] = 'stopped'
                save_data(data)
            del server_processes[server_id]
        else:
            # تحديث الإحصائيات
            try:
                proc = psutil.Process(process.pid)
                cpu_percent = proc.cpu_percent(interval=0.1)
                memory_percent = proc.memory_percent()
                
                data = load_data()
                if server_id in data['servers']:
                    data['servers'][server_id]['usage_cpu'] = round(cpu_percent, 1)
                    data['servers'][server_id]['usage_memory'] = round(memory_percent, 1)
                    save_data(data)
            except:
                pass

# ============== Routes ==============
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')
    
    data = load_data()
    username = request.form.get('username')
    password = request.form.get('password')
    email = request.form.get('email')
    ip = request.remote_addr
    browser = request.headers.get('User-Agent', 'Unknown')
    
    # التحقق من وجود المستخدم
    if username in data['users']:
        return render_template('signup.html', error="Username already exists")
    
    if len(password) < 6:
        return render_template('signup.html', error="Password must be at least 6 characters")
    
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
    
    # تسجيل الدخول تلقائياً
    session['username'] = username
    session['is_admin'] = False
    
    return redirect(url_for('dashboard'))

@app.route('/signin', methods=['POST'])
def signin():
    username = request.form.get('username')
    password = request.form.get('password')
    ip = request.remote_addr
    browser = request.headers.get('User-Agent', 'Unknown')
    timestamp = datetime.now().isoformat()
    
    data = load_data()
    user = data['users'].get(username)
    
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

# ============== Admin Panel ==============
@app.route('/admin')
@admin_required
def admin_panel():
    data = load_data()
    return render_template('admin.html', 
                         users=data['users'],
                         servers=data['servers'],
                         login_logs=data['login_logs'],
                         failed_logins=data['failed_logins'],
                         signup_logs=data['signup_logs'])

@app.route('/admin/add_user', methods=['POST'])
@admin_required
def admin_add_user():
    username = request.form.get('username')
    password = request.form.get('password')
    email = request.form.get('email')
    
    data = load_data()
    if username in data['users']:
        return jsonify({'error': 'User exists'}), 400
    
    data['users'][username] = {
        'password': password,
        'email': email,
        'is_admin': False,
        'is_premium': False,
        'servers': [],
        'created_at': datetime.now().isoformat(),
        'max_servers': 1
    }
    save_data(data)
    
    return jsonify({'success': True})

@app.route('/admin/make_premium', methods=['POST'])
@admin_required
def admin_make_premium():
    username = request.form.get('username')
    
    data = load_data()
    if username in data['users']:
        data['users'][username]['is_premium'] = True
        data['users'][username]['max_servers'] = 5
        save_data(data)
        return jsonify({'success': True})
    
    return jsonify({'error': 'User not found'}), 400

@app.route('/admin/remove_user', methods=['POST'])
@admin_required
def admin_remove_user():
    username = request.form.get('username')
    
    if username == 'JAGWARGG':
        return jsonify({'error': 'Cannot remove admin'}), 400
    
    data = load_data()
    if username in data['users']:
        # حذف مجلدات المستخدم
        user_servers = data['users'][username].get('servers', [])
        for server_id in user_servers:
            server_path = get_user_server_path(username, server_id)
            if os.path.exists(server_path):
                shutil.rmtree(server_path)
            if server_id in data['servers']:
                del data['servers'][server_id]
        
        del data['users'][username]
        save_data(data)
        return jsonify({'success': True})
    
    return jsonify({'error': 'User not found'}), 400

# ============== User Dashboard ==============
@app.route('/dashboard')
@login_required
def dashboard():
    data = load_data()
    user = data['users'].get(session['username'], {})
    user_servers = [data['servers'][sid] for sid in user.get('servers', []) if sid in data['servers']]
    
    max_servers = 5 if user.get('is_premium', False) else 1
    remaining = max_servers - len(user_servers)
    
    return render_template('dashboard.html',
                         user=user,
                         servers=user_servers,
                         max_servers=max_servers,
                         remaining=remaining)

@app.route('/create_server', methods=['POST'])
@login_required
def create_server():
    server_name = request.form.get('server_name')
    language = request.form.get('language', 'Python')
    description = request.form.get('description', '')
    
    username = session['username']
    server_id, message = create_server_folder(username, server_name, language, description)
    
    if server_id:
        return jsonify({'success': True, 'server_id': server_id, 'message': message})
    return jsonify({'success': False, 'message': message}), 400

@app.route('/delete_server/<server_id>', methods=['POST'])
@login_required
def delete_server(server_id):
    data = load_data()
    username = session['username']
    
    if server_id not in data['servers']:
        return jsonify({'error': 'Server not found'}), 400
    
    server = data['servers'][server_id]
    if server['owner'] != username and not data['users'][username].get('is_admin'):
        return jsonify({'error': 'Permission denied'}), 403
    
    # إيقاف السيرفر إذا كان يعمل
    stop_server(server_id)
    
    # حذف المجلد
    server_path = get_user_server_path(server['owner'], server_id)
    if os.path.exists(server_path):
        shutil.rmtree(server_path)
    
    # حذف من البيانات
    del data['servers'][server_id]
    if server_id in data['users'][server['owner']]['servers']:
        data['users'][server['owner']]['servers'].remove(server_id)
    save_data(data)
    
    return jsonify({'success': True})

# ============== Server Control Panel ==============
@app.route('/server/<server_id>')
@login_required
def server_control(server_id):
    data = load_data()
    username = session['username']
    
    if server_id not in data['servers']:
        return "Server not found", 404
    
    server = data['servers'][server_id]
    if server['owner'] != username and not data['users'][username].get('is_admin'):
        return "Permission denied", 403
    
    return render_template('server_control.html', server=server, server_id=server_id)

@app.route('/api/server/<server_id>/start', methods=['POST'])
@login_required
def api_start_server(server_id):
    success, message = start_server(server_id)
    return jsonify({'success': success, 'message': message})

@app.route('/api/server/<server_id>/stop', methods=['POST'])
@login_required
def api_stop_server(server_id):
    success, message = stop_server(server_id)
    return jsonify({'success': success, 'message': message})

@app.route('/api/server/<server_id>/restart', methods=['POST'])
@login_required
def api_restart_server(server_id):
    success, message = restart_server(server_id)
    return jsonify({'success': success, 'message': message})

@app.route('/api/server/<server_id>/console')
@login_required
def api_server_console(server_id):
    output = get_server_console(server_id)
    return jsonify({'console': output})

@app.route('/api/server/<server_id>/files')
@login_required
def api_server_files(server_id):
    data = load_data()
    username = session['username']
    
    if server_id not in data['servers']:
        return jsonify({'error': 'Server not found'}), 404
    
    server = data['servers'][server_id]
    server_path = get_user_server_path(server['owner'], server_id)
    path = request.args.get('path', '')
    
    full_path = os.path.join(server_path, path)
    
    if not os.path.exists(full_path):
        return jsonify({'error': 'Path not found'}), 404
    
    files = []
    for item in os.listdir(full_path):
        item_path = os.path.join(full_path, item)
        files.append({
            'name': item,
            'is_dir': os.path.isdir(item_path),
            'size': os.path.getsize(item_path) if os.path.isfile(item_path) else 0,
            'path': os.path.join(path, item) if path else item
        })
    
    return jsonify({'files': files, 'current_path': path})

@app.route('/api/server/<server_id>/file', methods=['GET', 'POST', 'DELETE', 'PUT'])
@login_required
def api_server_file(server_id):
    data = load_data()
    username = session['username']
    
    if server_id not in data['servers']:
        return jsonify({'error': 'Server not found'}), 404
    
    server = data['servers'][server_id]
    server_path = get_user_server_path(server['owner'], server_id)
    file_path = request.args.get('path', '')
    full_path = os.path.join(server_path, file_path)
    
    if request.method == 'GET':
        if not os.path.exists(full_path):
            return jsonify({'error': 'File not found'}), 404
        with open(full_path, 'r') as f:
            content = f.read()
        return jsonify({'content': content, 'path': file_path})
    
    elif request.method == 'POST':
        # إنشاء ملف
        content = request.json.get('content', '')
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w') as f:
            f.write(content)
        return jsonify({'success': True})
    
    elif request.method == 'PUT':
        # تعديل ملف
        content = request.json.get('content', '')
        with open(full_path, 'w') as f:
            f.write(content)
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        if os.path.isdir(full_path):
            shutil.rmtree(full_path)
        else:
            os.remove(full_path)
        return jsonify({'success': True})

@app.route('/api/server/<server_id>/folder', methods=['POST'])
@login_required
def api_create_folder(server_id):
    data = load_data()
    username = session['username']
    
    if server_id not in data['servers']:
        return jsonify({'error': 'Server not found'}), 404
    
    server = data['servers'][server_id]
    server_path = get_user_server_path(server['owner'], server_id)
    folder_path = request.json.get('path', '')
    folder_name = request.json.get('name', '')
    
    full_path = os.path.join(server_path, folder_path, folder_name)
    os.makedirs(full_path, exist_ok=True)
    
    return jsonify({'success': True})

@app.route('/api/server/<server_id>/rename', methods=['POST'])
@login_required
def api_rename_item(server_id):
    data = load_data()
    username = session['username']
    
    if server_id not in data['servers']:
        return jsonify({'error': 'Server not found'}), 404
    
    server = data['servers'][server_id]
    server_path = get_user_server_path(server['owner'], server_id)
    old_path = request.json.get('old_path', '')
    new_name = request.json.get('new_name', '')
    
    old_full = os.path.join(server_path, old_path)
    new_full = os.path.join(os.path.dirname(old_full), new_name)
    
    os.rename(old_full, new_full)
    
    return jsonify({'success': True})

@app.route('/api/server/<server_id>/upload', methods=['POST'])
@login_required
def api_upload_file(server_id):
    data = load_data()
    username = session['username']
    
    if server_id not in data['servers']:
        return jsonify({'error': 'Server not found'}), 404
    
    server = data['servers'][server_id]
    server_path = get_user_server_path(server['owner'], server_id)
    upload_path = request.form.get('path', '')
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    full_path = os.path.join(server_path, upload_path, file.filename)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    file.save(full_path)
    
    return jsonify({'success': True})

# تحديث الإحصائيات كل 5 ثواني
def stats_updater():
    while True:
        update_server_stats()
        time.sleep(5)

threading.Thread(target=stats_updater, daemon=True).start()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
