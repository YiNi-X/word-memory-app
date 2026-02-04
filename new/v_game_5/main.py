"""
单词尖塔 v5.0 - Spire of Vocab
====================================
模块化架构版

启动方式: streamlit run v_game_5/main.py
"""

import streamlit as st
import random
import sys
from pathlib import Path

# 添加当前目录到 Python 路径
_current_dir = Path(__file__).parent
if str(_current_dir) not in sys.path:
    sys.path.insert(0, str(_current_dir))

# 导入模块
from config import TOTAL_FLOORS
from database import GameDB
from ai_service import CyberMind
from models import GamePhase, NodeType, Player
from systems import WordPool, MapSystem
from registries import CombatRegistry, EventRegistry
from ui.components import render_hud
from ui.renderers import (
    render_lobby, render_map_select, render_combat,
    render_boss, render_event, render_shop, render_rest
)


# ==========================================
# 🎮 GameManager: 游戏总管
# ==========================================
class GameManager:
    """
    游戏核心控制器
    
    职责：
    1. 初始化游戏状态
    2. 管理游戏生命周期
    3. 协调各系统交互
    """
    
    def __init__(self):
        self._init_session_state()
    
    def _init_session_state(self):
        """初始化会话状态"""
        if 'db' not in st.session_state:
            st.session_state.db = GameDB()
        
        if 'db_player' not in st.session_state:
            st.session_state.db_player = st.session_state.db.get_or_create_player()
        
        if 'player' not in st.session_state:
            db_p = st.session_state.db_player
            st.session_state.player = Player(id=db_p['id'], gold=db_p.get('gold', 0))
        
        if 'game_map' not in st.session_state:
            st.session_state.game_map = MapSystem(total_floors=TOTAL_FLOORS)
        
        if 'phase' not in st.session_state:
            st.session_state.phase = GamePhase.LOBBY
        
        if 'word_pool' not in st.session_state:
            st.session_state.word_pool = None
        
        if 'ai' not in st.session_state:
            st.session_state.ai = CyberMind()
    
    def start_run(self, raw_text: str):
        """
        开始新的一局
        
        Args:
            raw_text: 用户输入的单词 (逗号分隔)
        """
        # 解析单词
        words = [w.strip() for w in raw_text.split(',') if w.strip()]
        new_words = [{"word": w, "meaning": "待学习"} for w in words]
        
        # ⚠️ 不再填充占位符！只使用用户实际输入的词
        if len(new_words) < 5:
            st.warning("至少需要 5 个单词！")
            return
        
        # 获取复习词
        player_id = st.session_state.db_player["id"]
        review_words = st.session_state.db.get_review_words(player_id, count=10)
        
        # 初始化单词池
        st.session_state.word_pool = WordPool(new_words, review_words)
        
        # 重置游戏状态
        st.session_state.game_map = MapSystem(total_floors=TOTAL_FLOORS)
        st.session_state.game_map.next_options = st.session_state.game_map.generate_next_options()
        st.session_state.player.hp = st.session_state.player.max_hp
        st.session_state.phase = GamePhase.MAP_SELECT
        
        # 清除旧状态
        for key in ['combat_state', 'boss_state', 'shop_items', 'quiz_errors']:
            if key in st.session_state:
                del st.session_state[key]
        
        st.rerun()
    
    def enter_node(self, node):
        """进入节点"""
        # 生成节点内容
        self._generate_node_content(node)
        
        st.session_state.game_map.current_node = node
        st.session_state.phase = GamePhase.IN_NODE
        
        # 清除旧战斗状态
        for key in ['combat_state', 'boss_state', 'quiz_errors']:
            if key in st.session_state:
                del st.session_state[key]
        
        st.rerun()
    
    def _generate_node_content(self, node):
        """根据节点类型生成内容"""
        word_pool = st.session_state.word_pool
        node_type = node.type.name
        
        # 战斗类节点
        if node_type in ["COMBAT_NEW", "COMBAT_RECALL", "ELITE_MIXED", "ELITE_STRONG", "EVENT_QUIZ"]:
            config = CombatRegistry.get(node_type)
            if config:
                min_count, max_count = config.word_count
                count = random.randint(min_count, max_count)
                
                if config.word_source == "new":
                    node.data['enemies'] = word_pool.draw_new(count)
                elif config.word_source == "review":
                    node.data['enemies'] = word_pool.draw_review(count)
                elif config.word_source == "mixed":
                    node.data['enemies'] = word_pool.draw_mixed(count)
        
        # Boss 节点 - 使用所有遇到的词
        elif node_type == "BOSS":
            # Boss 的 enemies 在 render_boss 中动态获取
            pass
        
        # 事件节点
        elif node_type == "EVENT_RANDOM":
            event_id, event_config = EventRegistry.get_random()
            node.data['event'] = {'id': event_id, 'config': event_config}
    
    def resolve_node(self):
        """结算节点，进入下一层"""
        ms = st.session_state.game_map
        
        # 清除战斗状态
        for key in ['combat_state', 'boss_state', 'quiz_errors']:
            if key in st.session_state:
                del st.session_state[key]
        
        # 保存金币
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
    
    def end_run(self, victory: bool = False):
        """结束本局"""
        player_id = st.session_state.db_player["id"]
        floor = st.session_state.game_map.floor
        
        word_pool = st.session_state.word_pool
        words = [w["word"] for w in word_pool.new_words] if word_pool else []
        
        # 记录到数据库
        st.session_state.db.record_run(player_id, floor, victory, words)
        st.session_state.db.update_gold(player_id, st.session_state.player.gold)
        
        # 胜利时把词汇加入 Deck
        if victory and word_pool:
            for w in word_pool.new_words:
                st.session_state.db.add_to_deck(player_id, w["word"], w["meaning"])
        
        st.session_state.phase = GamePhase.VICTORY if victory else GamePhase.GAME_OVER
        st.rerun()
    
    def check_player_death(self) -> bool:
        """检查玩家是否死亡"""
        if st.session_state.player.is_dead():
            self.end_run(victory=False)
            return True
        return False


