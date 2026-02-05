"""
单词尖塔 v5.3 - Spire of Vocab
====================================
Word = Card 战斗系统 + 游戏平衡优化

启动方式: streamlit run v_game_5/main.py
"""

import streamlit as st
import random
import sys
from pathlib import Path

_current_dir = Path(__file__).parent
if str(_current_dir) not in sys.path:
    sys.path.insert(0, str(_current_dir))

from config import TOTAL_FLOORS, INITIAL_GOLD
from database import GameDB
from ai_service import CyberMind, MockGenerator
from models import GamePhase, NodeType, Player
from systems import WordPool, MapSystem
from registries import EventRegistry
from ui.components import render_hud
from ui.renderers import (
    render_lobby, render_map_select, render_combat,
    render_boss, render_event, render_shop, render_rest
)


class GameManager:
    """游戏核心控制器"""
    
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
            # 使用固定初始金币
            st.session_state.player = Player(id=db_p['id'], gold=INITIAL_GOLD)
        
        if 'game_map' not in st.session_state:
            st.session_state.game_map = MapSystem(total_floors=TOTAL_FLOORS)
        
        if 'phase' not in st.session_state:
            st.session_state.phase = GamePhase.LOBBY
        
        if 'word_pool' not in st.session_state:
            st.session_state.word_pool = None
        
        if 'ai' not in st.session_state:
            st.session_state.ai = CyberMind()
        
        # 后台生成的文章缓存
        if 'boss_article_cache' not in st.session_state:
            st.session_state.boss_article_cache = None
    
    def start_run(self, raw_text: str):
        """开始新的一局"""
        words = [w.strip() for w in raw_text.split(',') if w.strip()]
        
        if len(words) < 5:
            st.warning("至少需要 5 个单词！")
            return
        
        # 使用 AI 获取释义
        with st.spinner("🧠 AI 正在分析单词释义..."):
            ai = st.session_state.get('ai') or CyberMind()
            word_analysis = ai.analyze_words(words)
            
            if word_analysis and word_analysis.get('words'):
                new_words = []
                for w in word_analysis['words']:
                    new_words.append({
                        "word": w.get('word', ''),
                        "meaning": w.get('meaning', '释义获取失败'),
                        "is_review": False,
                        "tier": 0
                    })
                    if w.get('meaning'):
                        st.session_state.db.add_to_distractor_pool(
                            w.get('word', ''), 
                            w.get('meaning', '')
                        )
            else:
                st.warning("⚠️ AI 释义获取失败")
                new_words = [{"word": w, "meaning": "释义待确认", "is_review": False, "tier": 0} for w in words]
        
        # 获取复习词 (系统自动选择)
        player_id = st.session_state.db_player["id"]
        review_words = st.session_state.db.get_review_words(player_id, count=10)
        
        # 初始化单词池
        st.session_state.word_pool = WordPool(new_words, review_words)
        
        # 后台生成 Boss 文章 (减少等待时间)
        self._generate_boss_article_background(new_words + review_words)
        
        # 重置游戏状态
        st.session_state.game_map = MapSystem(total_floors=TOTAL_FLOORS)
        st.session_state.game_map.next_options = st.session_state.game_map.generate_next_options()
        
        # 固定初始金币 50
        st.session_state.player = Player(
            id=st.session_state.db_player['id'],
            gold=INITIAL_GOLD
        )
        st.session_state.phase = GamePhase.MAP_SELECT
        
        # 清除旧状态
        for key in ['card_combat', 'boss_state', 'shop_items']:
            if key in st.session_state:
                del st.session_state[key]
        
        st.rerun()
    
    def _generate_boss_article_background(self, all_words: list):
        """后台生成 Boss 文章"""
        try:
            ai = st.session_state.get('ai') or CyberMind()
            word_list = [w['word'] for w in all_words if w.get('word')]
            
            # 生成文章
            article = ai.generate_article(word_list)
            if article and article.get('article_english'):
                # 生成 Quiz
                quizzes = ai.generate_quiz(word_list, article['article_english'])
                st.session_state.boss_article_cache = {
                    'article': article,
                    'quizzes': quizzes
                }
            else:
                # 使用 Mock
                st.session_state.boss_article_cache = {
                    'article': MockGenerator.generate_article(word_list),
                    'quizzes': MockGenerator.generate_quiz(word_list)
                }
        except Exception as e:
            st.session_state.boss_article_cache = None
    
    def enter_node(self, node):
        """进入节点"""
        st.session_state.game_map.current_node = node
        st.session_state.phase = GamePhase.IN_NODE
        
        for key in ['card_combat', 'boss_state']:
            if key in st.session_state:
                del st.session_state[key]
        
        st.rerun()
    
    def resolve_node(self):
        """结算节点"""
        ms = st.session_state.game_map
        
        for key in ['card_combat', 'boss_state']:
            if key in st.session_state:
                del st.session_state[key]
        
        # 不保存金币到数据库 (每局独立)
        
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
        
        st.session_state.db.record_run(player_id, floor, victory, words)
        
        if victory and word_pool:
            for w in word_pool.new_words:
                st.session_state.db.add_or_update_word(
                    player_id, w["word"], w["meaning"], tier=1
                )
        
        # 清除 Boss 文章缓存
        st.session_state.boss_article_cache = None
        
        st.session_state.phase = GamePhase.VICTORY if victory else GamePhase.GAME_OVER
        st.rerun()
    
    def check_player_death(self) -> bool:
        """检查玩家是否死亡"""
        if st.session_state.player.is_dead():
            self.end_run(victory=False)
            return True
        return False


