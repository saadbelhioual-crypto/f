#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JAGWAR HOST - Enterprise Python Hosting Platform
Production-Ready Flask Application
"""

import os
import sys
import json
import shutil
import subprocess
import threading
import queue
import time
import signal
import uuid
import logging
import platform
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Generator
import psutil
from flask import (
    Flask, render_template, request, redirect, 
    url_for, session, jsonify, Response, g
)
from werkzeug.security import generate_password_hash, check_password_hash

# ============================================================================
# CONFIGURATION
# ============================================================================
class Config:
    APP_NAME = "JAGWAR HOST"
    APP_VERSION = "3.0.0"
    BASE_DIR = Path(__file__).resolve().parent
    SERVERS_ROOT = BASE_DIR / 'servers'
    DATA_DIR = BASE_DIR / 'data'
    
    USERS_FILE = DATA_DIR / 'users.json'
    SERVERS_FILE = DATA_DIR / 'servers.json'
    LOGS_FILE = DATA_DIR / 'activity_logs.json'
    
    MAX_DEFAULT_SERVERS = 1
    MAX_PREMIUM_SERVERS = 5
    
    ADMIN_USERNAME = "JAGWARGG"
    ADMIN_PASSWORD = "JAGWAR12345"
    SECRET_KEY = 'jagwar-host-production-secret-2026'
    
    SESSION_LIFETIME = 86400  # 24 hours
    MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB
    MAX_CONSOLE_BUFFER = 10000
    
    @classmethod
    def init_directories(cls):
        for directory in [cls.SERVERS_ROOT, cls.DATA_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

# ============================================================================
# JSON DATABASE SYSTEM
# ============================================================================
class JSONDatabase:
    def __init__(self, filepath: Path):
        self.filepath = Path(filepath)
        self.lock = threading.RLock()
        self._ensure_file()
    
    def _ensure_file(self):
        if not self.filepath.exists():
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump([], f)
    
    def _read(self) -> List[Dict]:
        with self.lock:
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
    
    def _write(self, data: List[Dict]):
        with self.lock:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
    
    def all(self) -> List[Dict]:
        return self._read()
    
    def query(self, **kwargs) -> List[Dict]:
        data = self._read()
        return [item for item in data if all(item.get(k) == v for k, v in kwargs.items())]
    
    def find_one(self, **kwargs) -> Optional[Dict]:
        results = self.query(**kwargs)
        return results[0] if results else None
    
    def find_by_id(self, record_id: str) -> Optional[Dict]:
        return self.find_one(id=record_id)
    
    def insert(self, record: Dict) -> bool:
        data = self._read()
        if 'id' not in record:
            record['id'] = str(uuid.uuid4())
        if 'created_at' not in record:
            record['created_at'] = datetime.now().isoformat()
        data.append(record)
        self._write(data)
        return True
    
    def update(self, record_id: str, updates: Dict) -> bool:
        data = self._read()
        for item in data:
            if item.get('id') == record_id:
                item.update(updates)
                item['updated_at'] = datetime.now().isoformat()
                self._write(data)
                return True
        return False
    
    def delete(self, record_id: str) -> bool:
        data = self._read()
        new_data = [item for item in data if item.get('id') != record_id]
        if len(new_data) < len(data):
            self._write(new_data)
            return True
        return False
    
    def delete_where(self, **conditions) -> int:
        data = self._read()
        original_len = len(data)
        data = [item for item in data if not all(item.get(k) == v for k, v in conditions.items())]
        count = original_len - len(data)
        if count > 0:
            self._write(data)
        return count
    
    def count(self, **conditions) -> int:
        return len(self.query(**conditions))
    
    def exists(self, **conditions) -> bool:
        return self.count(**conditions) > 0

# ============================================================================
# PROCESS MANAGER - Server Isolation & Execution
# ============================================================================
class ProcessManager:
    def __init__(self):
        self.registry: Dict[str, Dict[str, Any]] = {}
        self.registry_lock = threading.RLock()
        self._start_monitor()
    
    def _start_monitor(self):
        def monitor_loop():
            while True:
                time.sleep(5)
                with self.registry_lock:
                    dead_keys = []
                    for key, proc_data in self.registry.items():
                        process = proc_data.get('process')
                        if process and process.poll() is not None:
                            proc_data['status'] = 'stopped'
                            dead_keys.append(key)
        threading.Thread(target=monitor_loop, daemon=True).start()
    
    def get_server_path(self, username: str, server_name: str) -> Path:
        return Config.SERVERS_ROOT / username / server_name
    
    def get_venv_path(self, username: str, server_name: str) -> Path:
        return self.get_server_path(username, server_name) / 'venv'
    
    def get_venv_python(self, username: str, server_name: str) -> Path:
        venv_path = self.get_venv_path(username, server_name)
        if platform.system() == 'Windows':
            return venv_path / 'Scripts' / 'python.exe'
        return venv_path / 'bin' / 'python3'
    
    def get_venv_pip(self, username: str, server_name: str) -> Path:
        venv_path = self.get_venv_path(username, server_name)
        if platform.system() == 'Windows':
            return venv_path / 'Scripts' / 'pip.exe'
        return venv_path / 'bin' / 'pip'
    
    def create_server_environment(self, username: str, server_name: str) -> Tuple[bool, str]:
        server_path = self.get_server_path(username, server_name)
        venv_path = self.get_venv_path(username, server_name)
        
        try:
            server_path.mkdir(parents=True, exist_ok=True)
            
            if not venv_path.exists():
                result = subprocess.run(
                    [sys.executable, '-m', 'venv', '--copies', str(venv_path)],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if result.returncode != 0:
                    return False, f"Failed to create venv: {result.stderr}"
                
                pip_path = self.get_venv_pip(username, server_name)
                subprocess.run(
                    [str(pip_path), 'install', '--upgrade', 'pip'],
                    capture_output=True,
                    timeout=60
                )
            
            main_py = server_path / 'main.py'
            if not main_py.exists():
                main_py.write_text('''#!/usr/bin/env python3
"""JAGWAR HOST Application"""
import sys, time
from datetime import datetime

def main():
    print("=" * 50)
    print(f"JAGWAR HOST Server Started")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    counter = 0
    try:
        while True:
            counter += 1
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Heartbeat #{counter}")
            time.sleep(5)
    except KeyboardInterrupt:
        print("\\nShutting down...")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
''', encoding='utf-8')
            
            req_file = server_path / 'requirements.txt'
            if not req_file.exists():
                req_file.write_text("# Add your dependencies here\n", encoding='utf-8')
            
            return True, "Server environment created successfully"
            
        except subprocess.TimeoutExpired:
            return False, "Virtual environment creation timed out"
        except Exception as e:
            return False, str(e)
    
    def install_dependencies(self, username: str, server_name: str) -> Tuple[bool, str]:
        server_path = self.get_server_path(username, server_name)
        req_file = server_path / 'requirements.txt'
        pip_path = self.get_venv_pip(username, server_name)
        
        if not req_file.exists() or req_file.stat().st_size == 0:
            return True, "No dependencies to install"
        
        try:
            result = subprocess.run(
                [str(pip_path), 'install', '-r', str(req_file)],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(server_path)
            )
            
            if result.returncode == 0:
                return True, "Dependencies installed successfully"
            else:
                return False, result.stderr
        except subprocess.TimeoutExpired:
            return False, "Dependency installation timed out"
        except Exception as e:
            return False, str(e)
    
    def start_server(self, username: str, server_name: str) -> Tuple[bool, str]:
        key = f"{username}_{server_name}"
        
        self.stop_server(username, server_name)
        
        server_path = self.get_server_path(username, server_name)
        venv_python = self.get_venv_python(username, server_name)
        
        if not venv_python.exists():
            return False, "Virtual environment not found"
        
        dep_success, dep_msg = self.install_dependencies(username, server_name)
        
        try:
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            env['JAGWAR_SERVER_NAME'] = server_name
            env['JAGWAR_USERNAME'] = username
            
            process = subprocess.Popen(
                [str(venv_python), '-u', str(server_path / 'main.py')],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=str(server_path),
                env=env,
                preexec_fn=os.setsid if platform.system() != 'Windows' else None
            )
            
            with self.registry_lock:
                self.registry[key] = {
                    'process': process,
                    'pid': process.pid,
                    'start_time': time.time(),
                    'status': 'running',
                    'username': username,
                    'server_name': server_name,
                    'output_queue': queue.Queue(maxsize=Config.MAX_CONSOLE_BUFFER)
                }
                
                reader_thread = threading.Thread(
                    target=self._read_output,
                    args=(key, process),
                    daemon=True
                )
                reader_thread.start()
            
            return True, f"Server started successfully (PID: {process.pid})"
            
        except Exception as e:
            return False, str(e)
    
    def _read_output(self, key: str, process: subprocess.Popen):
        try:
            for line in iter(process.stdout.readline, ''):
                with self.registry_lock:
                    if key in self.registry:
                        try:
                            self.registry[key]['output_queue'].put_nowait(line)
                        except queue.Full:
                            try:
                                self.registry[key]['output_queue'].get_nowait()
                                self.registry[key]['output_queue'].put_nowait(line)
                            except:
                                pass
            process.stdout.close()
        except Exception:
            pass
    
    def stop_server(self, username: str, server_name: str) -> Tuple[bool, str]:
        key = f"{username}_{server_name}"
        
        with self.registry_lock:
            if key not in self.registry:
                return False, "Server is not running"
            
            proc_data = self.registry[key]
            process = proc_data.get('process')
            
            if not process or process.poll() is not None:
                del self.registry[key]
                return True, "Server was already stopped"
            
            try:
                if platform.system() != 'Windows':
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                else:
                    process.terminate()
                
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    if platform.system() != 'Windows':
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    else:
                        process.kill()
                    process.wait(timeout=2)
                
                exit_code = process.returncode
                proc_data['status'] = 'stopped'
                proc_data['exit_code'] = exit_code
                
                return True, f"Server stopped (exit code: {exit_code})"
                
            except Exception as e:
                return False, str(e)
    
    def restart_server(self, username: str, server_name: str) -> Tuple[bool, str]:
        self.stop_server(username, server_name)
        time.sleep(1)
        return self.start_server(username, server_name)
    
    def get_process_info(self, username: str, server_name: str) -> Dict[str, Any]:
        key = f"{username}_{server_name}"
        info = {
            'running': False,
            'pid': None,
            'cpu_percent': 0.0,
            'memory_mb': 0.0,
            'uptime_seconds': 0,
            'status': 'stopped',
            'exit_code': None
        }
        
        with self.registry_lock:
            if key in self.registry:
                proc_data = self.registry[key]
                process = proc_data.get('process')
                
                if process and process.poll() is None:
                    try:
                        p = psutil.Process(process.pid)
                        info['running'] = True
                        info['pid'] = process.pid
                        info['cpu_percent'] = round(p.cpu_percent(interval=0.1), 2)
                        mem_info = p.memory_info()
                        info['memory_mb'] = round(mem_info.rss / (1024 * 1024), 2)
                        info['uptime_seconds'] = int(time.time() - proc_data['start_time'])
                        info['status'] = proc_data.get('status', 'running')
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        info['status'] = 'terminated'
                        info['exit_code'] = process.poll()
                else:
                    info['exit_code'] = process.poll() if process else proc_data.get('exit_code')
        
        return info
    
    def generate_console_stream(self, username: str, server_name: str) -> Generator[str, None, None]:
        key = f"{username}_{server_name}"
        
        while True:
            with self.registry_lock:
                if key not in self.registry:
                    yield f"data: [SERVER_NOT_RUNNING]\n\n"
                    break
                
                proc_data = self.registry[key]
                process = proc_data.get('process')
                q = proc_data.get('output_queue')
                
                if process and process.poll() is not None:
                    while q and not q.empty():
                        try:
                            line = q.get_nowait()
                            yield f"data: {line}\n\n"
                        except queue.Empty:
                            break
                    yield f"data: [PROCESS_ENDED]\n\n"
                    break
                
                if q:
                    temp_lines = []
                    while not q.empty():
                        try:
                            temp_lines.append(q.get_nowait())
                        except queue.Empty:
                            break
                    for line in temp_lines:
                        yield f"data: {line}\n\n"
                    for line in temp_lines:
                        try:
                            q.put_nowait(line)
                        except queue.Full:
                            pass
            
            time.sleep(0.1)

# ============================================================================
# FILE MANAGER
# ============================================================================
class FileManager:
    BLOCKED_NAMES = {'venv', '__pycache__', '.git', 'node_modules', '.env'}
    
    @staticmethod
    def get_server_path(username: str, server_name: str) -> Path:
        return Config.SERVERS_ROOT / username / server_name
    
    @classmethod
    def is_safe_path(cls, base_path: Path, target_path: Path) -> bool:
        try:
            resolved_base = base_path.resolve()
            resolved_target = target_path.resolve()
            return resolved_target.is_relative_to(resolved_base)
        except (ValueError, AttributeError):
            return str(resolved_base) in str(resolved_target) and str(resolved_target).startswith(str(resolved_base))
    
    @classmethod
    def list_directory(cls, username: str, server_name: str, subpath: str = '') -> List[Dict[str, Any]]:
        server_path = cls.get_server_path(username, server_name)
        target_path = server_path / subpath if subpath else server_path
        
        if not target_path.exists():
            return []
        
        if not cls.is_safe_path(server_path, target_path):
            return []
        
        items = []
        try:
            for entry in sorted(target_path.iterdir()):
                if entry.name in cls.BLOCKED_NAMES or entry.name.startswith('.'):
                    continue
                
                rel_path = str(entry.relative_to(server_path))
                stat = entry.stat()
                
                items.append({
                    'name': entry.name,
                    'path': rel_path,
                    'type': 'directory' if entry.is_dir() else 'file',
                    'size': stat.st_size if entry.is_file() else 0,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'editable': entry.suffix.lower() in {
                        '.py', '.js', '.html', '.css', '.json', '.txt', '.md',
                        '.yml', '.yaml', '.cfg', '.ini', '.conf', '.sh', '.xml', '.csv'
                    }
                })
        except PermissionError:
            pass
        
        return items
    
    @classmethod
    def read_file(cls, username: str, server_name: str, filepath: str) -> Tuple[Optional[str], Optional[str]]:
        server_path = cls.get_server_path(username, server_name)
        target_file = server_path / filepath
        
        if not target_file.exists() or not target_file.is_file():
            return None, "File not found"
        
        if not cls.is_safe_path(server_path, target_file):
            return None, "Access denied"
        
        try:
            content = target_file.read_text(encoding='utf-8')
            return content, None
        except Exception as e:
            return None, str(e)
    
    @classmethod
    def write_file(cls, username: str, server_name: str, filepath: str, content: str) -> Tuple[bool, str]:
        server_path = cls.get_server_path(username, server_name)
        target_file = server_path / filepath
        
        if not cls.is_safe_path(server_path, target_file):
            return False, "Access denied"
        
        try:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(content, encoding='utf-8')
            return True, "File saved successfully"
        except Exception as e:
            return False, str(e)
    
    @classmethod
    def create_file(cls, username: str, server_name: str, filepath: str) -> Tuple[bool, str]:
        server_path = cls.get_server_path(username, server_name)
        target_file = server_path / filepath
        
        if not cls.is_safe_path(server_path, target_file):
            return False, "Access denied"
        
        if target_file.exists():
            return False, "File already exists"
        
        try:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.touch()
            return True, "File created"
        except Exception as e:
            return False, str(e)
    
    @classmethod
    def create_directory(cls, username: str, server_name: str, dirpath: str) -> Tuple[bool, str]:
        server_path = cls.get_server_path(username, server_name)
        target_dir = server_path / dirpath
        
        if not cls.is_safe_path(server_path, target_dir):
            return False, "Access denied"
        
        if target_dir.exists():
            return False, "Directory already exists"
        
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            return True, "Directory created"
        except Exception as e:
            return False, str(e)
    
    @classmethod
    def delete_item(cls, username: str, server_name: str, itempath: str) -> Tuple[bool, str]:
        server_path = cls.get_server_path(username, server_name)
        target_path = server_path / itempath
        
        if not cls.is_safe_path(server_path, target_path):
            return False, "Access denied"
        
        if not target_path.exists():
            return False, "Item not found"
        
        if target_path.name in cls.BLOCKED_NAMES:
            return False, "Cannot delete protected item"
        
        try:
            if target_path.is_dir():
                shutil.rmtree(target_path)
            else:
                target_path.unlink()
            return True, "Deleted successfully"
        except Exception as e:
            return False, str(e)
    
    @classmethod
    def rename_item(cls, username: str, server_name: str, old_path: str, new_path: str) -> Tuple[bool, str]:
        server_path = cls.get_server_path(username, server_name)
        source = server_path / old_path
        destination = server_path / new_path
        
        if not cls.is_safe_path(server_path, source) or not cls.is_safe_path(server_path, destination):
            return False, "Access denied"
        
        if not source.exists():
            return False, "Source item not found"
        
        if destination.exists():
            return False, "Destination already exists"
        
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.rename(destination)
            return True, "Renamed successfully"
        except Exception as e:
            return False, str(e)
    
    @classmethod
    def upload_file(cls, username: str, server_name: str, file, subpath: str = '') -> Tuple[bool, str]:
        server_path = cls.get_server_path(username, server_name)
        upload_dir = server_path / subpath if subpath else server_path
        
        if not cls.is_safe_path(server_path, upload_dir):
            return False, "Access denied"
        
        if not file or not file.filename:
            return False, "No file selected"
        
        from werkzeug.utils import secure_filename
        filename = secure_filename(file.filename)
        if not filename:
            return False, "Invalid filename"
        
        try:
            upload_dir.mkdir(parents=True, exist_ok=True)
            file.save(str(upload_dir / filename))
            return True, f"File '{filename}' uploaded successfully"
        except Exception as e:
            return False, str(e)
    
    @classmethod
    def get_disk_usage(cls, username: str, server_name: str) -> Dict[str, Any]:
        server_path = cls.get_server_path(username, server_name)
        
        if not server_path.exists():
            return {'total_size': 0, 'file_count': 0, 'dir_count': 0}
        
        total_size = 0
        file_count = 0
        dir_count = 0
        
        try:
            for entry in server_path.rglob('*'):
                if entry.name in cls.BLOCKED_NAMES:
                    continue
                if entry.is_file():
                    total_size += entry.stat().st_size
                    file_count += 1
                elif entry.is_dir():
                    dir_count += 1
        except PermissionError:
            pass
        
        return {
            'total_size': total_size,
            'file_count': file_count,
            'dir_count': dir_count
        }

# ============================================================================
# AUDIT LOGGING
# ============================================================================
class AuditLogger:
    def __init__(self, db: JSONDatabase):
        self.db = db
    
    def log(self, username: str, action: str, status: str = "success", details: Dict = None):
        self.db.insert({
            'timestamp': datetime.now().isoformat(),
            'username': username,
            'action': action,
            'status': status,
            'ip_address': request.remote_addr if request else 'system',
            'user_agent': request.headers.get('User-Agent', '') if request else '',
            'details': details or {}
        })
    
    def get_recent(self, limit: int = 100) -> List[Dict]:
        logs = self.db.all()
        logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return logs[:limit]
    
    def get_failed_logins(self, limit: int = 50) -> List[Dict]:
        logs = self.db.query(action='login', status='failed')
        logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return logs[:limit]

# ============================================================================
# DECORATORS
# ============================================================================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login_page'))
        if session.get('user') != Config.ADMIN_USERNAME:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Admin access required'}), 403
            abort(403)
        return f(*args, **kwargs)
    return decorated

# ============================================================================
# CREATE FLASK APP
# ============================================================================
Config.init_directories()

app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_UPLOAD_SIZE
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=Config.SESSION_LIFETIME)

# Initialize managers
process_manager = ProcessManager()
file_manager = FileManager()
users_db = JSONDatabase(Config.USERS_FILE)
servers_db = JSONDatabase(Config.SERVERS_FILE)
logs_db = JSONDatabase(Config.LOGS_FILE)
audit = AuditLogger(logs_db)

# Ensure admin user exists
if not users_db.find_one(username=Config.ADMIN_USERNAME):
    users_db.insert({
        'username': Config.ADMIN_USERNAME,
        'password_hash': generate_password_hash(Config.ADMIN_PASSWORD),
        'tier': 'admin',
        'is_active': True,
        'email': 'admin@jagwar.host',
        'servers_count': 0
    })

# ============================================================================
# ROUTES - PUBLIC
# ============================================================================
@app.route('/')
def landing():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            return render_template('login.html', error="Username and password required")
        
        # Admin login
        if username == Config.ADMIN_USERNAME and password == Config.ADMIN_PASSWORD:
            session.clear()
            session['user'] = username
            session['tier'] = 'admin'
            session.permanent = True
            audit.log(username, 'login', 'success', {'method': 'admin'})
            return redirect(url_for('admin_panel'))
        
        # User login
        user = users_db.find_one(username=username)
        if not user:
            audit.log(username, 'login', 'failed', {'reason': 'user_not_found'})
            return render_template('login.html', error="Invalid credentials")
        
        if not user.get('is_active', True):
            audit.log(username, 'login', 'failed', {'reason': 'disabled'})
            return render_template('login.html', error="Account disabled")
        
        if check_password_hash(user['password_hash'], password):
            session.clear()
            session['user'] = username
            session['tier'] = user.get('tier', 'free')
            session.permanent = True
            users_db.update(user['id'], {'last_login': datetime.now().isoformat()})
            audit.log(username, 'login', 'success')
            return redirect(url_for('dashboard'))
        else:
            audit.log(username, 'login', 'failed', {'reason': 'wrong_password'})
            return render_template('login.html', error="Invalid credentials")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    if 'user' in session:
        audit.log(session['user'], 'logout', 'success')
    session.clear()
    return redirect(url_for('landing'))

# ============================================================================
# ROUTES - USER DASHBOARD
# ============================================================================
@app.route('/dashboard')
@login_required
def dashboard():
    username = session['user']
    if username == Config.ADMIN_USERNAME:
        return redirect(url_for('admin_panel'))
    
    user = users_db.find_one(username=username)
    servers = servers_db.query(username=username)
    
    # Enrich with process info
    for s in servers:
        s['process_info'] = process_manager.get_process_info(username, s['name'])
    
    max_servers = Config.MAX_PREMIUM_SERVERS if user.get('tier') == 'premium' else Config.MAX_DEFAULT_SERVERS
    
    return render_template('dashboard.html', 
                          username=username, 
                          servers=servers, 
                          max_servers=max_servers,
                          tier=user.get('tier', 'free'))

@app.route('/create_server', methods=['POST'])
@login_required
def create_server():
    username = session['user']
    if username == Config.ADMIN_USERNAME:
        return jsonify({'error': 'Admin cannot create servers'}), 403
    
    user = users_db.find_one(username=username)
    current = servers_db.count(username=username)
    max_servers = Config.MAX_PREMIUM_SERVERS if user.get('tier') == 'premium' else Config.MAX_DEFAULT_SERVERS
    
    if current >= max_servers:
        return jsonify({'error': f'Server limit reached ({max_servers})'}), 400
    
    server_name = request.form.get('server_name', '').strip()
    if not server_name or not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-_]*$', server_name):
        return jsonify({'error': 'Invalid server name'}), 400
    
    if servers_db.exists(username=username, name=server_name):
        return jsonify({'error': 'Server already exists'}), 400
    
    # Create environment
    success, msg = process_manager.create_server_environment(username, server_name)
    if not success:
        return jsonify({'error': msg}), 500
    
    # Save server record
    servers_db.insert({
        'username': username,
        'name': server_name,
        'language': 'python',
        'status': 'stopped'
    })
    
    users_db.update(user['id'], {'servers_count': current + 1})
    audit.log(username, 'create_server', 'success', {'server': server_name})
    
    return redirect(url_for('dashboard'))

@app.route('/delete_server/<server_name>', methods=['POST'])
@login_required
def delete_server(server_name):
    username = session['user']
    if username == Config.ADMIN_USERNAME:
        return jsonify({'error': 'Unauthorized'}), 403
    
    server = servers_db.find_one(username=username, name=server_name)
    if not server:
        return jsonify({'error': 'Server not found'}), 404
    
    process_manager.stop_server(username, server_name)
    
    server_path = Config.SERVERS_ROOT / username / server_name
    if server_path.exists():
        shutil.rmtree(server_path, ignore_errors=True)
    
    servers_db.delete(server['id'])
    
    user = users_db.find_one(username=username)
    if user:
        users_db.update(user['id'], {'servers_count': max(0, user.get('servers_count', 1) - 1)})
    
    audit.log(username, 'delete_server', 'success', {'server': server_name})
    return redirect(url_for('dashboard'))

# ============================================================================
# ROUTES - SERVER CONTROL
# ============================================================================
@app.route('/server/<server_name>')
@login_required
def server_control(server_name):
    username = session['user']
    if username == Config.ADMIN_USERNAME:
        return redirect(url_for('admin_panel'))
    
    server = servers_db.find_one(username=username, name=server_name)
    if not server:
        return "Server not found", 404
    
    server['process_info'] = process_manager.get_process_info(username, server_name)
    files = file_manager.list_directory(username, server_name)
    disk = file_manager.get_disk_usage(username, server_name)
    
    return render_template('server_control.html', 
                          server=server, 
                          files=files, 
                          disk_usage=disk,
                          username=username)

# ============================================================================
# API - SERVER LIFECYCLE
# ============================================================================
@app.route('/api/server/start/<server_name>', methods=['POST'])
@login_required
def api_start_server(server_name):
    username = session['user']
    server = servers_db.find_one(username=username, name=server_name)
    if not server:
        return jsonify({'error': 'Server not found'}), 404
    
    success, msg = process_manager.start_server(username, server_name)
    if success:
        servers_db.update(server['id'], {'status': 'running', 'last_started': datetime.now().isoformat()})
    
    return jsonify({'success': success, 'message': msg})

@app.route('/api/server/stop/<server_name>', methods=['POST'])
@login_required
def api_stop_server(server_name):
    username = session['user']
    server = servers_db.find_one(username=username, name=server_name)
    if not server:
        return jsonify({'error': 'Server not found'}), 404
    
    success, msg = process_manager.stop_server(username, server_name)
    if success:
        servers_db.update(server['id'], {'status': 'stopped'})
    
    return jsonify({'success': success, 'message': msg})

@app.route('/api/server/restart/<server_name>', methods=['POST'])
@login_required
def api_restart_server(server_name):
    username = session['user']
    server = servers_db.find_one(username=username, name=server_name)
    if not server:
        return jsonify({'error': 'Server not found'}), 404
    
    success, msg = process_manager.restart_server(username, server_name)
    if success:
        servers_db.update(server['id'], {'status': 'running'})
    
    return jsonify({'success': success, 'message': msg})

@app.route('/api/server/console/<server_name>')
@login_required
def api_console_stream(server_name):
    username = session['user']
    
    def generate():
        for line in process_manager.generate_console_stream(username, server_name):
            yield line
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive'
        }
    )

@app.route('/api/server/status/<server_name>')
@login_required
def api_server_status(server_name):
    username = session['user']
    return jsonify(process_manager.get_process_info(username, server_name))

# ============================================================================
# API - FILE MANAGEMENT
# ============================================================================
@app.route('/api/files/list/<server_name>')
@login_required
def api_list_files(server_name):
    username = session['user']
    subpath = request.args.get('path', '')
    return jsonify({
        'files': file_manager.list_directory(username, server_name, subpath),
        'disk_usage': file_manager.get_disk_usage(username, server_name)
    })

@app.route('/api/files/read/<server_name>', methods=['POST'])
@login_required
def api_read_file(server_name):
    username = session['user']
    data = request.get_json()
    content, error = file_manager.read_file(username, server_name, data.get('path', ''))
    if error:
        return jsonify({'error': error}), 400
    return jsonify({'content': content})

@app.route('/api/files/write/<server_name>', methods=['POST'])
@login_required
def api_write_file(server_name):
    username = session['user']
    data = request.get_json()
    success, msg = file_manager.write_file(username, server_name, data.get('path', ''), data.get('content', ''))
    if not success:
        return jsonify({'error': msg}), 400
    return jsonify({'message': msg})

@app.route('/api/files/create-file/<server_name>', methods=['POST'])
@login_required
def api_create_file(server_name):
    username = session['user']
    data = request.get_json()
    success, msg = file_manager.create_file(username, server_name, data.get('path', ''))
    if not success:
        return jsonify({'error': msg}), 400
    return jsonify({'message': msg})

@app.route('/api/files/create-folder/<server_name>', methods=['POST'])
@login_required
def api_create_folder(server_name):
    username = session['user']
    data = request.get_json()
    success, msg = file_manager.create_directory(username, server_name, data.get('path', ''))
    if not success:
        return jsonify({'error': msg}), 400
    return jsonify({'message': msg})

@app.route('/api/files/delete/<server_name>', methods=['POST'])
@login_required
def api_delete_item(server_name):
    username = session['user']
    data = request.get_json()
    success, msg = file_manager.delete_item(username, server_name, data.get('path', ''))
    if not success:
        return jsonify({'error': msg}), 400
    return jsonify({'message': msg})

@app.route('/api/files/rename/<server_name>', methods=['POST'])
@login_required
def api_rename_item(server_name):
    username = session['user']
    data = request.get_json()
    success, msg = file_manager.rename_item(username, server_name, data.get('old_path', ''), data.get('new_path', ''))
    if not success:
        return jsonify({'error': msg}), 400
    return jsonify({'message': msg})

@app.route('/api/files/upload/<server_name>', methods=['POST'])
@login_required
def api_upload_file(server_name):
    username = session['user']
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    subpath = request.form.get('path', '')
    success, msg = file_manager.upload_file(username, server_name, request.files['file'], subpath)
    if not success:
        return jsonify({'error': msg}), 400
    return jsonify({'message': msg})

# ============================================================================
# ROUTES - ADMIN PANEL
# ============================================================================
@app.route('/admin')
@admin_required
def admin_panel():
    users = users_db.all()
    servers = servers_db.all()
    activity = audit.get_recent(100)
    failed = audit.get_failed_logins(20)
    
    stats = {
        'total_users': len(users),
        'total_servers': len(servers),
        'active_servers': len([s for s in servers if s.get('status') == 'running']),
        'premium_users': len([u for u in users if u.get('tier') == 'premium']),
        'failed_logins': len(failed),
        'cpu': psutil.cpu_percent(),
        'memory': psutil.virtual_memory().percent,
        'disk': psutil.disk_usage('/').percent
    }
    
    return render_template('admin.html', 
                          users=users, 
                          servers=servers, 
                          activity=activity,
                          stats=stats)

@app.route('/admin/create_user', methods=['POST'])
@admin_required
def admin_create_user():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    email = request.form.get('email', '').strip()
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    if users_db.exists(username=username):
        return jsonify({'error': 'User already exists'}), 400
    
    users_db.insert({
        'username': username,
        'password_hash': generate_password_hash(password),
        'email': email,
        'tier': 'free',
        'is_active': True,
        'servers_count': 0
    })
    
    audit.log(session['user'], 'admin_create_user', 'success', {'created': username})
    return redirect(url_for('admin_panel'))

@app.route('/admin/toggle_premium/<username>', methods=['POST'])
@admin_required
def admin_toggle_premium(username):
    user = users_db.find_one(username=username)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    new_tier = 'free' if user.get('tier') == 'premium' else 'premium'
    users_db.update(user['id'], {'tier': new_tier})
    
    audit.log(session['user'], 'toggle_premium', 'success', {'user': username, 'new_tier': new_tier})
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_user/<username>', methods=['POST'])
@admin_required
def admin_delete_user(username):
    if username == Config.ADMIN_USERNAME:
        return jsonify({'error': 'Cannot delete admin'}), 400
    
    user = users_db.find_one(username=username)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Delete all user servers
    user_servers = servers_db.query(username=username)
    for s in user_servers:
        process_manager.stop_server(username, s['name'])
        server_path = Config.SERVERS_ROOT / username / s['name']
        if server_path.exists():
            shutil.rmtree(server_path, ignore_errors=True)
    
    servers_db.delete_where(username=username)
    
    user_dir = Config.SERVERS_ROOT / username
    if user_dir.exists():
        shutil.rmtree(user_dir, ignore_errors=True)
    
    users_db.delete(user['id'])
    
    audit.log(session['user'], 'admin_delete_user', 'success', {'deleted': username})
    return redirect(url_for('admin_panel'))

# ============================================================================
# ERROR HANDLERS
# ============================================================================
@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    return render_template('index.html'), 404

@app.errorhandler(500)
def server_error(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Server error'}), 500
    return render_template('index.html'), 500

# ============================================================================
# CONTEXT PROCESSOR
# ============================================================================
@app.context_processor
def inject_globals():
    return {
        'app_name': Config.APP_NAME,
        'footer_text': 'جميع الحقوق محفوظة JAGWAR 2026'
    }

# ============================================================================
# MAIN
# ============================================================================
if __name__ == '__main__':
    import re
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
