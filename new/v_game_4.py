"""
单词尖塔 v4.0 - Spire of Vocab
====================================
模块化架构重构版

架构:
- GameDB: SQLite 持久化层 (金币/Deck/历史)
- GameManager: 游戏总管 (状态机 + 生命周期)
- MapSystem: 层级地图 (分支路径)
- EnemyFactory: 单词敌人分配器
- CombatSystem: 卡片翻转战斗
- BossSystem: AI 文章 + Quiz
"""

import streamlit as st
import streamlit.components.v1 as components
import random
import time
import json
import re
import sqlite3
from enum import Enum
from datetime import datetime
from contextlib import contextmanager
from openai import OpenAI

# ==========================================
# ⚙️ CONFIG & CONSTANTS
# ==========================================
KIMI_API_KEY = "sk-tqxUlkDlyX2N2Ka2fJzjv0aDKr5B8hJGVDhFD9N56vGBjlZf"
BASE_URL = "https://api.moonshot.cn/v1"
MODEL_ID = "kimi-k2.5"
DB_NAME = "vocab_spire.db"
USE_MOCK = False  # 🔴 设为 False 使用真实 AI API

# 默认复习词库 (当 deck 表为空时使用)
DEFAULT_REVIEW_WORDS = [
    {"word": "Ambiguous", "meaning": "模糊的，有歧义的"},
    {"word": "Compelling", "meaning": "令人信服的，引人注目的"},
    {"word": "Deteriorate", "meaning": "恶化，变坏"},
    {"word": "Eloquent", "meaning": "雄辩的，有说服力的"},
    {"word": "Formidable", "meaning": "令人敬畏的，可怕的"},
    {"word": "Gratify", "meaning": "使满足，使高兴"},
    {"word": "Hierarchy", "meaning": "等级制度"},
    {"word": "Imminent", "meaning": "即将发生的"},
    {"word": "Jeopardize", "meaning": "危及，损害"},
    {"word": "Keen", "meaning": "敏锐的，热衷的"},
]

class NodeType(Enum):
    COMBAT = "⚔️ 普通战斗"
    ELITE = "☠️ 精英战斗"
    EVENT = "❓ 随机事件"
    REST = "🔥 营地休息"
    SHOP = "🛒 地精商店"
    BOSS = "👹 最终领主"

class GamePhase(Enum):
    LOBBY = 0
    MAP_SELECT = 1
    IN_NODE = 2
    GAME_OVER = 3
    VICTORY = 4

# ==========================================
# 🔊 TTS 发音引擎
# ==========================================
def play_audio(text):
    js_code = f"""
        <script>
            window.speechSynthesis.cancel(); 
            var msg = new SpeechSynthesisUtterance("{text}");
            msg.lang = 'en-US';
            msg.rate = 0.9;
            window.speechSynthesis.speak(msg);
        </script>
    """
    components.html(js_code, height=0, width=0)

