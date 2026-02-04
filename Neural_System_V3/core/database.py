# core/database.py
import sqlite3
from datetime import datetime

class NeuralDB:
    def __init__(self, db_name):
        self.db_name = db_name
        self._init_tables()

    def _get_conn(self):
        return sqlite3.connect(self.db_name)

    def _init_tables(self):
        with self._get_conn() as conn:
            c = conn.cursor()
            # Session 表：存储输入和生成的文章
            c.execute('''CREATE TABLE IF NOT EXISTS learning_sessions
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          words_input TEXT,
                          article_english TEXT,
                          article_chinese TEXT,
                          quiz_data TEXT, 
                          created_at TIMESTAMP)''')
            # Words 表：存储单词卡片
            c.execute('''CREATE TABLE IF NOT EXISTS session_words
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          session_id INTEGER,
                          word TEXT,
                          meaning TEXT,
                          root_explanation TEXT,
                          imagery_desc TEXT,
                          is_core BOOLEAN,
                          FOREIGN KEY(session_id) REFERENCES learning_sessions(id))''')
            conn.commit()

    def create_session(self, words_input):
        with self._get_conn() as conn:
            c = conn.cursor()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute("INSERT INTO learning_sessions (words_input, created_at) VALUES (?, ?)", 
                      (words_input, current_time))
            return c.lastrowid

    def update_article(self, session_id, en, cn):
        with self._get_conn() as conn:
            conn.execute("UPDATE learning_sessions SET article_english = ?, article_chinese = ? WHERE id = ?", 
                         (en, cn, session_id))

    def update_quiz(self, session_id, quiz_json_str):
        with self._get_conn() as conn:
            conn.execute("UPDATE learning_sessions SET quiz_data = ? WHERE id = ?", 
                         (quiz_json_str, session_id))

    def save_words(self, session_id, words_data):
        with self._get_conn() as conn:
            # 先清空旧的（防止重复生成时堆积）
            conn.execute("DELETE FROM session_words WHERE session_id = ?", (session_id,))
            for w in words_data:
                conn.execute('''INSERT INTO session_words 
                             (session_id, word, meaning, root_explanation, imagery_desc, is_core) 
                             VALUES (?, ?, ?, ?, ?, ?)''', 
                             (session_id, w['word'], w['meaning'], w['root'], w['imagery'], w['is_core']))

    def get_history_list(self):
        """获取最近 10 条历史记录用于侧边栏展示"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT id, words_input, created_at FROM learning_sessions ORDER BY id DESC LIMIT 10")
            return c.fetchall()

    def load_session(self, session_id):
        """完整恢复一个 Session 的所有数据 (已修复字段映射问题)"""
        data = {}
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row # 允许通过列名访问
            c = conn.cursor()
            
            # 1. Load Session Info (Article & Quiz)
            c.execute("SELECT * FROM learning_sessions WHERE id = ?", (session_id,))
            sess = c.fetchone()
            if sess:
                data['info'] = dict(sess)
            
            # 2. Load Words
            c.execute("SELECT * FROM session_words WHERE session_id = ?", (session_id,))
            words = c.fetchall()
            
            # 关键修复：手动将数据库列名映射回前端需要的 JSON key
            cleaned_words = []
            for w in words:
                w_dict = dict(w)
                # 数据库列名 -> 前端使用的 Key
                w_dict['root'] = w_dict.get('root_explanation', '') # 映射 root
                w_dict['imagery'] = w_dict.get('imagery_desc', '')  # 映射 imagery
                cleaned_words.append(w_dict)
                
            data['words'] = cleaned_words
            
        return data
