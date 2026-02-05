# ==========================================
# 🗄️ 数据库持久化层 - v5.4
# ==========================================
import sqlite3
import json
import random
import sys
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
from typing import List, Optional

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
            
            # 词汇表 (Grimoire) - v5.4 结构
            c.execute('''CREATE TABLE IF NOT EXISTS deck (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER,
                word TEXT,
                meaning TEXT,
                tier INTEGER DEFAULT 0,
                consecutive_correct INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                priority TEXT DEFAULT 'normal',
                last_seen_room INTEGER DEFAULT 0,
                next_review_room INTEGER DEFAULT 0,
                mastered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(player_id) REFERENCES players(id)
            )''')
            
            # 迁移旧表
            self._migrate_deck_table(c)
            self._migrate_run_history_table(c)
            
            # 爬塔历史/存档
            c.execute('''CREATE TABLE IF NOT EXISTS run_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER,
                floor_reached INTEGER,
                victory BOOLEAN,
                words_learned TEXT,
                deck_snapshot TEXT,
                in_progress BOOLEAN DEFAULT FALSE,
                ended_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(player_id) REFERENCES players(id)
            )''')
            
            # 全局干扰词库
            c.execute('''CREATE TABLE IF NOT EXISTS distractor_pool (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT UNIQUE,
                meaning TEXT,
                pos TEXT DEFAULT 'unknown'
            )''')
            
            conn.commit()
            self._init_distractor_pool(conn)
    
    def _migrate_deck_table(self, cursor):
        """迁移旧版 deck 表"""
        cursor.execute("PRAGMA table_info(deck)")
        columns = {row[1] for row in cursor.fetchall()}
        
        migrations = [
            ("tier", "INTEGER DEFAULT 0"),
            ("consecutive_correct", "INTEGER DEFAULT 0"),
            ("error_count", "INTEGER DEFAULT 0"),
            ("priority", "TEXT DEFAULT 'normal'"),
            ("last_seen_room", "INTEGER DEFAULT 0"),
            ("next_review_room", "INTEGER DEFAULT 0"),
        ]
        
        for col_name, col_def in migrations:
            if col_name not in columns:
                try:
                    cursor.execute(f"ALTER TABLE deck ADD COLUMN {col_name} {col_def}")
                except Exception:
                    pass
    
    def _migrate_run_history_table(self, cursor):
        """迁移旧版 run_history 表"""
        cursor.execute("PRAGMA table_info(run_history)")
        columns = {row[1] for row in cursor.fetchall()}
        
        migrations = [
            ("in_progress", "BOOLEAN DEFAULT FALSE"),
            ("deck_snapshot", "TEXT"),
        ]
        
        for col_name, col_def in migrations:
            if col_name not in columns:
                try:
                    cursor.execute(f"ALTER TABLE run_history ADD COLUMN {col_name} {col_def}")
                except Exception:
                    pass
    
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
            ("Ephemeral", "短暂的", "adj"),
            ("Cacophony", "刺耳的声音", "n"),
        ]
        
        c = conn.cursor()
        for word, meaning, pos in distractors:
            try:
                c.execute("INSERT OR IGNORE INTO distractor_pool (word, meaning, pos) VALUES (?, ?, ?)",
                         (word, meaning, pos))
            except:
                pass
    
    # ==========================================
    # 玩家管理
    # ==========================================
    
    def get_or_create_player(self) -> dict:
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM players LIMIT 1")
            player = c.fetchone()
            if player:
                return dict(player)
            c.execute("INSERT INTO players DEFAULT VALUES")
            return {"id": c.lastrowid, "name": "Adventurer", "gold": 0, "total_runs": 0, "victories": 0}
    
    def update_gold(self, player_id: int, gold_amount: int):
        with self._get_conn() as conn:
            conn.execute("UPDATE players SET gold = ?, last_played = CURRENT_TIMESTAMP WHERE id = ?", 
                        (gold_amount, player_id))
    
    # ==========================================
    # 词汇管理 (Grimoire)
    # ==========================================
    
    def add_word(self, player_id: int, word: str, meaning: str, 
                 tier: int = 0, priority: str = "normal") -> int:
        """添加新词到词库"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM deck WHERE player_id = ? AND word = ?", (player_id, word))
            existing = c.fetchone()
            
            if existing:
                conn.execute("UPDATE deck SET meaning = ?, priority = ? WHERE id = ?", 
                           (meaning, priority, existing['id']))
                return existing['id']
            else:
                c.execute("""INSERT INTO deck 
                    (player_id, word, meaning, tier, consecutive_correct, priority) 
                    VALUES (?, ?, ?, ?, 0, ?)""",
                    (player_id, word, meaning, tier, priority))
                return c.lastrowid
    
    def add_words_batch(self, player_id: int, words: List[dict], priority: str = "pinned"):
        """批量添加词汇 (用于 Word Library 输入)"""
        for w in words:
            self.add_word(player_id, w['word'], w.get('meaning', ''), 
                         tier=0, priority=priority)
    
    def get_words_by_tier_range(self, player_id: int, min_tier: int, max_tier: int, count: int = 50) -> list:
        """按熟练度范围获取词汇"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("""SELECT word, meaning, tier, consecutive_correct, priority, error_count
                        FROM deck WHERE player_id = ? AND tier >= ? AND tier <= ?
                        ORDER BY priority DESC, RANDOM() LIMIT ?""",
                     (player_id, min_tier, max_tier, count))
            return [dict(row) for row in c.fetchall()]
    
    def get_all_words(self, player_id: int) -> dict:
        """获取所有词汇，按颜色分类"""
        return {
            "red": self.get_words_by_tier_range(player_id, 0, 1, 100),
            "blue": self.get_words_by_tier_range(player_id, 2, 3, 100),
            "gold": self.get_words_by_tier_range(player_id, 4, 5, 100),
        }
    
    # ==========================================
    # 智能推荐 (Recommender)
    # ==========================================
    
    def get_draft_candidates(self, player_id: int, count: int = 3) -> list:
        """
        获取战后抓牌候选词
        优先级: PINNED > GHOST > RANDOM
        """
        candidates = []
        
        with self._get_conn() as conn:
            c = conn.cursor()
            
            # Priority 1: PINNED (用户新输入)
            c.execute("""SELECT word, meaning, tier, priority FROM deck 
                        WHERE player_id = ? AND tier <= 1 AND priority = 'pinned'
                        ORDER BY id DESC LIMIT ?""",
                     (player_id, count))
            pinned = [dict(row) for row in c.fetchall()]
            candidates.extend(pinned)
            
            if len(candidates) >= count:
                return candidates[:count]
            
            # Priority 2: GHOST (高错误率)
            remaining = count - len(candidates)
            existing_words = {c['word'] for c in candidates}
            c.execute("""SELECT word, meaning, tier, priority FROM deck 
                        WHERE player_id = ? AND tier <= 1 AND priority = 'ghost'
                        AND word NOT IN ({})
                        ORDER BY error_count DESC LIMIT ?""".format(
                            ','.join('?' * len(existing_words)) if existing_words else '""'
                        ),
                     (player_id, *existing_words, remaining) if existing_words else (player_id, remaining))
            ghost = [dict(row) for row in c.fetchall()]
            candidates.extend(ghost)
            
            if len(candidates) >= count:
                return candidates[:count]
            
            # Priority 3: RANDOM (剩余 Lv0)
            remaining = count - len(candidates)
            existing_words = {c['word'] for c in candidates}
            placeholders = ','.join('?' * len(existing_words)) if existing_words else '""'
            
            c.execute(f"""SELECT word, meaning, tier, priority FROM deck 
                        WHERE player_id = ? AND tier <= 1 
                        AND word NOT IN ({placeholders})
                        ORDER BY RANDOM() LIMIT ?""",
                     (player_id, *existing_words, remaining) if existing_words else (player_id, remaining))
            random_words = [dict(row) for row in c.fetchall()]
            candidates.extend(random_words)
        
        return candidates[:count]
    
    def get_game_pool(self, player_id: int, red: int = 25, blue: int = 12, gold: int = 5) -> list:
        """
        获取本局游戏的单词池
        默认: 25红 + 12蓝 + 5金 = 42张
        """
        pool = []
        
        with self._get_conn() as conn:
            c = conn.cursor()
            
            # Red cards (Lv0-1)
            c.execute("""SELECT word, meaning, tier, consecutive_correct, priority FROM deck 
                        WHERE player_id = ? AND tier <= 1
                        ORDER BY priority DESC, RANDOM() LIMIT ?""",
                     (player_id, red))
            pool.extend([dict(row) for row in c.fetchall()])
            
            # Blue cards (Lv2-3)
            c.execute("""SELECT word, meaning, tier, consecutive_correct, priority FROM deck 
                        WHERE player_id = ? AND tier >= 2 AND tier <= 3
                        ORDER BY RANDOM() LIMIT ?""",
                     (player_id, blue))
            pool.extend([dict(row) for row in c.fetchall()])
            
            # Gold cards (Lv4-5)
            c.execute("""SELECT word, meaning, tier, consecutive_correct, priority FROM deck 
                        WHERE player_id = ? AND tier >= 4
                        ORDER BY RANDOM() LIMIT ?""",
                     (player_id, gold))
            pool.extend([dict(row) for row in c.fetchall()])
        
        # 如果不够，用任意词补充
        total_needed = red + blue + gold
        if len(pool) < total_needed:
            existing = {w['word'] for w in pool}
            with self._get_conn() as conn:
                c = conn.cursor()
                placeholders = ','.join('?' * len(existing)) if existing else '""'
                c.execute(f"""SELECT word, meaning, tier, consecutive_correct, priority FROM deck 
                            WHERE player_id = ? AND word NOT IN ({placeholders})
                            ORDER BY RANDOM() LIMIT ?""",
                         (player_id, *existing, total_needed - len(pool)) if existing else (player_id, total_needed - len(pool)))
                pool.extend([dict(row) for row in c.fetchall()])
        
        return pool
    
    def get_initial_deck_from_pool(self, pool: list, red: int = 6, blue: int = 2, gold: int = 1) -> list:
        """
        从游戏池中抽取初始卡组
        默认: 6红 + 2蓝 + 1金 = 9张
        """
        import random
        
        red_cards = [w for w in pool if w.get('tier', 0) <= 1]
        blue_cards = [w for w in pool if 2 <= w.get('tier', 0) <= 3]
        gold_cards = [w for w in pool if w.get('tier', 0) >= 4]
        
        deck = []
        deck.extend(random.sample(red_cards, min(red, len(red_cards))))
        deck.extend(random.sample(blue_cards, min(blue, len(blue_cards))))
        deck.extend(random.sample(gold_cards, min(gold, len(gold_cards))))
        
        # 补足数量
        total_needed = red + blue + gold
        if len(deck) < total_needed:
            remaining = [w for w in pool if w not in deck]
            random.shuffle(remaining)
            deck.extend(remaining[:total_needed - len(deck)])
        
        return deck
    
    def get_initial_deck(self, player_id: int) -> list:
        """
        获取初始卡组
        5 Red (Lv0-1) + 2 Blue (Lv2-3) + 1 Gold (Lv4-5)
        """
        deck = []
        
        with self._get_conn() as conn:
            c = conn.cursor()
            
            # 5 Red cards (Lv0-1)
            c.execute("""SELECT word, meaning, tier, consecutive_correct, priority FROM deck 
                        WHERE player_id = ? AND tier <= 1
                        ORDER BY priority DESC, RANDOM() LIMIT 5""",
                     (player_id,))
            red_cards = [dict(row) for row in c.fetchall()]
            deck.extend(red_cards)
            
            # 2 Blue cards (Lv2-3)
            c.execute("""SELECT word, meaning, tier, consecutive_correct, priority FROM deck 
                        WHERE player_id = ? AND tier >= 2 AND tier <= 3
                        ORDER BY RANDOM() LIMIT 2""",
                     (player_id,))
            blue_cards = [dict(row) for row in c.fetchall()]
            deck.extend(blue_cards)
            
            # 1 Gold card (Lv4-5)
            c.execute("""SELECT word, meaning, tier, consecutive_correct, priority FROM deck 
                        WHERE player_id = ? AND tier >= 4
                        ORDER BY RANDOM() LIMIT 1""",
                     (player_id,))
            gold_cards = [dict(row) for row in c.fetchall()]
            deck.extend(gold_cards)
        
        # 如果不足 8 张，用 Lv0 补充
        if len(deck) < 8:
            needed = 8 - len(deck)
            existing = {d['word'] for d in deck}
            
            with self._get_conn() as conn:
                c = conn.cursor()
                placeholders = ','.join('?' * len(existing)) if existing else '""'
                c.execute(f"""SELECT word, meaning, tier, consecutive_correct, priority FROM deck 
                            WHERE player_id = ? AND word NOT IN ({placeholders})
                            ORDER BY tier ASC, RANDOM() LIMIT ?""",
                         (player_id, *existing, needed) if existing else (player_id, needed))
                extra = [dict(row) for row in c.fetchall()]
                deck.extend(extra)
        
        return deck[:8]
    
    # ==========================================
    # 升级判定
    # ==========================================
    
    def update_word_progress(self, player_id: int, word: str, correct: bool, current_room: int = 0):
        """
        更新单词进度
        
        升级判定:
        - Red -> Blue: consecutive_correct >= 3
        - Blue -> Gold: consecutive_correct >= 5
        """
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT id, tier, consecutive_correct, error_count FROM deck WHERE player_id = ? AND word = ?", 
                     (player_id, word))
            row = c.fetchone()
            
            if not row:
                return None
            
            current_tier = row['tier'] or 0
            streak = row['consecutive_correct'] or 0
            errors = row['error_count'] or 0
            
            if correct:
                new_streak = streak + 1
                new_tier = current_tier
                
                # 升级判定
                if current_tier <= 1 and new_streak >= 2:
                    new_tier = 2  # Red -> Blue
                    new_streak = 0  # 重置连击
                elif current_tier in [2, 3] and new_streak >= 3:
                    new_tier = 4  # Blue -> Gold
                    new_streak = 0
                
                conn.execute("""UPDATE deck SET 
                    tier = ?, consecutive_correct = ?, last_seen_room = ?, priority = 'normal'
                    WHERE id = ?""",
                    (new_tier, new_streak, current_room, row['id']))
                
                return {"upgraded": new_tier > current_tier, "new_tier": new_tier}
            else:
                # 答错: 降级 + 标记为 GHOST
                new_tier = max(0, current_tier - 1)
                new_errors = errors + 1
                
                conn.execute("""UPDATE deck SET 
                    tier = ?, consecutive_correct = 0, error_count = ?, 
                    priority = 'ghost', last_seen_room = ?
                    WHERE id = ?""",
                    (new_tier, new_errors, current_room, row['id']))
                
                return {"upgraded": False, "new_tier": new_tier, "downgraded": new_tier < current_tier}
    
    # ==========================================
    # 存档系统
    # ==========================================
    
    def save_run_state(self, player_id: int, floor: int, deck: list, in_progress: bool = True):
        """保存游戏进度"""
        with self._get_conn() as conn:
            # 先清除旧的进行中存档
            conn.execute("UPDATE run_history SET in_progress = FALSE WHERE player_id = ? AND in_progress = TRUE",
                        (player_id,))
            
            conn.execute("""INSERT INTO run_history 
                (player_id, floor_reached, victory, deck_snapshot, in_progress)
                VALUES (?, ?, FALSE, ?, ?)""",
                (player_id, floor, json.dumps(deck, ensure_ascii=False), in_progress))
    
    def get_continue_state(self, player_id: int) -> Optional[dict]:
        """获取可继续的存档"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("""SELECT * FROM run_history 
                        WHERE player_id = ? AND in_progress = TRUE
                        ORDER BY id DESC LIMIT 1""",
                     (player_id,))
            row = c.fetchone()
            if row:
                return {
                    "floor": row['floor_reached'],
                    "deck": json.loads(row['deck_snapshot']) if row['deck_snapshot'] else []
                }
            return None
    
    def end_run(self, player_id: int, floor: int, victory: bool, words: list):
        """结束游戏"""
        with self._get_conn() as conn:
            # 清除进行中存档
            conn.execute("UPDATE run_history SET in_progress = FALSE WHERE player_id = ?", (player_id,))
            
            # 记录结果
            conn.execute("""INSERT INTO run_history 
                (player_id, floor_reached, victory, words_learned, in_progress)
                VALUES (?, ?, ?, ?, FALSE)""",
                (player_id, floor, victory, json.dumps(words, ensure_ascii=False)))
            
            if victory:
                conn.execute("UPDATE players SET total_runs = total_runs + 1, victories = victories + 1 WHERE id = ?",
                           (player_id,))
            else:
                conn.execute("UPDATE players SET total_runs = total_runs + 1 WHERE id = ?", (player_id,))
    
    # ==========================================
    # 兼容旧方法
    # ==========================================
    
    def add_or_update_word(self, player_id: int, word: str, meaning: str, tier: int = 0):
        return self.add_word(player_id, word, meaning, tier)
    
    def update_word_tier(self, player_id: int, word: str, correct: bool, current_room: int):
        return self.update_word_progress(player_id, word, correct, current_room)
    
    def get_review_words(self, player_id: int, count: int = 10) -> list:
        """兼容旧方法"""
        words = self.get_words_by_tier_range(player_id, 1, 3, count)
        if len(words) < count:
            extra = self.get_words_by_tier_range(player_id, 0, 0, count - len(words))
            words.extend(extra)
        
        for w in words:
            w['is_review'] = w.get('tier', 0) > 0
        
        if len(words) < count:
            for dw in DEFAULT_REVIEW_WORDS[:count - len(words)]:
                words.append({**dw, "tier": 1, "is_review": True})
        
        return words[:count]
    
    def get_distractors(self, correct_meaning: str, count: int = 3) -> list:
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("""SELECT meaning FROM distractor_pool 
                        WHERE meaning != ? 
                        ORDER BY RANDOM() LIMIT ?""",
                     (correct_meaning, count))
            return [row['meaning'] for row in c.fetchall()]
    
    def add_to_distractor_pool(self, word: str, meaning: str, pos: str = "unknown"):
        if not meaning or meaning == "待学习":
            return
        with self._get_conn() as conn:
            try:
                conn.execute("INSERT OR IGNORE INTO distractor_pool (word, meaning, pos) VALUES (?, ?, ?)",
                           (word, meaning, pos))
            except:
                pass
    
    def record_run(self, player_id: int, floor: int, victory: bool, words: list):
        self.end_run(player_id, floor, victory, words)
