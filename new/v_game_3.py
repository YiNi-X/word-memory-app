import streamlit as st
import random
import time
from enum import Enum
import streamlit.components.v1 as components # 👈 新增：用于 TTS 发音

# ==========================================
# ⚙️ 基础配置与工具函数
# ==========================================
USE_MOCK = True

def play_audio(text):
    """前端 TTS 发音引擎"""
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
# 🧠 数据模型 (Model Classes)
# ==========================================

class Player:
    def __init__(self):
        self.hp = 100
        self.max_hp = 100
        self.gold = 0
        # self.deck = [] 
        # self.relics = [] 

    def change_hp(self, amount):
        self.hp += amount
        self.hp = min(self.hp, self.max_hp)
        if amount < 0:
            st.toast(f"💔 HP {amount}", icon="🩸")
        else:
            st.toast(f"💚 HP +{amount}", icon="🌿")

class Node:
    def __init__(self, node_type: NodeType, level: int):
        self.type = node_type
        self.level = level
        self.status = "PENDING"
        self.data = {} 

    def generate_content(self, all_new_words):
        if self.type == NodeType.COMBAT:
            # 随机抓 3 个新词做小怪
            # 确保不报错：如果词不够3个，就取全部
            k = min(3, len(all_new_words))
            self.data['enemies'] = random.sample(all_new_words, k=k)
            self.data['desc'] = f"遭遇了 {k} 个游荡的单词幽灵。"
            
        elif self.type == NodeType.BOSS:
            self.data['enemies'] = all_new_words 
            self.data['boss_name'] = "The Syntax Colossus"
            self.data['desc'] = "它由你这段时间所有的记忆碎片组成。"
            
        elif self.type == NodeType.EVENT:
            events = [
                {"title": "遗忘之泉", "desc": "喝下泉水，回复 20 HP，但会暂时遗忘痛苦。"},
                {"title": "古老卷轴", "desc": "阅读卷轴消耗 10 HP，获得 50 金币。"}
            ]
            self.data['event'] = random.choice(events)

# ==========================================
# 🗺️ 地图系统
# ==========================================
class MapSystem:
    def __init__(self, total_floors=5):
        self.floor = 0
        self.total_floors = total_floors
        self.current_node = None
        self.next_options = []

    def generate_next_options(self):
        self.floor += 1
        options = []
        if self.floor == self.total_floors:
            return [Node(NodeType.BOSS, self.floor)]
        
        weights = [NodeType.COMBAT, NodeType.COMBAT, NodeType.EVENT, NodeType.REST, NodeType.SHOP]
        type1 = random.choice(weights)
        type2 = random.choice(weights)
        while type2 == type1: type2 = random.choice(weights)

        options.append(Node(type1, self.floor))
        options.append(Node(type2, self.floor))
        return options

# ==========================================
# 🎮 游戏管理器
# ==========================================
class GameManager:
    def __init__(self):
        if 'player' not in st.session_state: st.session_state.player = Player()
        if 'game_map' not in st.session_state: st.session_state.game_map = MapSystem(total_floors=5)
        if 'phase' not in st.session_state: st.session_state.phase = GamePhase.LOBBY
        if 'run_words' not in st.session_state: st.session_state.run_words = [] 

    def start_run(self, raw_text):
        if USE_MOCK:
            # 🟢 优化 Mock 数据生成：为了让选项有区分度，生成不同的释义
            mock_vocab = [
                ("Ephemeral", "短暂的"), ("Serendipity", "意外好运"), ("Oblivion", "遗忘"), 
                ("Resilience", "韧性"), ("Cacophony", "刺耳噪音"), ("Luminous", "发光的"),
                ("Solitude", "孤独"), ("Epiphany", "顿悟"), ("Nostalgia", "怀旧"),
                ("Ethereal", "超凡脱俗的"), ("Ineffable", "不可言喻的"), ("Mellifluous", "声音甜美的"),
                ("Petrichor", "雨后泥土味"), ("Sonder", "路人皆有故事"), ("Vellichor", "旧书店情怀")
            ]
            words = [{"word": w, "meaning": m} for w, m in mock_vocab]
            random.shuffle(words)
        else:
            # 真实 API 逻辑在这里
            pass
        
        st.session_state.run_words = words[:15]
        st.session_state.game_map = MapSystem(total_floors=5) 
        st.session_state.game_map.next_options = st.session_state.game_map.generate_next_options()
        st.session_state.phase = GamePhase.MAP_SELECT
        st.rerun()

    def enter_node(self, node):
        node.generate_content(st.session_state.run_words)
        st.session_state.game_map.current_node = node
        
        # 🟢 清除旧的战斗状态，防止干扰
        if 'combat_state' in st.session_state:
            del st.session_state.combat_state
            
        st.session_state.phase = GamePhase.IN_NODE
        st.rerun()

    def resolve_node(self):
        ms = st.session_state.game_map
        # 🟢 离开节点时清除战斗状态
        if 'combat_state' in st.session_state:
            del st.session_state.combat_state

        if ms.floor >= ms.total_floors:
            st.session_state.phase = GamePhase.VICTORY
        else:
            ms.next_options = ms.generate_next_options()
            st.session_state.phase = GamePhase.MAP_SELECT
        st.rerun()