# ==========================================
# 🗄️ GameDB: SQLite 持久化层
# ==========================================
class GameDB:
    """管理玩家金币、已掌握词汇(Deck)、爬塔历史"""
    
    def __init__(self, db_name):
        self.db_name = db_name
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
    
    def get_or_create_player(self):
        """获取或创建默认玩家"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM players LIMIT 1")
            player = c.fetchone()
            if player:
                return dict(player)
            # 创建新玩家
            c.execute("INSERT INTO players DEFAULT VALUES")
            player_id = c.lastrowid
            return {"id": player_id, "name": "Adventurer", "gold": 0, "total_runs": 0, "victories": 0}
    
    def update_gold(self, player_id, gold_amount):
        with self._get_conn() as conn:
            conn.execute("UPDATE players SET gold = ?, last_played = CURRENT_TIMESTAMP WHERE id = ?", 
                        (gold_amount, player_id))
    
    def add_to_deck(self, player_id, word, meaning):
        """添加已掌握的词汇到 Deck"""
        with self._get_conn() as conn:
            # 检查是否已存在
            c = conn.cursor()
            c.execute("SELECT id FROM deck WHERE player_id = ? AND word = ?", (player_id, word))
            if not c.fetchone():
                conn.execute("INSERT INTO deck (player_id, word, meaning) VALUES (?, ?, ?)",
                           (player_id, word, meaning))
    
    def get_review_words(self, player_id, count=5):
        """从 Deck 获取复习词，不足时用默认词补充"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT word, meaning FROM deck WHERE player_id = ? ORDER BY RANDOM() LIMIT ?",
                     (player_id, count))
            words = [{"word": row["word"], "meaning": row["meaning"]} for row in c.fetchall()]
        
        # 不足时用默认词补充
        if len(words) < count:
            needed = count - len(words)
            existing_words = {w["word"] for w in words}
            for dw in DEFAULT_REVIEW_WORDS:
                if dw["word"] not in existing_words and needed > 0:
                    words.append(dw)
                    needed -= 1
        
        return words[:count]
    
    def record_run(self, player_id, floor_reached, victory, words_learned):
        """记录一次爬塔"""
        with self._get_conn() as conn:
            conn.execute("""INSERT INTO run_history (player_id, floor_reached, victory, words_learned) 
                           VALUES (?, ?, ?, ?)""",
                        (player_id, floor_reached, victory, json.dumps(words_learned, ensure_ascii=False)))
            # 更新玩家统计
            if victory:
                conn.execute("UPDATE players SET total_runs = total_runs + 1, victories = victories + 1 WHERE id = ?",
                           (player_id,))
            else:
                conn.execute("UPDATE players SET total_runs = total_runs + 1 WHERE id = ?", (player_id,))

# ==========================================
# 🧠 CyberMind: AI 智能体
# ==========================================
class CyberMind:
    def __init__(self):
        self.client = OpenAI(api_key=KIMI_API_KEY, base_url=BASE_URL)
    
    def _call(self, system, user, retries=3):
        for attempt in range(retries):
            try:
                response = self.client.chat.completions.create(
                    model=MODEL_ID,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user}
                    ],
                    temperature=0.8,
                    response_format={"type": "json_object"}
                )
                content = response.choices[0].message.content
                
                # 清洗 Markdown 代码块
                if "```" in content:
                    match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
                    if match:
                        content = match.group(1)
                
                return json.loads(content.strip())
            except json.JSONDecodeError as e:
                if attempt == retries - 1:
                    st.error(f"AI 返回格式异常: {e}")
                    return {}
            except Exception as e:
                st.error(f"API 错误: {e}")
                return {}
        return {}
    
    def generate_article(self, words):
        prompt = """
## 角色设定
你是《经济学人》的资深专栏作家，文风专业、逻辑严密。

## 任务
基于单词列表撰写 CET-6 难度短文 (150-220词)。

## 要求
1. 主题明确，单词自然融入上下文
2. 包含复杂句型（定语从句、虚拟语气等）
3. 用 `<span class='highlight-word'>...</span>` 高亮单词

## JSON 输出格式
{
    "article_english": "...",
    "article_chinese": "..."
}
"""
        return self._call(prompt, f"单词列表: {words}")
    
    def generate_quiz(self, words, article_context):
        prompt = f"""
## 角色设定
你是 CET-6/IELTS 命题专家。

## 输入
1. 单词: {words}
2. 文章: {article_context}

## 要求
1. 设计 3-5 道阅读理解/词汇推断题
2. 干扰项要有迷惑性
3. 题目考察语境理解，非简单词义匹配

## JSON 输出格式
{{
    "quizzes": [
        {{
            "question": "题干...",
            "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
            "answer": "A. ...",
            "damage": 25,
            "explanation": "解析..."
        }}
    ]
}}
"""
        return self._call(prompt, f"请设计题目")