def render_game():
    """游戏主渲染入口"""
    gm = GameManager()
    phase = st.session_state.phase
    
    if phase != GamePhase.LOBBY:
        render_hud()
    
    if phase == GamePhase.LOBBY:
        render_lobby(gm.start_run)
    
    elif phase == GamePhase.MAP_SELECT:
        render_map_select(gm.enter_node)
    
    elif phase == GamePhase.IN_NODE:
        node = st.session_state.game_map.current_node
        node_type = node.type.name
        
        if node_type in ["COMBAT", "ELITE"]:
            render_combat(gm.resolve_node, gm.check_player_death)
        elif node_type == "BOSS":
            render_boss(gm.resolve_node, gm.check_player_death)
        elif node_type == "EVENT":
            render_event(gm.resolve_node)
        elif node_type == "SHOP":
            render_shop(gm.resolve_node)
        elif node_type == "REST":
            render_rest(gm.resolve_node)
        else:
            st.error(f"未知节点: {node_type}")
            if st.button("强制返回"):
                gm.resolve_node()
    
    elif phase == GamePhase.VICTORY:
        st.balloons()
        st.title("🏆 通关！")
        st.success("所有新词已加入 Deck！")
        st.metric("本局金币", st.session_state.player.gold)
        if st.button("🔄 再来一局", type="primary"):
            # 重置金币为初始值
            st.session_state.player = Player(
                id=st.session_state.db_player['id'],
                gold=INITIAL_GOLD
            )
            st.session_state.phase = GamePhase.LOBBY
            st.rerun()
    
    elif phase == GamePhase.GAME_OVER:
        st.error("💀 你的意识消散了...")
        if st.button("🔄 重新开始"):
            # 重置金币为初始值
            st.session_state.player = Player(
                id=st.session_state.db_player['id'],
                gold=INITIAL_GOLD
            )
            st.session_state.phase = GamePhase.LOBBY
            st.rerun()


# ==========================================
# 🚀 启动
# ==========================================
st.set_page_config(page_title="单词尖塔 v5.3", page_icon="🏰", layout="wide")

st.markdown("""
<style>
    .highlight-word { 
        color: #ff6b6b; 
        font-weight: bold; 
    }
    .relic-item {
        padding: 4px 8px;
        margin: 2px 0;
        border-radius: 4px;
        background: rgba(255,255,255,0.1);
    }
</style>
""", unsafe_allow_html=True)

render_game()