# ==========================================
# 🖥️ UI 渲染层
# ==========================================
def render_hud():
    p = st.session_state.player
    m = st.session_state.game_map
    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1: st.progress(p.hp / p.max_hp, f"HP: {p.hp}/{p.max_hp}")
        with c2: st.write(f"🗺️ Floor: {m.floor}/{m.total_floors}")
        with c3: st.write(f"💰 Gold: {p.gold}")

def render_lobby(gm):
    st.title("🏰 单词尖塔 (Spire of Vocab)")
    st.info("Mock 模式已开启，无需输入，直接开始即可体验战斗循环。")
    if st.button("🩸 开始冒险 (Start Run)"):
        gm.start_run("ignored_in_mock")

def render_map_select(gm):
    st.header("🛤️ 选择路径")
    options = st.session_state.game_map.next_options
    col_opts = st.columns(len(options))
    for i, node in enumerate(options):
        with col_opts[i]:
            with st.container(border=True):
                st.markdown(f"### {node.type.value}")
                st.caption(f"Floor {node.level}")
                if st.button(f"前往", key=f"node_sel_{i}", use_container_width=True):
                    gm.enter_node(node)

# 🔴 核心修改：战斗逻辑的实现
# 🔴 核心修改：战斗逻辑的实现 (修复版)
def render_in_node(gm):
    node = st.session_state.game_map.current_node
    st.subheader(f"📍 {node.type.value}")
    
    # 🟢 修复核心：获取枚举的名字 (字符串)，用于稳定的逻辑判断
    # 这样可以避免 "NodeType.COMBAT != NodeType.COMBAT" 的热重载 Bug
    current_type_name = node.type.name 
    
    # === COMBAT LOGIC ===
    # 🟢 把原来的 node.type == NodeType.COMBAT 改为字符串比较
    if current_type_name == "COMBAT":
        enemies = node.data['enemies']
        
        # 1. 初始化战斗状态 (仅在第一次渲染时)
        if 'combat_state' not in st.session_state:
            st.session_state.combat_state = {
                'idx': 0,          # 当前打第几个怪
                'flipped': False,  # 当前卡片是否翻开
                'options': None    # 当前题目的选项缓存
            }
        
        cs = st.session_state.combat_state
        
        # 2. 胜利判定
        if cs['idx'] >= len(enemies):
            st.balloons()
            st.success(f"战斗胜利！清理了 {len(enemies)} 个生词。")
            if st.button("🎁 搜刮战利品并离开", type="primary"):
                st.session_state.player.gold += 20 # 结算金币
                gm.resolve_node()
            return # 结束渲染

        # 3. 获取当前怪物
        current_enemy = enemies[cs['idx']]
        
        # 4. 战斗界面布局
        col_card, col_action = st.columns([1, 1])
        
        with col_card:
            with st.container(border=True):
                st.markdown(f"## 👻 怪物 {cs['idx']+1}/{len(enemies)}")
                st.markdown(f"# {current_enemy['word']}")
                
                if st.button("🔊 听音辨位", key=f"tts_{cs['idx']}"):
                    play_audio(current_enemy['word'])
                
                if cs['flipped']:
                    st.divider()
                    st.markdown(f"**释义:** {current_enemy['meaning']}")

        with col_action:
            st.write("### 你的行动")
            
            # 阶段 A: 观察
            if not cs['flipped']:
                st.info("你遇到了一个生词怪物。")
                if st.button("🔍 洞察弱点 (翻看释义)", use_container_width=True):
                    cs['flipped'] = True
                    st.rerun()
            
            # 阶段 B: 攻击
            else:
                if cs['options'] is None:
                    all_meanings = [w['meaning'] for w in st.session_state.run_words if w['meaning'] != current_enemy['meaning']]
                    distractors = random.sample(all_meanings, k=min(3, len(all_meanings)))
                    options = distractors + [current_enemy['meaning']]
                    random.shuffle(options)
                    cs['options'] = options
                
                st.write("⚔️ 选择正确的攻击方位 (释义):")
                user_choice = st.radio("Options", cs['options'], key=f"quiz_{cs['idx']}")
                
                if st.button("🗡️ 发动攻击", type="primary", use_container_width=True):
                    if user_choice == current_enemy['meaning']:
                        st.toast("⚡ 暴击！一击必杀！", icon="💥")
                        st.session_state.player.gold += 5
                        cs['idx'] += 1
                        cs['flipped'] = False
                        cs['options'] = None
                        st.rerun()
                    else:
                        st.session_state.player.change_hp(-10)
                        st.error("🛡️ 攻击偏离！你受到了 10 点反伤！")

    # === BOSS LOGIC ===
    elif current_type_name == "BOSS":
        st.error("👹 Boss 战逻辑待接入 AI...")
        if st.button("跳过 Boss (Debug)"): gm.resolve_node()
            
    # === OTHER NODES ===
    elif current_type_name == "EVENT":
        evt = node.data['event']
        st.markdown(f"### {evt['title']}")
        st.info(evt['desc'])
        if st.button("继续前进"): gm.resolve_node()
        
    elif current_type_name == "SHOP":
        st.write("🛒 商店开发中...")
        if st.button("离开"): gm.resolve_node()
        
    elif current_type_name == "REST":
        st.write("🔥 营地休息中... HP +20")
        if st.button("休息完毕"): 
            st.session_state.player.change_hp(20)
            gm.resolve_node()
            
    # 兜底：防止未知的节点类型导致空白
    else:
        st.warning(f"⚠️ 未知节点类型: {current_type_name}")
        if st.button("强制离开"): gm.resolve_node()