# ==========================================
# 👾 EnemyFactory: 单词敌人分配器
# ==========================================
class EnemyFactory:
    """负责将单词分配到各层作为敌人"""
    
    def __init__(self, new_words, review_words):
        self.new_words = new_words  # 15 个新词
        self.review_words = review_words  # 5 个复习词
        self.word_pool = list(new_words)  # 复制一份用于分配
        random.shuffle(self.word_pool)
        self.distribution = {}
    
    def get_enemies_for_floor(self, floor, total_floors):
        """
        分配逻辑:
        - Floor 1-4: 每层 3-4 个新词作为小怪
        - Floor 5 (Boss): 所有 15 新词 + 5 复习词
        """
        if floor == total_floors:  # Boss 层
            return self.new_words + self.review_words
        
        # 计算每层分配多少词
        words_per_floor = len(self.new_words) // (total_floors - 1)
        extra = len(self.new_words) % (total_floors - 1)
        
        count = words_per_floor + (1 if floor <= extra else 0)
        count = max(3, min(4, count))  # 限制 3-4 个
        
        # 从池中取出
        if floor not in self.distribution:
            enemies = []
            for _ in range(count):
                if self.word_pool:
                    enemies.append(self.word_pool.pop())
            self.distribution[floor] = enemies
        
        return self.distribution.get(floor, [])

# ==========================================
# 🧑 Player: 玩家数据模型
# ==========================================
class Player:
    def __init__(self, db_player=None):
        if db_player:
            self.id = db_player["id"]
            self.gold = db_player["gold"]
        else:
            self.id = 1
            self.gold = 0
        self.hp = 100
        self.max_hp = 100
        self.inventory = []  # 道具
    
    def change_hp(self, amount):
        self.hp += amount
        self.hp = max(0, min(self.hp, self.max_hp))
        if amount < 0:
            st.toast(f"💔 HP {amount}", icon="🩸")
        else:
            st.toast(f"💚 HP +{amount}", icon="🌿")
    
    def add_gold(self, amount):
        self.gold += amount
        st.toast(f"💰 金币 +{amount}")

# ==========================================
# 🗺️ Node & MapSystem: 地图系统
# ==========================================
class Node:
    def __init__(self, node_type: NodeType, level: int):
        self.type = node_type
        self.level = level
        self.status = "PENDING"
        self.data = {}
    
    def generate_content(self, enemy_factory, floor, total_floors):
        if self.type == NodeType.COMBAT or self.type == NodeType.ELITE:
            self.data['enemies'] = enemy_factory.get_enemies_for_floor(floor, total_floors)
            self.data['desc'] = "遭遇了游荡的单词幽灵。" if self.type == NodeType.COMBAT else "精英怪物出现！"
        
        elif self.type == NodeType.BOSS:
            self.data['enemies'] = enemy_factory.get_enemies_for_floor(floor, total_floors)
            self.data['boss_name'] = "The Syntax Colossus"
            self.data['boss_hp'] = 100
            self.data['boss_max_hp'] = 100
            self.data['desc'] = "它由你所有的记忆碎片组成。"
        
        elif self.type == NodeType.EVENT:
            events = [
                {"title": "遗忘之泉", "desc": "喝下泉水，回复 20 HP。", "effect": "heal", "value": 20},
                {"title": "古老卷轴", "desc": "阅读消耗 10 HP，获得 50 金币。", "effect": "trade", "hp": -10, "gold": 50},
                {"title": "神秘商人", "desc": "花费 30 金币，永久 +10 最大 HP。", "effect": "upgrade", "cost": 30, "value": 10}
            ]
            self.data['event'] = random.choice(events)
        
        elif self.type == NodeType.SHOP:
            self.data['items'] = [
                {"name": "🧪 生命药水", "desc": "恢复 50 HP", "price": 30, "effect": "heal", "value": 50},
                {"name": "🛡️ 逻辑护盾", "desc": "Boss 战第一次伤害免疫", "price": 50, "effect": "shield"},
                {"name": "📚 智慧卷轴", "desc": "下次战斗提示正确答案", "price": 40, "effect": "hint"}
            ]