# ==========================================
# 🖥️ 主渲染函数
# ==========================================
def render_game():
    """游戏主渲染入口"""
    gm = GameManager()
    phase = st.session_state.phase
    
    # 非大厅阶段显示 HUD
    if phase != GamePhase.LOBBY:
        render_hud()
    
    # 路由到对应渲染器
    if phase == GamePhase.LOBBY:
        render_lobby(gm.start_run)
    
    elif phase == GamePhase.MAP_SELECT:
        render_map_select(gm.enter_node)
    
    elif phase == GamePhase.IN_NODE:
        node = st.session_state.game_map.current_node
        node_type = node.type.name
        
        if node_type in ["COMBAT_NEW", "COMBAT_RECALL", "ELITE_MIXED", "ELITE_STRONG", "EVENT_QUIZ"]:
            render_combat(gm.resolve_node, gm.check_player_death)
        elif node_type == "BOSS":
            render_boss(gm.resolve_node, gm.check_player_death)
        elif node_type == "EVENT_RANDOM":
            render_event(gm.resolve_node)
        elif node_type == "SHOP":
            render_shop(gm.resolve_node)
        elif node_type == "REST":
            render_rest(gm.resolve_node)
        else:
            st.error(f"未知节点类型: {node_type}")
            if st.button("强制返回"):
                gm.resolve_node()
    
    elif phase == GamePhase.VICTORY:
        st.balloons()
        st.title("🏆 通关！")
        st.success("你成功攀登了单词尖塔！所有新词已加入你的 Deck！")
        st.metric("获得金币", st.session_state.player.gold)
        if st.button("🔄 再来一局", type="primary"):
            st.session_state.phase = GamePhase.LOBBY
            st.rerun()
    
    elif phase == GamePhase.GAME_OVER:
        st.error("💀 你的意识消散了...")
        st.markdown(f"到达层数: {st.session_state.game_map.floor}")
        if st.button("🔄 重新开始"):
            st.session_state.phase = GamePhase.LOBBY
            db_p = st.session_state.db_player
            st.session_state.player = Player(id=db_p['id'], gold=db_p.get('gold', 0))
            st.rerun()


# ==========================================
# 🚀 启动入口
# ==========================================
st.set_page_config(page_title="单词尖塔 v5", page_icon="🏰", layout="centered")

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
