# ==========================================
# 🗄️ 数据库持久化层
# ==========================================
import sqlite3
import json
import sys
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

# 添加当前目录到路径
_current_dir = Path(__file__).parent
if str(_current_dir) not in sys.path:
    sys.path.insert(0, str(_current_dir))

from config import DB_NAME, DEFAULT_REVIEW_WORDS


class GameDB:
    """管理玩家金币、已掌握词汇(Deck)、爬塔历史"""
    
    def __init__(self, db_name=None):
        self.db_name = db_name or DB_NAME
        self._init_tables()
    
    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_tables(self):
        with self._get_conn() as conn:
            c = conn.cursor()
            # 玩家表
            c.execute('''CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT DEFAULT 'Adventurer',
                gold INTEGER DEFAULT 0,
                total_runs INTEGER DEFAULT 0,
                victories INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_played TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            # 已掌握词汇表 (Deck)
            c.execute('''CREATE TABLE IF NOT EXISTS deck (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER,
                word TEXT,
                meaning TEXT,
                mastered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(player_id) REFERENCES players(id)
            )''')
            # 爬塔历史
            c.execute('''CREATE TABLE IF NOT EXISTS run_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER,
                floor_reached INTEGER,
                victory BOOLEAN,
                words_learned TEXT,
                ended_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(player_id) REFERENCES players(id)
            )''')
            conn.commit()
    
    def get_or_create_player(self) -> dict:
        """获取或创建默认玩家"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM players LIMIT 1")
            player = c.fetchone()
            if player:
                return dict(player)
            c.execute("INSERT INTO players DEFAULT VALUES")
            player_id = c.lastrowid
            return {"id": player_id, "name": "Adventurer", "gold": 0, "total_runs": 0, "victories": 0}
    
    def update_gold(self, player_id: int, gold_amount: int):
        with self._get_conn() as conn:
            conn.execute("UPDATE players SET gold = ?, last_played = CURRENT_TIMESTAMP WHERE id = ?", 
                        (gold_amount, player_id))
    
    def add_to_deck(self, player_id: int, word: str, meaning: str):
        """添加已掌握的词汇到 Deck"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM deck WHERE player_id = ? AND word = ?", (player_id, word))
            if not c.fetchone():
                conn.execute("INSERT INTO deck (player_id, word, meaning) VALUES (?, ?, ?)",
                           (player_id, word, meaning))
    
    def get_review_words(self, player_id: int, count: int = 10) -> list:
        """从 Deck 获取复习词，不足时用默认词补充"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT word, meaning FROM deck WHERE player_id = ? ORDER BY RANDOM() LIMIT ?",
                     (player_id, count))
            words = [{"word": row["word"], "meaning": row["meaning"], "is_review": True} for row in c.fetchall()]
        
        # 不足时用默认词补充
        if len(words) < count:
            needed = count - len(words)
            existing_words = {w["word"] for w in words}
            for dw in DEFAULT_REVIEW_WORDS:
                if dw["word"] not in existing_words and needed > 0:
                    words.append({**dw, "is_review": True})
                    needed -= 1
        
        return words[:count]
    
    def get_deck_count(self, player_id: int) -> int:
        """获取 Deck 中词汇数量"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM deck WHERE player_id = ?", (player_id,))
            return c.fetchone()[0]
    
    def record_run(self, player_id: int, floor_reached: int, victory: bool, words_learned: list):
        """记录一次爬塔"""
        with self._get_conn() as conn:
            conn.execute("""INSERT INTO run_history (player_id, floor_reached, victory, words_learned) 
                           VALUES (?, ?, ?, ?)""",
                        (player_id, floor_reached, victory, json.dumps(words_learned, ensure_ascii=False)))
            if victory:
                conn.execute("UPDATE players SET total_runs = total_runs + 1, victories = victories + 1 WHERE id = ?",
                           (player_id,))
            else:
                conn.execute("UPDATE players SET total_runs = total_runs + 1 WHERE id = ?", (player_id,))