class MapSystem:
    def __init__(self, total_floors=5):
        self.floor = 0
        self.total_floors = total_floors
        self.current_node = None
        self.next_options = []
    
    def generate_next_options(self):
        self.floor += 1
        
        if self.floor == self.total_floors:
            return [Node(NodeType.BOSS, self.floor)]
        
        # 权重: 战斗最多，事件/休息/商店较少
        weights = [NodeType.COMBAT, NodeType.COMBAT, NodeType.COMBAT, 
                   NodeType.EVENT, NodeType.REST, NodeType.SHOP]
        if self.floor == self.total_floors - 1:
            weights.append(NodeType.ELITE)  # Boss 前一层可能有精英
        
        type1 = random.choice(weights)
        type2 = random.choice(weights)
        while type2 == type1:
            type2 = random.choice(weights)
        
        return [Node(type1, self.floor), Node(type2, self.floor)]

# ==========================================
# 🎮 GameManager: 游戏总管
# ==========================================
class GameManager:
    def __init__(self):
        # 初始化数据库
        if 'db' not in st.session_state:
            st.session_state.db = GameDB(DB_NAME)
        
        # 加载或创建玩家
        if 'db_player' not in st.session_state:
            st.session_state.db_player = st.session_state.db.get_or_create_player()
        
        if 'player' not in st.session_state:
            st.session_state.player = Player(st.session_state.db_player)
        
        if 'game_map' not in st.session_state:
            st.session_state.game_map = MapSystem(total_floors=5)
        
        if 'phase' not in st.session_state:
            st.session_state.phase = GamePhase.LOBBY
        
        if 'run_words' not in st.session_state:
            st.session_state.run_words = []
        
        if 'enemy_factory' not in st.session_state:
            st.session_state.enemy_factory = None
        
        if 'ai' not in st.session_state:
            st.session_state.ai = CyberMind()
    
    def start_run(self, raw_text):
        """开始新的一局"""
        if USE_MOCK:
            # Mock 数据
            mock_vocab = [
                ("Ephemeral", "短暂的"), ("Serendipity", "意外好运"), ("Oblivion", "遗忘"),
                ("Resilience", "韧性"), ("Cacophony", "刺耳噪音"), ("Luminous", "发光的"),
                ("Solitude", "孤独"), ("Epiphany", "顿悟"), ("Nostalgia", "怀旧"),
                ("Ethereal", "超凡脱俗的"), ("Ineffable", "不可言喻的"), ("Mellifluous", "声音甜美的"),
                ("Petrichor", "雨后泥土味"), ("Sonder", "路人皆有故事"), ("Vellichor", "旧书店情怀")
            ]
            new_words = [{"word": w, "meaning": m} for w, m in mock_vocab]
        else:
            # 解析用户输入
            words = [w.strip() for w in raw_text.split(',') if w.strip()]
            new_words = [{"word": w, "meaning": "待学习"} for w in words[:15]]
            while len(new_words) < 15:
                new_words.append({"word": f"Word_{len(new_words)+1}", "meaning": "补充词"})
        
        # 获取复习词
        player_id = st.session_state.db_player["id"]
        review_words = st.session_state.db.get_review_words(player_id, count=5)
        
        # 初始化
        st.session_state.run_words = new_words
        st.session_state.enemy_factory = EnemyFactory(new_words, review_words)
        st.session_state.game_map = MapSystem(total_floors=5)
        st.session_state.game_map.next_options = st.session_state.game_map.generate_next_options()
        st.session_state.player.hp = st.session_state.player.max_hp  # 重置 HP
        st.session_state.phase = GamePhase.MAP_SELECT
        
        # 清除旧战斗状态
        for key in ['combat_state', 'boss_state']:
            if key in st.session_state:
                del st.session_state[key]
        
        st.rerun()
    
    def enter_node(self, node):
        node.generate_content(
            st.session_state.enemy_factory,
            st.session_state.game_map.floor,
            st.session_state.game_map.total_floors
        )
        st.session_state.game_map.current_node = node
        
        # 清除旧战斗状态
        for key in ['combat_state', 'boss_state']:
            if key in st.session_state:
                del st.session_state[key]
        
        st.session_state.phase = GamePhase.IN_NODE
        st.rerun()
    
    def resolve_node(self):
        ms = st.session_state.game_map
        
        # 清除战斗状态
        for key in ['combat_state', 'boss_state']:
            if key in st.session_state:
                del st.session_state[key]
        
        # 保存金币到数据库
        st.session_state.db.update_gold(
            st.session_state.db_player["id"],
            st.session_state.player.gold
        )
        
        if ms.floor >= ms.total_floors:
            self.end_run(victory=True)
        else:
            ms.next_options = ms.generate_next_options()
            st.session_state.phase = GamePhase.MAP_SELECT
        st.rerun()
    
    def end_run(self, victory=False):
        """结束本局，记录历史"""
        player_id = st.session_state.db_player["id"]
        floor = st.session_state.game_map.floor
        words = [w["word"] for w in st.session_state.run_words]
        
        # 记录到数据库
        st.session_state.db.record_run(player_id, floor, victory, words)
        st.session_state.db.update_gold(player_id, st.session_state.player.gold)
        
        # 如果胜利，把本局词汇加入 Deck
        if victory:
            for w in st.session_state.run_words:
                st.session_state.db.add_to_deck(player_id, w["word"], w["meaning"])
        
        st.session_state.phase = GamePhase.VICTORY if victory else GamePhase.GAME_OVER
        st.rerun()
    
    def check_player_death(self):
        if st.session_state.player.hp <= 0:
            self.end_run(victory=False)
            return True
        return False