# ==========================================
# 🖥️ UI 渲染层 (修复版)
# ==========================================
def render_game():
    gm = GameManager()
    
    # 🟢 修复 1: 使用 .name 进行字符串比较，避免 Enum 对象身份不一致的问题
    # 只要名字是 'LOBBY'，就认为是 Lobby
    current_phase_name = st.session_state.phase.name 

    # 如果不是 Lobby，显示顶部的 HUD
    if current_phase_name != "LOBBY": 
        render_hud()
    
    # 根据状态渲染对应的界面
    if current_phase_name == "LOBBY":
        render_lobby(gm)
    elif current_phase_name == "MAP_SELECT":
        render_map_select(gm)
    elif current_phase_name == "IN_NODE":
        render_in_node(gm)
    elif current_phase_name == "VICTORY":
        st.balloons()
        st.title("🏆 通关！")
        if st.button("再来一局"):
            st.session_state.phase = GamePhase.LOBBY
            st.rerun()
            
    # 🟢 修复 2: 增加兜底逻辑 (Catch-all)
    # 如果状态掉进了虚空（比如之前的僵尸状态），强制重置
    else:
        st.warning("⚠️ 检测到状态异常 (可能是热重载导致的)，正在重置游戏...")
        time.sleep(1)
        st.session_state.clear()
        st.rerun()

# ==========================================
# 🚀 启动
# ==========================================
st.set_page_config(page_title="Roguelike Vocab", layout="centered")
render_game()