"""
单词尖塔 v5.4 - Spire of Vocab
====================================
Major System Upgrade:
- Main Menu: Start / Continue / Word Library
- Smart Recommender: PINNED > GHOST > RANDOM
- Initial Deck: 5R + 2B + 1G
- Post-combat Drafting

启动方式: streamlit run v_game_5/main.py
"""

import streamlit as st
import random
import threading
import sys
from pathlib import Path

_current_dir = Path(__file__).parent
if str(_current_dir) not in sys.path:
    sys.path.insert(0, str(_current_dir))

from config import TOTAL_FLOORS, INITIAL_GOLD
from database import GameDB
from ai_service import CyberMind, MockGenerator
from models import GamePhase, NodeType, Player, WordCard, CardType
from systems import WordPool, MapSystem
from registries import EventRegistry
from ui.components import render_hud
from ui.renderers import (
    render_main_menu, render_word_library, render_map_select, 
    render_combat, render_boss, render_event, render_shop, render_rest,
    render_drafting, render_tower_prep
)


class GameManager:
    """游戏核心控制器 v5.4"""
    
    def __init__(self):
        self._init_session_state()
    
    def _init_session_state(self):
        if 'db' not in st.session_state:
            st.session_state.db = GameDB()
        
        if 'db_player' not in st.session_state:
            st.session_state.db_player = st.session_state.db.get_or_create_player()
        
        if 'player' not in st.session_state:
            st.session_state.player = Player(
                id=st.session_state.db_player['id'],
                gold=INITIAL_GOLD
            )
        
        if 'game_map' not in st.session_state:
            st.session_state.game_map = MapSystem(total_floors=TOTAL_FLOORS)
        
        if 'phase' not in st.session_state:
            st.session_state.phase = GamePhase.MAIN_MENU
        
        if 'word_pool' not in st.session_state:
            st.session_state.word_pool = None
        
        if 'ai' not in st.session_state:
            st.session_state.ai = CyberMind()
        
        if 'boss_article_cache' not in st.session_state:
            st.session_state.boss_article_cache = None
    
    def start_new_game(self):
        """开始新游戏"""
        player_id = st.session_state.db_player["id"]
        db = st.session_state.db
        
        # 1. 获取本局游戏池 (25红+12蓝+5金 = 42张)
        from config import GAME_POOL_RED, GAME_POOL_BLUE, GAME_POOL_GOLD
        from config import INITIAL_DECK_RED, INITIAL_DECK_BLUE, INITIAL_DECK_GOLD
        
        game_pool = db.get_game_pool(player_id, GAME_POOL_RED, GAME_POOL_BLUE, GAME_POOL_GOLD)
        
        if len(game_pool) < 10:
            st.warning("⚠️ 词库不足！请先在 Word Library 添加至少 10 个单词")
            return
        
        # 2. 从池中抽取初始卡组 (6红+2蓝+1金 = 9张)
        initial_deck = db.get_initial_deck_from_pool(game_pool, INITIAL_DECK_RED, INITIAL_DECK_BLUE, INITIAL_DECK_GOLD)
        
        # 3. 转换为 WordCard
        deck_cards = []
        for w in initial_deck:
            deck_cards.append(WordCard(
                word=w['word'],
                meaning=w['meaning'],
                tier=w.get('tier', 0),
                priority=w.get('priority', 'normal')
            ))
        
        # 4. 计算剩余池 (用于战利品抽取)
        deck_words = {c.word for c in deck_cards}
        remaining_pool = [w for w in game_pool if w['word'] not in deck_words]
        
        # 转换为 WordCard 列表
        remaining_pool_cards = []
        for w in remaining_pool:
            remaining_pool_cards.append(WordCard(
                word=w['word'],
                meaning=w['meaning'],
                tier=w.get('tier', 0),
                priority=w.get('priority', 'normal')
            ))
        
        # 5. 初始化玩家 (空deck，待Prep)
        st.session_state.player = Player(
            id=player_id,
            gold=INITIAL_GOLD,
            deck=[] # 空卡组
        )
        
        # 6. 保存全量池到 session (用于 Prep)
        # 注意：这里我们将所有42张卡都作为 candidates
        all_pool_cards = deck_cards + remaining_pool_cards
        st.session_state.full_draft_pool = all_pool_cards
        st.session_state.in_game_streak = {}
        
        # 7. 初始化地图
        st.session_state.game_map = MapSystem(total_floors=TOTAL_FLOORS)
        st.session_state.game_map.next_options = st.session_state.game_map.generate_next_options()
        
        # 8. Boss生成 (后台)
        all_words_list = [{**w, "word": w['word']} for w in game_pool]
        st.session_state.boss_generation_status = 'generating'
        self._start_background_boss_generation(all_words_list)
        
        # 清除旧状态
        for key in ['card_combat', 'boss_state', 'shop_items', 'draft_candidates', 'word_pool', 'prep_indices']:
            if key in st.session_state:
                del st.session_state[key]
        
        # 进入 Tower Prep 阶段
        st.session_state.phase = GamePhase.TOWER_PREP
        st.rerun()
    
    def continue_game(self):
        """继续游戏"""
        player_id = st.session_state.db_player["id"]
        save = st.session_state.db.get_continue_state(player_id)
        
        if not save:
            st.warning("没有可继续的存档")
            return
        
        # 恢复卡组
        deck_cards = []
        for w in save.get('deck', []):
            deck_cards.append(WordCard(
                word=w['word'],
                meaning=w['meaning'],
                tier=w.get('tier', 0)
            ))
        
        st.session_state.player = Player(
            id=player_id,
            gold=INITIAL_GOLD,
            deck=deck_cards
        )
        
        # 恢复地图
        st.session_state.game_map = MapSystem(total_floors=TOTAL_FLOORS)
        st.session_state.game_map.floor = save.get('floor', 0)
        st.session_state.game_map.next_options = st.session_state.game_map.generate_next_options()
        
        st.session_state.word_pool = WordPool(
            new_words=[{"word": c.word, "meaning": c.meaning, "tier": c.tier} for c in deck_cards if c.tier <= 1],
            review_words=[{"word": c.word, "meaning": c.meaning, "tier": c.tier} for c in deck_cards if c.tier > 1]
        )
        
        # v6.0 恢复本局游戏词池 (用于战利品奖励)
        from config import GAME_POOL_RED, GAME_POOL_BLUE, GAME_POOL_GOLD
        game_pool = st.session_state.db.get_game_pool(player_id, GAME_POOL_RED, GAME_POOL_BLUE, GAME_POOL_GOLD)
        deck_words = {c.word for c in deck_cards}
        st.session_state.game_word_pool = [
            WordCard(
                word=w['word'], 
                meaning=w['meaning'], 
                tier=w.get('tier', 0), 
                priority=w.get('priority', 'normal')
            ) for w in game_pool if w['word'] not in deck_words
        ]
        
        st.session_state.phase = GamePhase.MAP_SELECT
        st.rerun()
    
    def open_word_library(self):
        """打开单词图书馆"""
        st.session_state.phase = GamePhase.WORD_LIBRARY
        st.rerun()
    def back_to_menu(self):
        """返回主菜单"""
        st.session_state.phase = GamePhase.MAIN_MENU
        st.rerun()

    def complete_tower_prep(self, selected_cards: list, remaining_cards: list):
        """完成爬塔准备"""
        # 1. 设置卡组
        st.session_state.player.deck = selected_cards
        
        # 2. 设置词池 (用于loot)
        st.session_state.game_word_pool = remaining_cards
        
        # 3. 清理 prep 状态
        if 'full_draft_pool' in st.session_state:
            del st.session_state.full_draft_pool
        if 'prep_indices' in st.session_state:
            del st.session_state.prep_indices
            
        # 4. 保存进度
        st.session_state.db.save_run_state(
            st.session_state.player.id, 
            0, 
            [c.to_dict() for c in selected_cards]
        )
        
        # 5. 进入地图
        st.session_state.phase = GamePhase.MAP_SELECT
        st.rerun()
    
    def _start_background_boss_generation(self, all_words: list):
        """在后台线程中生成 Boss 文章"""
        def _generate():
            try:
                ai = CyberMind()
                word_list = [w['word'] for w in all_words if w.get('word')]
                
                article = ai.generate_article(word_list)
                if article and article.get('article_english'):
                    quizzes = ai.generate_quiz(word_list, article['article_english'])
                    st.session_state.boss_article_cache = {
                        'article': article,
                        'quizzes': quizzes
                    }
                else:
                    st.session_state.boss_article_cache = {
                        'article': MockGenerator.generate_article(word_list),
                        'quizzes': MockGenerator.generate_quiz(word_list)
                    }
                st.session_state.boss_generation_status = 'ready'
            except Exception:
                st.session_state.boss_article_cache = {
                    'article': MockGenerator.generate_article(word_list),
                    'quizzes': MockGenerator.generate_quiz(word_list)
                }
                st.session_state.boss_generation_status = 'ready'
        
        thread = threading.Thread(target=_generate, daemon=True)
        thread.start()
    
    def enter_node(self, node):
        """进入节点"""
        st.session_state.game_map.current_node = node
        st.session_state.phase = GamePhase.IN_NODE
        
        for key in ['card_combat', 'boss_state']:
            if key in st.session_state:
                del st.session_state[key]
        
        st.rerun()
    
    def resolve_node(self, trigger_draft: bool = False):
        """结算节点"""
        ms = st.session_state.game_map
        
        for key in ['card_combat', 'boss_state']:
            if key in st.session_state:
                del st.session_state[key]
        
        # 保存进度
        player = st.session_state.player
        st.session_state.db.save_run_state(
            player.id,
            ms.floor,
            [c.to_dict() for c in player.deck]
        )
        
        if ms.floor >= ms.total_floors:
            self.end_run(victory=True)
        elif trigger_draft:
            # 战后抓牌
            st.session_state.phase = GamePhase.DRAFTING
            st.rerun()
        else:
            ms.next_options = ms.generate_next_options()
            st.session_state.phase = GamePhase.MAP_SELECT
            st.rerun()
    
    def complete_draft(self, selected_card: WordCard = None):
        """完成抓牌"""
        if selected_card:
            st.session_state.player.add_card_to_deck(selected_card)
            # 更新词池
            if st.session_state.word_pool:
                st.session_state.word_pool.new_words.append({
                    "word": selected_card.word,
                    "meaning": selected_card.meaning,
                    "tier": selected_card.tier
                })
        
        if 'draft_candidates' in st.session_state:
            del st.session_state.draft_candidates
        
        ms = st.session_state.game_map
        ms.next_options = ms.generate_next_options()
        st.session_state.phase = GamePhase.MAP_SELECT
        st.rerun()
    
    def end_run(self, victory: bool = False):
        """结束本局"""
        player_id = st.session_state.db_player["id"]
        floor = st.session_state.game_map.floor
        
        words = [c.word for c in st.session_state.player.deck]
        st.session_state.db.end_run(player_id, floor, victory, words)
        
        st.session_state.boss_article_cache = None
        st.session_state.phase = GamePhase.VICTORY if victory else GamePhase.GAME_OVER
        st.rerun()
    
    def check_player_death(self) -> bool:
        if st.session_state.player.is_dead():
            self.end_run(victory=False)
            return True
        return False