# ==========================================
# 🖥️ UI 渲染层
# ==========================================
def render_hud():
    p = st.session_state.player
    m = st.session_state.game_map
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        with c1:
            st.progress(p.hp / p.max_hp, f"HP: {p.hp}/{p.max_hp}")
        with c2:
            st.write(f"🗺️ Floor: {m.floor}/{m.total_floors}")
        with c3:
            st.write(f"💰 Gold: {p.gold}")
        with c4:
            st.write(f"📦 {len(p.inventory)} 道具")

def render_lobby(gm):
    st.title("🏰 单词尖塔 (Spire of Vocab)")
    
    # 显示玩家统计
    db_player = st.session_state.db_player
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💰 累计金币", db_player.get("gold", 0))
    with col2:
        st.metric("🏆 胜利次数", db_player.get("victories", 0))
    with col3:
        st.metric("🎮 总场次", db_player.get("total_runs", 0))
    
    st.divider()
    
    if USE_MOCK:
        st.info("🧪 Mock 模式：无需输入，使用预设词汇测试")
        if st.button("🩸 开始冒险", type="primary", use_container_width=True):
            gm.start_run("")
    else:
        st.markdown("### 📝 输入今天要攻克的生词")
        user_input = st.text_area(
            "用逗号分隔 (10-15 个词)",
            "Ephemeral, Serendipity, Oblivion, Resilience, Cacophony",
            height=100
        )
        if st.button("🩸 献祭单词并开始", type="primary", use_container_width=True):
            gm.start_run(user_input)

def render_map_select(gm):
    st.header("🛤️ 选择你的路径")
    st.markdown("前方迷雾散去，你看到了岔路...")
    
    options = st.session_state.game_map.next_options
    cols = st.columns(len(options))
    
    for i, node in enumerate(options):
        with cols[i]:
            with st.container(border=True):
                st.markdown(f"### {node.type.value}")
                st.caption(f"Floor {node.level}")
                if st.button(f"前往", key=f"node_sel_{i}", use_container_width=True):
                    gm.enter_node(node)

