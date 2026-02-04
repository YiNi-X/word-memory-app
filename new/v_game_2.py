import streamlit as st
import random
import time
from enum import Enum

# ==========================================
# ⚙️ 基础配置与枚举
# ==========================================
USE_MOCK = True

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
        self.deck = [] # 玩家已掌握的技能/道具
        self.relics = [] # 圣遗物

    def change_hp(self, amount):
        self.hp += amount
        self.hp = min(self.hp, self.max_hp)
        if amount < 0:
            st.toast(f"💔 HP {amount}")
        else:
            st.toast(f"💚 HP +{amount}")

class Node:
    """地图上的一个节点（房间）"""
    def __init__(self, node_type: NodeType, level: int):
        self.type = node_type
        self.level = level
        self.status = "PENDING" # PENDING, ACTIVE, CLEARED
        self.data = {} # 存放这个房间特有的数据（比如怪物列表、事件内容）

    def generate_content(self, all_new_words):
        """
        核心逻辑：根据房间类型，从生词池里抓取怪物
        """
        if self.type == NodeType.COMBAT:
            # 普通战斗：随机抓 3 个新词做小怪
            # 真实场景下，这里应确保不重复抓取，或者抓取未掌握的
            self.data['enemies'] = random.sample(all_new_words, k=3)
            self.data['desc'] = "遇到了一群游荡的单词小鬼。"
            
        elif self.type == NodeType.BOSS:
            # Boss战：所有新词 + 复习词
            self.data['enemies'] = all_new_words # 全部 10-15 个词
            self.data['boss_name'] = "The Syntax Colossus"
            self.data['desc'] = "它由你这段时间所有的记忆碎片组成。"
            
        elif self.type == NodeType.EVENT:
            events = [
                {"title": "遗忘之泉", "desc": "喝下泉水，你可以选择遗忘一个生词（跳过复习），或者回复 20 HP。"},
                {"title": "古老卷轴", "desc": "你发现了一张破损的语法卷轴，阅读它需要消耗 10 HP，但能获得 50 金币。"}
            ]
            self.data['event'] = random.choice(events)

# ==========================================
# 🗺️ 地图系统 (Map System)
# ==========================================
class MapSystem:
    def __init__(self, total_floors=5):
        self.floor = 0
        self.total_floors = total_floors
        self.current_node = None
        self.next_options = [] # 下一层可选的节点列表

    def generate_next_options(self):
        """生成下一层的 2-3 个可选路径（Roguelike 核心）"""
        self.floor += 1
        options = []
        
        # 最后一层强制是 Boss
        if self.floor == self.total_floors:
            return [Node(NodeType.BOSS, self.floor)]
        
        # 随机生成 2 个选项
        # 权重控制：战斗最常见，商店和事件较少
        weights = [NodeType.COMBAT, NodeType.COMBAT, NodeType.EVENT, NodeType.REST, NodeType.SHOP]
        
        type1 = random.choice(weights)
        type2 = random.choice(weights)
        
        # 确保两个选项尽量不一样，增加选择乐趣
        while type2 == type1:
            type2 = random.choice(weights)

        options.append(Node(type1, self.floor))
        options.append(Node(type2, self.floor))
        
        return options

# ==========================================
# 🎮 游戏管理器 (Game Manager)
# ==========================================
class GameManager:
    def __init__(self):
        # 1. 玩家数据
        if 'player' not in st.session_state:
            st.session_state.player = Player()
        
        # 2. 地图数据
        if 'game_map' not in st.session_state:
            st.session_state.game_map = MapSystem(total_floors=5)
            
        # 3. 游戏阶段
        if 'phase' not in st.session_state:
            st.session_state.phase = GamePhase.LOBBY
            
        # 4. 本局数据池 (Input)
        if 'run_words' not in st.session_state:
            st.session_state.run_words = [] # 本局输入的 15 个生词

    def start_run(self, raw_text):
        # 简单的 Mock 解析，实际接 AI 分析
        if USE_MOCK:
            # 模拟把输入文本切分成单词对象
            words = [{"word": w.strip(), "meaning": "测试释义"} for w in raw_text.split(',')]
            # 补齐一点假数据防止不够
            while len(words) < 15:
                words.append({"word": f"MockWord_{len(words)}", "meaning": "虚构的单词"})
        
        st.session_state.run_words = words[:15] # 取前15个
        st.session_state.game_map = MapSystem(total_floors=5) # 重置地图
        
        # 生成第一层的选项
        st.session_state.game_map.next_options = st.session_state.game_map.generate_next_options()
        st.session_state.phase = GamePhase.MAP_SELECT
        st.rerun()

    def enter_node(self, node):
        # 进入节点，生成内容
        node.generate_content(st.session_state.run_words)
        st.session_state.game_map.current_node = node
        st.session_state.phase = GamePhase.IN_NODE
        st.rerun()

    def resolve_node(self):
        # 结算节点，准备去下一层
        # 生成下一层的选项
        ms = st.session_state.game_map
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
        with c1:
            st.progress(p.hp / p.max_hp, f"HP: {p.hp}/{p.max_hp}")
        with c2:
            st.write(f"🗺️ Floor: {m.floor}/{m.total_floors}")
        with c3:
            st.write(f"💰 Gold: {p.gold}")

