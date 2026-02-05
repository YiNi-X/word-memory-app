# ==========================================
# 🎴 卡牌效果注册表
# ==========================================
"""
📝 扩展指南：添加新卡牌效果

在对应颜色的列表中添加新效果:
CardEffect(
    name="效果名称",
    icon="🔥",
    description="效果描述",
    on_correct=lambda ctx: ...,  # 答对时执行
    on_wrong=lambda ctx: ...     # 答错时执行 (可选)
)

ctx 包含:
- player: 玩家对象
- enemy: 敌人对象
- cs: 战斗状态
- card: 当前卡牌
"""

from dataclasses import dataclass, field
from typing import Callable, Optional, Dict, List, Any
from enum import Enum


@dataclass
class EffectContext:
    """效果执行上下文"""
    player: Any
    enemy: Any
    cs: Any  # CardCombatState
    card: Any  # WordCard
    st: Any  # streamlit 模块


@dataclass
class CardEffect:
    """卡牌效果配置"""
    name: str
    icon: str
    description: str
    on_correct: Callable[[EffectContext], None] = None
    on_wrong: Callable[[EffectContext], None] = None


# ==========================================
# 🟥 红卡效果 - 狂暴型
# ==========================================
def _red_heavy_strike(ctx: EffectContext):
    """重击：造成伤害"""
    damage = ctx.card.damage
    if ctx.cs.next_card_x2:
        damage *= 2
        ctx.cs.next_card_x2 = False
        ctx.st.toast("⚡ 效果翻倍！", icon="✨")
    ctx.enemy.take_damage(damage)
    ctx.st.toast(f"⚔️ 造成 {damage} 伤害！", icon="💥")


def _red_self_harm(ctx: EffectContext):
    """狂暴惩罚：答错自伤"""
    penalty = ctx.card.penalty
    ctx.player.change_hp(-penalty)
    ctx.st.error(f"💥 狂暴反噬！受到 {penalty} 伤害")


RED_EFFECTS = CardEffect(
    name="重击",
    icon="⚔️",
    description="造成 25 伤害，答错自伤 10",
    on_correct=_red_heavy_strike,
    on_wrong=_red_self_harm
)


# ==========================================
# 🟦 蓝卡效果 - 均衡型
# ==========================================
def _blue_hybrid_attack(ctx: EffectContext):
    """混合攻击：造成伤害 + 护甲"""
    damage = ctx.card.damage
    armor = ctx.card.block
    if ctx.cs.next_card_x2:
        damage *= 2
        armor *= 2
        ctx.cs.next_card_x2 = False
        ctx.st.toast("⚡ 效果翻倍！", icon="✨")
    ctx.enemy.take_damage(damage)
    ctx.player.add_armor(armor)
    ctx.st.toast(f"⚔️ {damage} 伤害 + 🛡️ {armor} 护甲", icon="💎")
    
    # 检查蓝卡回血 buff（铁匠营地升级效果）
    # v6.0: 检查单卡 Buff 或 玩家全局 Buff (兼容旧存档)
    if hasattr(ctx.card, 'is_temporary_buffed') and ctx.card.is_temporary_buffed:
        ctx.player.change_hp(5)
        ctx.st.toast("💚 蓝卡回血 +5", icon="❤️‍🩹")


def _blue_no_penalty(ctx: EffectContext):
    """均衡型无惩罚"""
    pass


BLUE_EFFECTS = CardEffect(
    name="混合打击",
    icon="💎",
    description="造成 15 伤害，获得 10 护甲",
    on_correct=_blue_hybrid_attack,
    on_wrong=_blue_no_penalty
)


# ==========================================
# 🟨 金卡效果 - 辅助型
# ==========================================
def _gold_empower(ctx: EffectContext):
    """智慧光环：下张卡效果翻倍 + 抽 1 张牌"""
    ctx.cs.next_card_x2 = True
    ctx.st.toast("✨ 智慧光环！下张卡效果 x2", icon="🌟")
    
    # 抽 1 张牌到弹仓
    if ctx.cs.draw_pile:
        drawn = ctx.cs.draw_pile.pop(0)
        if ctx.cs.load_card(drawn):
            ctx.st.toast(f"📥 抽取了 {drawn.word}", icon="🎴")


