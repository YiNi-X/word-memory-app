# ==========================================
# 🖥️ 页面渲染器
# ==========================================
import sys
from pathlib import Path

# 添加父目录到路径
_parent = Path(__file__).parent.parent
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))

import streamlit as st
import random
import time
from typing import Callable

from models import GamePhase, NodeType, Player, CombatState, BossState
from registries import CombatRegistry, EventRegistry, ShopRegistry
from ai_service import CyberMind, MockGenerator
from ui.components import play_audio


def render_lobby(start_run_callback: Callable):
    """大厅页面"""
    st.title("🏰 单词尖塔 (Spire of Vocab)")
    
    # 玩家统计
    db_player = st.session_state.get('db_player', {})
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💰 累计金币", db_player.get("gold", 0))
    with col2:
        st.metric("🏆 胜利次数", db_player.get("victories", 0))
    with col3:
        st.metric("🎮 总场次", db_player.get("total_runs", 0))
    
    st.divider()
    
    st.markdown("### 📝 输入今天要攻克的生词")
    st.caption("用逗号分隔，每个词会自动配上释义 (支持 5-20 个词)")
    
    default_words = "Ephemeral, Serendipity, Oblivion, Resilience, Cacophony, Luminous, Solitude, Epiphany, Nostalgia, Ethereal"
    user_input = st.text_area("Spellbook", default_words, height=100)
    
    if st.button("🩸 献祭单词并开始", type="primary", use_container_width=True):
        start_run_callback(user_input)


def render_map_select(enter_node_callback: Callable):
    """地图选择页面"""
    st.header("🛤️ 选择你的路径")
    st.markdown("前方迷雾散去，你看到了岔路...")
    
    options = st.session_state.game_map.next_options
    cols = st.columns(len(options))
    
    for i, node in enumerate(options):
        with cols[i]:
            with st.container(border=True):
                # 获取节点显示信息
                st.markdown(f"### {node.type.value}")
                st.caption(f"Floor {node.level}")
                
                # 显示额外信息
                if node.type.name in ["COMBAT_NEW", "COMBAT_RECALL", "ELITE_MIXED", "ELITE_STRONG"]:
                    config = CombatRegistry.get(node.type.name)
                    if config:
                        st.caption(config.description)
                
                if st.button(f"前往", key=f"node_sel_{i}", use_container_width=True):
                    enter_node_callback(node)