def render_lobby(gm):
    st.title("🏰 单词尖塔 (Spire of Vocab)")
    st.markdown("### 新的冒险")
    st.info("请输入 10-15 个你今天想攻克的生词（用逗号分隔）。这些词将化身为塔中的怪物。")
    
    default_text = "Ephemeral, Serendipity, Oblivion, Resilience, Cacophony, Luminous, Solitude, Epiphany, Nostalgia, Ethereal"
    user_input = st.text_area("Spellbook (Input)", default_text, height=100)
    
    if st.button("🩸 献祭单词并开始"):
        gm.start_run(user_input)

def render_map_select(gm):
    st.header("🛤️ 选择你的路径")
    st.markdown("前方的迷雾散去，你看到了两条岔路...")
    
    options = st.session_state.game_map.next_options
    
    col_opts = st.columns(len(options))
    for i, node in enumerate(options):
        with col_opts[i]:
            with st.container(border=True):
                st.markdown(f"### {node.type.value}")
                st.caption(f"Floor {node.level}")
                if st.button(f"前往 {node.type.name}", key=f"node_sel_{i}", use_container_width=True):
                    gm.enter_node(node)

def render_in_node(gm):
    node = st.session_state.game_map.current_node
    st.subheader(f"📍 当前位置: {node.type.value}")
    
    # === 不同的房间渲染逻辑 ===
    if node.type == NodeType.COMBAT:
        st.write(node.data['desc'])
        enemies = node.data['enemies']
        
        # 这里为了演示，简化战斗逻辑
        st.write("👻 **出现的怪物:**")
        cols = st.columns(len(enemies))
        for i, enemy in enumerate(enemies):
            with cols[i]:
                st.button(f"{enemy['word']}", disabled=True)
        
        st.markdown("---")
        if st.button("⚔️ 战斗开始 (模拟打赢)", type="primary"):
            st.session_state.player.gold += 20
            st.toast("战斗胜利！金币 +20")
            gm.resolve_node()
            
    elif node.type == NodeType.EVENT:
        evt = node.data['event']
        st.markdown(f"**{evt['title']}**")
        st.info(evt['desc'])
        if st.button("离开"):
            gm.resolve_node()
            
    elif node.type == NodeType.BOSS:
        st.error("👹 警告：BOSS 战！")
        st.markdown(f"**{node.data['boss_name']}** 正在注视着你...")
        st.info("AI 正在将本局的 15 个生词编织成噩梦文章...")
        # 这里应当接入你的 AI 接口生成文章
        
        with st.expander("📜 查看 Boss 本体 (文章)", expanded=True):
            st.write("*(此处显示由所有生词组成的生成的文章...)*")
            
        if st.button("🦄 发动致命一击 (阅读理解通关)"):
            gm.resolve_node()

def render_game():
    gm = GameManager()
    
    if st.session_state.phase != GamePhase.LOBBY:
        render_hud()
        
    if st.session_state.phase == GamePhase.LOBBY:
        render_lobby(gm)
    elif st.session_state.phase == GamePhase.MAP_SELECT:
        render_map_select(gm)
    elif st.session_state.phase == GamePhase.IN_NODE:
        render_in_node(gm)
    elif st.session_state.phase == GamePhase.VICTORY:
        st.balloons()
        st.title("🏆 爬塔成功！")
        if st.button("返回大厅"):
            st.session_state.phase = GamePhase.LOBBY
            st.rerun()

# ==========================================
# 🚀 启动
# ==========================================
st.set_page_config(page_title="Roguelike Vocab", layout="centered")
render_game()