def _gold_draw_two(ctx: EffectContext):
    """快速抽取：从抽牌堆抽 2 张"""
    drawn_count = 0
    for _ in range(2):
        if ctx.cs.draw_pile:
            drawn = ctx.cs.draw_pile.pop(0)
            if ctx.cs.load_card(drawn):
                drawn_count += 1
    if drawn_count > 0:
        ctx.st.toast(f"📥 抽取了 {drawn_count} 张牌", icon="🎴")


def _gold_heal(ctx: EffectContext):
    """恢复：治疗 HP"""
    heal = 10 # 金卡默认治疗 10? 或者是 5?
    if ctx.cs.next_card_x2:
        heal *= 2
        ctx.cs.next_card_x2 = False
    ctx.player.change_hp(heal)
    ctx.st.toast(f"💚 治疗 {heal} HP", icon="❤️‍🩹")


def _gold_no_penalty(ctx: EffectContext):
    """辅助型无惩罚"""
    pass


GOLD_EFFECTS = CardEffect(
    name="智慧辅助",
    icon="✨",
    description="下张卡效果翻倍 + 抽 1 张牌",
    on_correct=_gold_empower,
    on_wrong=_gold_no_penalty
)


# ==========================================
# 🖤 黑卡效果 - 诅咒型
# ==========================================
def _black_curse_attack(ctx: EffectContext):
    """诅咒打击：造成伤害"""
    damage = ctx.card.damage
    if ctx.cs.next_card_x2:
        damage *= 2
        ctx.cs.next_card_x2 = False
        ctx.st.toast("⚡ 诅咒翻倍！", icon="💀")
    ctx.enemy.take_damage(damage)
    ctx.st.toast(f"🖤 诅咒爆发！造成 {damage} 伤害", icon="💀")


def _black_curse_backfire(ctx: EffectContext):
    """诅咒反噬：受到高额伤害"""
    penalty = ctx.card.penalty
    ctx.player.change_hp(-penalty)
    ctx.st.error(f"💀 诅咒反噬！受到 {penalty} 伤害")


BLACK_EFFECTS = CardEffect(
    name="诅咒打击",
    icon="🖤",
    description="答对造成 50 伤害，答错受到 50 伤害",
    on_correct=_black_curse_attack,
    on_wrong=_black_curse_backfire
)


# ==========================================
# 效果注册表
# ==========================================
class CardEffectRegistry:
    """卡牌效果注册表管理器"""
    
    # 主效果映射 (每种颜色的默认效果)
    EFFECTS = {
        "RED_BERSERK": RED_EFFECTS,
        "BLUE_HYBRID": BLUE_EFFECTS,
        "GOLD_SUPPORT": GOLD_EFFECTS,
        "BLACK_CURSE": BLACK_EFFECTS
    }
    
    @classmethod
    def get_effect(cls, card_type_name: str) -> CardEffect:
        """获取卡牌类型对应的效果"""
        return cls.EFFECTS.get(card_type_name)
    
    @classmethod
    def apply_effect(cls, card_type_name: str, ctx: EffectContext, correct: bool):
        """执行卡牌效果 (含Boss战特殊逻辑)"""
        # Boss战特殊规则 override
        if ctx.enemy.is_boss:
            # Boss战：答对10点伤害，答错25点反噬（无视卡牌类型）
            if correct:
                dmg = 10
                if ctx.cs.next_card_x2:
                    dmg *= 2
                    ctx.cs.next_card_x2 = False
                    ctx.st.toast("⚡ 伤害翻倍！", icon="💥")
                ctx.enemy.take_damage(dmg)
                ctx.st.toast(f"⚔️ 对Boss造成 {dmg} 伤害！", icon="⚔️")
            else:
                penalty = 25
                # 贪婪诅咒翻倍
                if ctx.player.change_hp.__code__.co_varnames:  # 简单检查
                     pass # 贪婪在 change_hp 内部处理
                
                ctx.player.change_hp(-penalty)
                ctx.st.error(f"💀 回答错误！受到 {penalty} 伤害")
            return
            
        # 常规卡牌效果
        effect = cls.get_effect(card_type_name)
        if not effect:
            return
        
        if correct and effect.on_correct:
            effect.on_correct(ctx)
        elif not correct and effect.on_wrong:
            effect.on_wrong(ctx)
    
    @classmethod
    def register(cls, card_type_name: str, effect: CardEffect):
        """动态注册新效果"""
        cls.EFFECTS[card_type_name] = effect