def render_combat(resolve_node_callback: Callable, check_death_callback: Callable):
    """战斗页面渲染"""
    node = st.session_state.game_map.current_node
    combat_type = node.type.name
    
    # 获取战斗配置
    config = CombatRegistry.get(combat_type)
    if not config:
        st.error(f"未知战斗类型: {combat_type}")
        return
    
    enemies = node.data.get('enemies', [])
    
    # 初始化战斗状态
    if 'combat_state' not in st.session_state:
        st.session_state.combat_state = CombatState(
            enemies=enemies,
            damage_per_wrong=config.damage,
            gold_reward=config.gold_reward
        )
    
    cs = st.session_state.combat_state
    
    # 显示战斗信息
    st.markdown(f"### {config.icon} {config.name}")
    st.caption(config.description)
    
    # 特殊规则提示
    if config.special_rules.get("no_damage"):
        st.info("💡 此战斗答错不扣血！")
    if config.special_rules.get("track_errors"):
        if 'quiz_errors' not in st.session_state:
            st.session_state.quiz_errors = 0
    
    # 胜利判定
    if cs.is_complete:
        st.balloons()
        st.success(f"🎉 战斗胜利！清理了 {len(enemies)} 个单词。")
        
        # 处理特殊奖励/惩罚
        if config.special_rules.get("reward_type") == "free_item":
            errors = st.session_state.get('quiz_errors', 0)
            if errors == 0:
                st.success("🎁 全部答对！获得免费商品选择权！")
                st.session_state.player.inventory.append("FREE_SHOP_ITEM")
            else:
                penalty = st.session_state.player.gold // 2
                st.session_state.player.gold -= penalty
                st.error(f"答错 {errors} 题，扣除 {penalty} 金币！")
        
        if st.button(f"🎁 搜刮战利品 (+{config.gold_reward}G)", type="primary"):
            st.session_state.player.add_gold(config.gold_reward)
            resolve_node_callback()
        return
    
    current = cs.current_enemy
    
    # 战斗界面
    col_card, col_action = st.columns([1, 1])
    
    with col_card:
        tag = "🔄 复习词" if current.get('is_review') else "✨ 新词"
        with st.container(border=True):
            st.markdown(f"## 👻 怪物 {cs.current_idx + 1}/{len(enemies)}")
            st.caption(tag)
            st.markdown(f"# {current['word']}")
            
            if st.button("🔊 听音辨位", key=f"tts_{cs.current_idx}"):
                play_audio(current['word'])
            
            if cs.flipped:
                st.divider()
                st.markdown(f"**释义:** {current['meaning']}")
    
    with col_action:
        st.write("### 你的行动")
        
        if not cs.flipped:
            st.info("你遇到了一个生词怪物。")
            if st.button("🔍 洞察弱点 (翻看释义)", use_container_width=True):
                cs.flipped = True
                st.rerun()
        else:
            # 生成选项
            if cs.options is None:
                all_meanings = []
                word_pool = st.session_state.get('word_pool')
                if word_pool:
                    all_meanings = [w['meaning'] for w in word_pool.new_words + word_pool.review_words
                                   if w['meaning'] != current['meaning']]
                
                if len(all_meanings) >= 3:
                    distractors = random.sample(all_meanings, 3)
                else:
                    distractors = all_meanings + ["不知道", "需要学习", "猜测"][:3-len(all_meanings)]
                
                options = distractors + [current['meaning']]
                random.shuffle(options)
                cs.options = options
            
            st.write("⚔️ 选择正确的释义:")
            user_choice = st.radio("Options", cs.options, key=f"quiz_{cs.current_idx}", label_visibility="collapsed")
            
            if st.button("🗡️ 发动攻击", type="primary", use_container_width=True):
                if user_choice == current['meaning']:
                    st.toast("⚡ 暴击！", icon="💥")
                    st.session_state.player.add_gold(5)
                    cs.advance()
                    st.rerun()
                else:
                    if config.special_rules.get("track_errors"):
                        st.session_state.quiz_errors = st.session_state.get('quiz_errors', 0) + 1
                    
                    if not config.special_rules.get("no_damage"):
                        st.session_state.player.change_hp(-cs.damage_per_wrong)
                        st.error(f"🛡️ 攻击偏离！受到 {cs.damage_per_wrong} 点反伤！")
                        if check_death_callback():
                            return
                    else:
                        st.warning("答错了，但此战斗不扣血！继续加油！")
                    
                    # 答错也继续下一个
                    cs.advance()
                    time.sleep(0.5)
                    st.rerun()