def render_combat(gm, node):
    """战斗节点渲染 - 卡片翻转 + 问答"""
    enemies = node.data['enemies']
    
    # 初始化战斗状态
    if 'combat_state' not in st.session_state:
        st.session_state.combat_state = {
            'idx': 0,
            'flipped': False,
            'options': None,
            'is_elite': node.type.name == "ELITE"
        }
    
    cs = st.session_state.combat_state
    is_elite = cs.get('is_elite', False)
    
    # 胜利判定
    if cs['idx'] >= len(enemies):
        st.balloons()
        st.success(f"🎉 战斗胜利！清理了 {len(enemies)} 个生词。")
        gold_reward = 30 if is_elite else 20
        if st.button(f"🎁 搜刮战利品 (+{gold_reward}G)", type="primary"):
            st.session_state.player.add_gold(gold_reward)
            gm.resolve_node()
        return
    
    current_enemy = enemies[cs['idx']]
    damage = 15 if is_elite else 10  # 精英伤害更高
    
    # 战斗界面
    col_card, col_action = st.columns([1, 1])
    
    with col_card:
        with st.container(border=True):
            enemy_icon = "☠️" if is_elite else "👻"
            st.markdown(f"## {enemy_icon} 怪物 {cs['idx']+1}/{len(enemies)}")
            st.markdown(f"# {current_enemy['word']}")
            
            if st.button("🔊 听音辨位", key=f"tts_{cs['idx']}"):
                play_audio(current_enemy['word'])
            
            if cs['flipped']:
                st.divider()
                st.markdown(f"**释义:** {current_enemy['meaning']}")
    
    with col_action:
        st.write("### 你的行动")
        
        if not cs['flipped']:
            st.info("你遇到了一个生词怪物。")
            if st.button("🔍 洞察弱点 (翻看释义)", use_container_width=True):
                cs['flipped'] = True
                st.rerun()
        else:
            # 生成选项
            if cs['options'] is None:
                all_meanings = [w['meaning'] for w in st.session_state.run_words 
                               if w['meaning'] != current_enemy['meaning']]
                distractors = random.sample(all_meanings, k=min(3, len(all_meanings)))
                options = distractors + [current_enemy['meaning']]
                random.shuffle(options)
                cs['options'] = options
            
            st.write("⚔️ 选择正确的释义:")
            user_choice = st.radio("Options", cs['options'], key=f"quiz_{cs['idx']}", label_visibility="collapsed")
            
            if st.button("🗡️ 发动攻击", type="primary", use_container_width=True):
                if user_choice == current_enemy['meaning']:
                    st.toast("⚡ 暴击！", icon="💥")
                    st.session_state.player.add_gold(5)
                    cs['idx'] += 1
                    cs['flipped'] = False
                    cs['options'] = None
                    st.rerun()
                else:
                    st.session_state.player.change_hp(-damage)
                    st.error(f"🛡️ 攻击偏离！受到 {damage} 点反伤！")
                    if gm.check_player_death():
                        return