def render_game():
    """游戏主渲染入口"""
    gm = GameManager()
    phase = st.session_state.phase
    
    # 主菜单和图书馆不显示 HUD
    if phase not in [GamePhase.MAIN_MENU, GamePhase.WORD_LIBRARY]:
        render_hud()
    
    if phase == GamePhase.MAIN_MENU:
        render_main_menu(gm.start_new_game, gm.continue_game, gm.open_word_library)
    
    elif phase == GamePhase.WORD_LIBRARY:
        render_word_library(gm.back_to_menu)
    
    elif phase == GamePhase.MAP_SELECT:
        render_map_select(gm.enter_node)
    
    elif phase == GamePhase.IN_NODE:
        node = st.session_state.game_map.current_node
        node_type = node.type.name
        
        if node_type in ["COMBAT", "ELITE"]:
            render_combat(
                lambda: gm.resolve_node(trigger_draft=True), 
                gm.check_player_death
            )
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
    
    elif phase == GamePhase.DRAFTING:
        render_drafting(gm.complete_draft)
    
    elif phase == GamePhase.TOWER_PREP:
        render_tower_prep(gm.complete_tower_prep)
    
    elif phase == GamePhase.VICTORY:
        st.balloons()
        st.title("🏆 通关！")
        st.success("所有单词已升级！")
        st.metric("本局金币", st.session_state.player.gold)
        if st.button("🔄 返回主菜单", type="primary"):
            st.session_state.player = Player(
                id=st.session_state.db_player['id'],
                gold=INITIAL_GOLD
            )
            st.session_state.phase = GamePhase.MAIN_MENU
            st.rerun()
    
    elif phase == GamePhase.GAME_OVER:
        st.error("💀 你的意识消散了...")
        if st.button("🔄 返回主菜单"):
            st.session_state.player = Player(
                id=st.session_state.db_player['id'],
                gold=INITIAL_GOLD
            )
            st.session_state.phase = GamePhase.MAIN_MENU
            st.rerun()


# ==========================================
# 🚀 启动
# ==========================================
st.set_page_config(page_title="单词尖塔 v5.4", page_icon="🏰", layout="wide")

st.markdown("""
<style>
    .highlight-word { color: #ff6b6b; font-weight: bold; }
    .relic-item { padding: 4px 8px; margin: 2px 0; border-radius: 4px; background: rgba(255,255,255,0.1); }
    .card-red { border-left: 4px solid #e74c3c; }
    .card-blue { border-left: 4px solid #3498db; }
    .card-gold { border-left: 4px solid #f39c12; }
</style>
""", unsafe_allow_html=True)

render_game()