def render_boss(resolve_node_callback: Callable, check_death_callback: Callable):
    """Boss 战渲染"""
    node = st.session_state.game_map.current_node
    
    # 初始化 Boss 状态
    if 'boss_state' not in st.session_state:
        # 从 word_pool 获取所有遇到的词
        word_pool = st.session_state.get('word_pool')
        all_words = word_pool.get_all_encountered() if word_pool else []
        
        # Boss 血量与词数成正比
        boss_hp = max(50, len(all_words) * 10)
        
        st.session_state.boss_state = BossState(
            boss_hp=boss_hp,
            boss_max_hp=boss_hp
        )
        node.data['enemies'] = all_words
    
    bs = st.session_state.boss_state
    enemies = node.data.get('enemies', [])
    
    # Boss 血条
    st.markdown(f"## 👹 The Syntax Colossus")
    st.caption(f"由 {len(enemies)} 个单词的记忆碎片组成")
    boss_pct = max(0, bs.boss_hp / bs.boss_max_hp)
    st.progress(boss_pct, f"Boss HP: {bs.boss_hp}/{bs.boss_max_hp}")
    
    # 阶段 1: 生成文章
    if bs.phase == 'loading':
        st.info("📝 Boss 正在觉醒... 生成文章中...")
        
        with st.spinner("AI 正在将所有单词编织成噩梦文章..."):
            ai = st.session_state.get('ai') or CyberMind()
            
            # 调用 AI 生成文章
            article = ai.generate_article(enemies)
            
            if article and article.get('article_english'):
                bs.article = article
                # 生成 Quiz
                bs.quizzes = ai.generate_quiz(enemies, article['article_english'])
            else:
                # API 失败，使用 Mock
                bs.api_error = ai.get_last_error()
                bs.article = MockGenerator.generate_article(enemies)
                bs.quizzes = MockGenerator.generate_quiz(enemies)
            
            bs.phase = 'article'
            st.rerun()
    
    # 阶段 2: 显示文章
    elif bs.phase == 'article':
        if bs.api_error:
            st.warning(f"⚠️ AI 连接失败: {bs.api_error}")
            st.info("已切换到离线模式，使用模拟文章。")
        
        if bs.article:
            with st.expander("📜 Boss 本体 (阅读文章)", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**English**")
                    st.markdown(bs.article.get('article_english', ''), unsafe_allow_html=True)
                with col2:
                    st.markdown("**中文翻译**")
                    st.markdown(bs.article.get('article_chinese', ''))
        
        st.info(f"📊 文章包含 {len(enemies)} 个单词，将生成 {len(bs.quizzes.get('quizzes', []))} 道题目")
        
        if st.button("⚔️ 准备战斗", type="primary", use_container_width=True):
            bs.phase = 'quiz'
            st.rerun()
    
    # 阶段 3: Quiz 战斗
    elif bs.phase == 'quiz':
        quizzes = bs.quizzes.get('quizzes', []) if bs.quizzes else []
        
        # Boss 死亡
        if bs.boss_hp <= 0:
            bs.phase = 'victory'
            st.rerun()
            return
        
        # 所有题目完成但 Boss 未死
        if bs.quiz_idx >= len(quizzes):
            st.warning("⚠️ 所有技能已释放，Boss 仍存活...")
            if st.button("🔄 再战一轮"):
                bs.quiz_idx = 0
                st.rerun()
            return
        
        q = quizzes[bs.quiz_idx]
        
        st.markdown(f"### 🔥 Boss 技能 [{bs.quiz_idx + 1}/{len(quizzes)}]")
        with st.container(border=True):
            st.markdown(f"**{q['question']}**")
            choice = st.radio("选择答案:", q['options'], key=f"boss_q_{bs.quiz_idx}")
            
            if st.button("✨ 释放反击", type="primary"):
                damage = q.get('damage', 20)
                if choice == q['answer']:
                    hit_damage = 30
                    bs.boss_hp -= hit_damage
                    st.toast(f"💥 暴击！Boss -{hit_damage} HP", icon="⚡")
                    st.success(f"✅ 正确！{q.get('explanation', '')}")
                else:
                    st.session_state.player.change_hp(-damage)
                    st.error(f"❌ 错误！正确答案: {q['answer']}")
                    st.info(q.get('explanation', ''))
                    if check_death_callback():
                        return
                
                bs.quiz_idx += 1
                time.sleep(1)
                st.rerun()
    
    # 阶段 4: 胜利
    elif bs.phase == 'victory':
        st.balloons()
        st.success("🏆 Boss 已被击败！你成功净化了这片记忆！")
        if st.button("🎁 获取胜利奖励 (+100G)", type="primary"):
            st.session_state.player.add_gold(100)
            resolve_node_callback()


def render_event(resolve_node_callback: Callable):
    """事件页面渲染"""
    node = st.session_state.game_map.current_node
    event_data = node.data.get('event')
    
    if not event_data:
        # 随机选择事件
        event_id, event_config = EventRegistry.get_random()
        node.data['event'] = {'id': event_id, 'config': event_config}
        event_data = node.data['event']
    
    config = event_data.get('config')
    if not config:
        st.error("事件数据错误")
        if st.button("离开"):
            resolve_node_callback()
        return
    
    st.markdown(f"### {config.icon} {config.name}")
    st.info(config.description)
    if config.flavor_text:
        st.caption(config.flavor_text)
    
    # 渲染选项
    for i, choice in enumerate(config.choices):
        disabled = False
        
        # 检查金币条件
        if choice.cost_gold > 0 and st.session_state.player.gold < choice.cost_gold:
            disabled = True
        
        if st.button(choice.text, key=f"event_choice_{i}", disabled=disabled, use_container_width=True):
            _apply_event_effect(choice)
            resolve_node_callback()


def _apply_event_effect(choice):
    """应用事件效果"""
    player = st.session_state.player
    
    # 扣除金币
    if choice.cost_gold > 0:
        player.gold -= choice.cost_gold
    
    effect = choice.effect
    value = choice.value
    
    if effect == "heal":
        player.change_hp(value)
    elif effect == "damage":
        player.change_hp(value)
    elif effect == "gold":
        player.add_gold(value)
    elif effect == "gold_random":
        amount = random.randint(value[0], value[1])
        player.add_gold(amount)
    elif effect == "max_hp":
        player.max_hp += value
        st.toast(f"最大 HP +{value}", icon="❤️")
    elif effect == "full_heal":
        player.hp = player.max_hp
        st.toast("HP 已回满！", icon="💚")
    elif effect == "item":
        player.inventory.append(value)
        st.toast(f"获得道具: {value}", icon="📦")
    elif effect == "relic":
        from registries import RelicRegistry
        if value == "random":
            relic_id, relic = RelicRegistry.get_random()
            player.relics.append(relic_id)
            st.toast(f"获得圣遗物: {relic.name}", icon="🏆")
        else:
            player.relics.append(value)
    elif effect == "trade":
        player.change_hp(value.get('hp', 0))
        player.add_gold(value.get('gold', 0))
    elif effect == "none":
        pass


def render_shop(resolve_node_callback: Callable):
    """商店页面渲染"""
    st.header("🛒 地精商店")
    st.caption(f"你的金币: 💰 {st.session_state.player.gold}")
    
    # 检查是否有免费商品权限
    has_free_item = "FREE_SHOP_ITEM" in st.session_state.player.inventory
    if has_free_item:
        st.success("🎁 你有一次免费选购机会！")
    
    # 获取商品
    if 'shop_items' not in st.session_state:
        st.session_state.shop_items = ShopRegistry.get_random_selection(4)
    
    items = st.session_state.shop_items
    cols = st.columns(len(items))
    
    for i, (item_id, item) in enumerate(items.items()):
        with cols[i]:
            with st.container(border=True):
                st.markdown(f"### {item.icon} {item.name}")
                st.markdown(f"**{item.description}**")
                
                if has_free_item:
                    st.markdown("💰 **免费！**")
                else:
                    st.markdown(f"💰 {item.price}G")
                
                can_buy = has_free_item or st.session_state.player.gold >= item.price
                
                if st.button(f"购买", key=f"shop_{item_id}", disabled=not can_buy, use_container_width=True):
                    if has_free_item:
                        st.session_state.player.inventory.remove("FREE_SHOP_ITEM")
                    else:
                        st.session_state.player.gold -= item.price
                    
                    _apply_shop_item(item)
                    st.rerun()
    
    st.divider()
    if st.button("🚪 离开商店", use_container_width=True):
        if 'shop_items' in st.session_state:
            del st.session_state.shop_items
        resolve_node_callback()


def _apply_shop_item(item):
    """应用商店物品效果"""
    player = st.session_state.player
    
    if item.effect == "heal":
        player.change_hp(item.value)
    elif item.effect == "max_hp":
        player.max_hp += item.value
        st.toast(f"最大 HP +{item.value}", icon="❤️")
    elif item.effect == "shield":
        player.inventory.append("SHIELD")
        st.toast("获得: 逻辑护盾", icon="🛡️")
    elif item.effect == "hint":
        player.inventory.append("HINT")
        st.toast("获得: 智慧卷轴", icon="📚")
    elif item.effect == "damage_reduce":
        player.inventory.append("DAMAGE_REDUCE")
        st.toast("获得: 坚韧护符", icon="🔮")
    elif item.effect == "gold_boost":
        player.inventory.append("GOLD_BOOST")
        st.toast("获得: 财运符文", icon="💎")


def render_rest(resolve_node_callback: Callable):
    """休息页面渲染"""
    st.header("🔥 营地")
    st.info("在温暖的篝火旁休息，恢复精力...")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("😴 休息 (+30 HP)", use_container_width=True):
            st.session_state.player.change_hp(30)
            resolve_node_callback()
    with col2:
        if st.button("🏃 跳过休息", use_container_width=True):
            resolve_node_callback()