def render_boss(gm, node):
    """Boss 战渲染 - AI 文章 + Quiz"""
    if 'boss_state' not in st.session_state:
        st.session_state.boss_state = {
            'phase': 'loading',  # loading, article, quiz
            'article': None,
            'quizzes': None,
            'quiz_idx': 0,
            'boss_hp': node.data['boss_hp']
        }
    
    bs = st.session_state.boss_state
    
    # Boss 血条
    st.markdown(f"## 👹 {node.data['boss_name']}")
    boss_pct = max(0, bs['boss_hp'] / node.data['boss_max_hp'])
    st.progress(boss_pct, f"Boss HP: {bs['boss_hp']}/{node.data['boss_max_hp']}")
    
    # 阶段 1: 加载文章
    if bs['phase'] == 'loading':
        with st.spinner("Boss 正在觉醒... AI 生成文章中..."):
            if USE_MOCK:
                # Mock 文章
                bs['article'] = {
                    "article_english": """In the <span class='highlight-word'>ephemeral</span> dance of digital existence, 
                    we often stumble upon moments of <span class='highlight-word'>serendipity</span>. 
                    The fear of <span class='highlight-word'>oblivion</span> drives us forward, 
                    while <span class='highlight-word'>resilience</span> becomes our greatest ally.""",
                    "article_chinese": "在数字存在的短暂舞蹈中，我们常常偶遇意外之喜。对遗忘的恐惧驱使我们前进，而韧性成为我们最大的盟友。"
                }
                bs['quizzes'] = {
                    "quizzes": [
                        {
                            "question": "What is the main theme of the passage?",
                            "options": ["A. Digital anxiety", "B. Cooking skills", "C. History", "D. Sports"],
                            "answer": "A. Digital anxiety",
                            "damage": 25,
                            "explanation": "文章讨论数字时代的存在与恐惧。"
                        },
                        {
                            "question": "The word 'ephemeral' suggests that digital existence is...",
                            "options": ["A. Permanent", "B. Short-lived", "C. Expensive", "D. Heavy"],
                            "answer": "B. Short-lived",
                            "damage": 25,
                            "explanation": "ephemeral 意为短暂的。"
                        }
                    ]
                }
            else:
                # 真实 AI 调用
                words = [w['word'] for w in node.data['enemies']]
                bs['article'] = st.session_state.ai.generate_article(words)
                if bs['article']:
                    bs['quizzes'] = st.session_state.ai.generate_quiz(
                        words, 
                        bs['article'].get('article_english', '')
                    )
            
            bs['phase'] = 'article'
            st.rerun()
    
    # 阶段 2: 显示文章
    elif bs['phase'] == 'article':
        if bs['article']:
            with st.expander("📜 Boss 本体 (阅读文章)", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**English**")
                    st.markdown(bs['article'].get('article_english', ''), unsafe_allow_html=True)
                with col2:
                    st.markdown("**中文翻译**")
                    st.markdown(bs['article'].get('article_chinese', ''))
        
        if st.button("⚔️ 准备战斗", type="primary", use_container_width=True):
            bs['phase'] = 'quiz'
            st.rerun()
    
    # 阶段 3: Quiz 战斗
    elif bs['phase'] == 'quiz':
        quizzes = bs['quizzes'].get('quizzes', []) if bs['quizzes'] else []
        
        # Boss 死亡判定
        if bs['boss_hp'] <= 0:
            st.balloons()
            st.success("🏆 Boss 已被击败！你成功净化了这片记忆！")
            if st.button("🎁 获取胜利奖励 (+100G)", type="primary"):
                st.session_state.player.add_gold(100)
                gm.resolve_node()
            return
        
        # Quiz 完成判定
        if bs['quiz_idx'] >= len(quizzes):
            st.warning("所有技能已释放，Boss 仍存活...")
            if st.button("🔄 再战一轮"):
                bs['quiz_idx'] = 0
                st.rerun()
            return
        
        q = quizzes[bs['quiz_idx']]
        
        st.markdown(f"### 🔥 Boss 技能 [{bs['quiz_idx']+1}/{len(quizzes)}]")
        with st.container(border=True):
            st.markdown(f"**{q['question']}**")
            choice = st.radio("选择答案:", q['options'], key=f"boss_q_{bs['quiz_idx']}")
            
            if st.button("✨ 释放反击", type="primary"):
                damage = q.get('damage', 25)
                if choice == q['answer']:
                    bs['boss_hp'] -= 30
                    st.toast(f"💥 暴击！Boss -{30} HP", icon="⚡")
                    st.success(f"✅ 正确！{q.get('explanation', '')}")
                else:
                    st.session_state.player.change_hp(-damage)
                    st.error(f"❌ 错误！正确答案: {q['answer']}")
                    st.info(q.get('explanation', ''))
                    if gm.check_player_death():
                        return
                
                bs['quiz_idx'] += 1
                time.sleep(1)
                st.rerun()

def render_event(gm, node):
    """事件节点渲染"""
    evt = node.data['event']
    st.markdown(f"### ❓ {evt['title']}")
    st.info(evt['desc'])
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ 接受", use_container_width=True):
            effect = evt.get('effect')
            if effect == 'heal':
                st.session_state.player.change_hp(evt['value'])
            elif effect == 'trade':
                st.session_state.player.change_hp(evt['hp'])
                st.session_state.player.add_gold(evt['gold'])
            elif effect == 'upgrade':
                if st.session_state.player.gold >= evt['cost']:
                    st.session_state.player.gold -= evt['cost']
                    st.session_state.player.max_hp += evt['value']
                    st.toast(f"最大 HP +{evt['value']}")
                else:
                    st.toast("金币不足！", icon="❌")
            gm.resolve_node()
    with col2:
        if st.button("❌ 离开", use_container_width=True):
            gm.resolve_node()

def render_shop(gm, node):
    """商店节点渲染"""
    st.header("🛒 地精商店")
    st.caption(f"你的金币: 💰 {st.session_state.player.gold}")
    
    items = node.data.get('items', [])
    cols = st.columns(len(items))
    
    for i, item in enumerate(items):
        with cols[i]:
            with st.container(border=True):
                st.markdown(f"### {item['name']}")
                st.markdown(f"**{item['desc']}**")
                st.markdown(f"💰 {item['price']}G")
                
                if st.button(f"购买", key=f"shop_{i}", use_container_width=True):
                    if st.session_state.player.gold >= item['price']:
                        st.session_state.player.gold -= item['price']
                        
                        if item['effect'] == 'heal':
                            st.session_state.player.change_hp(item['value'])
                        elif item['effect'] == 'shield':
                            st.session_state.player.inventory.append('SHIELD')
                            st.toast("获得: 逻辑护盾")
                        elif item['effect'] == 'hint':
                            st.session_state.player.inventory.append('HINT')
                            st.toast("获得: 智慧卷轴")
                        st.rerun()
                    else:
                        st.error("金币不足！")
    
    st.divider()
    if st.button("🚪 离开商店", use_container_width=True):
        gm.resolve_node()

def render_rest(gm, node):
    """营地休息渲染"""
    st.header("🔥 营地")
    st.info("在温暖的篝火旁休息，恢复精力...")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("😴 休息 (+30 HP)", use_container_width=True):
            st.session_state.player.change_hp(30)
            gm.resolve_node()
    with col2:
        if st.button("🏃 跳过休息", use_container_width=True):
            gm.resolve_node()

def render_in_node(gm):
    """节点内渲染路由"""
    node = st.session_state.game_map.current_node
    st.subheader(f"📍 {node.type.value}")
    
    type_name = node.type.name
    
    if type_name in ["COMBAT", "ELITE"]:
        render_combat(gm, node)
    elif type_name == "BOSS":
        render_boss(gm, node)
    elif type_name == "EVENT":
        render_event(gm, node)
    elif type_name == "SHOP":
        render_shop(gm, node)
    elif type_name == "REST":
        render_rest(gm, node)
    else:
        st.warning(f"未知节点: {type_name}")
        if st.button("强制离开"):
            gm.resolve_node()

def render_game():
    gm = GameManager()
    phase_name = st.session_state.phase.name
    
    if phase_name != "LOBBY":
        render_hud()
    
    if phase_name == "LOBBY":
        render_lobby(gm)
    elif phase_name == "MAP_SELECT":
        render_map_select(gm)
    elif phase_name == "IN_NODE":
        render_in_node(gm)
    elif phase_name == "VICTORY":
        st.balloons()
        st.title("🏆 通关！")
        st.success("你成功攀登了单词尖塔！")
        st.metric("获得金币", st.session_state.player.gold)
        if st.button("🔄 再来一局", type="primary"):
            st.session_state.phase = GamePhase.LOBBY
            st.rerun()
    elif phase_name == "GAME_OVER":
        st.error("💀 你的意识消散了...")
        st.markdown(f"到达层数: {st.session_state.game_map.floor}")
        if st.button("🔄 重新开始"):
            st.session_state.phase = GamePhase.LOBBY
            st.session_state.player = Player(st.session_state.db_player)
            st.rerun()
    else:
        st.warning("状态异常，正在重置...")
        time.sleep(1)
        st.session_state.clear()
        st.rerun()

# ==========================================
# 🚀 启动
# ==========================================
st.set_page_config(page_title="单词尖塔 v4", page_icon="🏰", layout="centered")

# 注入 CSS
st.markdown("""
<style>
    .highlight-word { 
        color: #ff6b6b; 
        font-weight: bold; 
        background: rgba(255, 107, 107, 0.1); 
        padding: 0 4px; 
        border-radius: 4px; 
    }
</style>
""", unsafe_allow_html=True)

render_game()
