# ==========================================
# 🗄️ 数据库持久化层
# ==========================================
import sqlite3
import json
import random
import sys
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

# 添加当前目录到路径
_current_dir = Path(__file__).parent
if str(_current_dir) not in sys.path:
    sys.path.insert(0, str(_current_dir))

from config import DB_NAME, DEFAULT_REVIEW_WORDS
from models import WordTier, REVIEW_INTERVALS


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
            
            # 已掌握词汇表 (Deck) - 包含莱特纳熟练度
            c.execute('''CREATE TABLE IF NOT EXISTS deck (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER,
                word TEXT,
                meaning TEXT,
                tier INTEGER DEFAULT 0,
                correct_streak INTEGER DEFAULT 0,
                last_seen_room INTEGER DEFAULT 0,
                next_review_room INTEGER DEFAULT 0,
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
            
            # 全局干扰词库 (用于生成选项)
            c.execute('''CREATE TABLE IF NOT EXISTS distractor_pool (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT UNIQUE,
                meaning TEXT,
                pos TEXT DEFAULT 'unknown'
            )''')
            
            conn.commit()
            
            # 初始化干扰词库
            self._init_distractor_pool(conn)
    
    def _init_distractor_pool(self, conn):
        """初始化干扰词库"""
        distractors = [
            ("Ambiguous", "模糊的，有歧义的", "adj"),
            ("Compelling", "令人信服的，引人注目的", "adj"),
            ("Deteriorate", "恶化，变坏", "v"),
            ("Eloquent", "雄辩的，有说服力的", "adj"),
            ("Formidable", "令人敬畏的，可怕的", "adj"),
            ("Gratify", "使满足，使高兴", "v"),
            ("Hierarchy", "等级制度", "n"),
            ("Imminent", "即将发生的", "adj"),
            ("Jeopardize", "危及，损害", "v"),
            ("Keen", "敏锐的，热衷的", "adj"),
            ("Lethargic", "昏昏欲睡的", "adj"),
            ("Meticulous", "一丝不苟的", "adj"),
            ("Nonchalant", "漠不关心的", "adj"),
            ("Obsolete", "过时的", "adj"),
            ("Pragmatic", "务实的", "adj"),
            ("Resilient", "有弹性的，坚韧的", "adj"),
            ("Scrutinize", "仔细检查", "v"),
            ("Tenacious", "顽强的，坚持的", "adj"),
            ("Ubiquitous", "无处不在的", "adj"),
            ("Volatile", "易变的，不稳定的", "adj"),
            ("Whimsical", "古怪的，异想天开的", "adj"),
            ("Zealous", "热情的，狂热的", "adj"),
            ("Acquiesce", "默许，顺从", "v"),
            ("Belligerent", "好斗的", "adj"),
            ("Cacophony", "刺耳的声音", "n"),
            ("Delineate", "描绘，勾画", "v"),
            ("Ephemeral", "短暂的", "adj"),
            ("Frivolous", "轻浮的", "adj"),
            ("Gregarious", "合群的，爱社交的", "adj"),
            ("Haughty", "傲慢的", "adj"),
        ]
        
        c = conn.cursor()
        for word, meaning, pos in distractors:
            try:
                c.execute("INSERT OR IGNORE INTO distractor_pool (word, meaning, pos) VALUES (?, ?, ?)",
                         (word, meaning, pos))
            except:
                pass
    
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
    
    # ==========================================
    # 莱特纳系统方法
    # ==========================================
    
    def add_or_update_word(self, player_id: int, word: str, meaning: str, tier: int = 0):
        """添加或更新词汇"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT id, tier FROM deck WHERE player_id = ? AND word = ?", (player_id, word))
            existing = c.fetchone()
            
            if existing:
                # 只更新释义，不覆盖熟练度
                conn.execute("UPDATE deck SET meaning = ? WHERE id = ?", (meaning, existing['id']))
            else:
                conn.execute("""INSERT INTO deck 
                    (player_id, word, meaning, tier, correct_streak) 
                    VALUES (?, ?, ?, ?, 0)""",
                    (player_id, word, meaning, tier))
    
    def update_word_tier(self, player_id: int, word: str, correct: bool, current_room: int):
        """
        更新单词熟练度
        
        算法：
        - 答对：tier += 1, correct_streak += 1
        - 答错：tier = max(1, tier - 1), correct_streak = 0
        """
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT id, tier, correct_streak FROM deck WHERE player_id = ? AND word = ?", 
                     (player_id, word))
            row = c.fetchone()
            
            if not row:
                return
            
            current_tier = row['tier']
            streak = row['correct_streak']
            
            if correct:
                new_tier = min(WordTier.ARCHIVED.value, current_tier + 1)
                new_streak = streak + 1
            else:
                new_tier = max(WordTier.BLURRY.value, current_tier - 1)
                new_streak = 0
            
            # 计算下次复习房间
            next_review = self._calculate_next_review(WordTier(new_tier), current_room)
            
            conn.execute("""UPDATE deck SET 
                tier = ?, correct_streak = ?, last_seen_room = ?, next_review_room = ?
                WHERE id = ?""",
                (new_tier, new_streak, current_room, next_review, row['id']))
    
    def _calculate_next_review(self, tier: WordTier, current_room: int) -> int:
        """计算下次复习房间号"""
        if tier == WordTier.ARCHIVED:
            return 999999  # 封存词不再复习
        
        interval = REVIEW_INTERVALS.get(tier, (10, 20))
        offset = random.randint(interval[0], interval[1])
        return current_room + offset
    
    def get_words_by_tier(self, player_id: int, tier: WordTier, count: int = 10) -> list:
        """按熟练度等级获取词汇"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("""SELECT word, meaning, tier, correct_streak, last_seen_room, next_review_room 
                        FROM deck WHERE player_id = ? AND tier = ? 
                        ORDER BY RANDOM() LIMIT ?""",
                     (player_id, tier.value, count))
            return [dict(row) for row in c.fetchall()]
    
    def get_due_review_words(self, player_id: int, current_room: int, count: int = 10) -> list:
        """获取到期需要复习的词汇"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("""SELECT word, meaning, tier, correct_streak, last_seen_room, next_review_room 
                        FROM deck WHERE player_id = ? AND tier > 0 AND tier < 5 
                        AND next_review_room <= ?
                        ORDER BY tier ASC, next_review_room ASC LIMIT ?""",
                     (player_id, current_room, count))
            return [dict(row) for row in c.fetchall()]
    
    def get_review_words(self, player_id: int, count: int = 10) -> list:
        """从 Deck 获取复习词，不足时用默认词补充"""
        with self._get_conn() as conn:
            c = conn.cursor()
            # 优先获取 tier 1-3 的词（需要复习的）
            c.execute("""SELECT word, meaning, tier FROM deck 
                        WHERE player_id = ? AND tier > 0 AND tier < 5
                        ORDER BY tier ASC, RANDOM() LIMIT ?""",
                     (player_id, count))
            words = [{
                "word": row["word"], 
                "meaning": row["meaning"], 
                "tier": row["tier"],
                "is_review": True
            } for row in c.fetchall()]
        
        # 不足时用默认词补充
        if len(words) < count:
            needed = count - len(words)
            existing_words = {w["word"] for w in words}
            for dw in DEFAULT_REVIEW_WORDS:
                if dw["word"] not in existing_words and needed > 0:
                    words.append({**dw, "tier": 1, "is_review": True})
                    needed -= 1
        
        return words[:count]
    
    def get_distractors(self, correct_meaning: str, count: int = 3) -> list:
        """
        获取干扰选项（真实释义）
        排除正确答案
        """
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("""SELECT meaning FROM distractor_pool 
                        WHERE meaning != ? 
                        ORDER BY RANDOM() LIMIT ?""",
                     (correct_meaning, count))
            return [row['meaning'] for row in c.fetchall()]
    
    def add_to_distractor_pool(self, word: str, meaning: str, pos: str = "unknown"):
        """添加词汇到干扰词库"""
        if not meaning or meaning == "待学习":
            return
        with self._get_conn() as conn:
            try:
                conn.execute("INSERT OR IGNORE INTO distractor_pool (word, meaning, pos) VALUES (?, ?, ?)",
                           (word, meaning, pos))
            except:
                pass
    
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
