import sqlite3
import hashlib
import os

def get_db_connection():
    conn = sqlite3.connect('bot_users.db')
    conn.row_factory = sqlite3.Row
    return conn
def setup_database():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password BLOB NOT NULL,
            email TEXT,
            discord_id INTEGER,
            quiz_results TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def hash_password(password):
    """Şifreyi hash'le"""
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt + key

def verify_password(stored_password, provided_password):
    """Hash'lenmiş şifreyi doğrula"""
    salt = stored_password[:32]
    stored_key = stored_password[32:]
    key = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 100000)
    return key == stored_key

def register_user(username, password, email, discord_id):
    """Yeni kullanıcı kaydı"""
    try:
        conn = get_db_connection()
        hashed_password = hash_password(password)
        conn.execute('INSERT INTO users (username, password, email, discord_id) VALUES (?, ?, ?, ?)',
                    (username, hashed_password, email, discord_id))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        # Kullanıcı adı zaten var
        return False

def verify_user(username, password):
    """Kullanıcı doğrulama"""
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    
    if user and verify_password(user['password'], password):
        return True
    return False