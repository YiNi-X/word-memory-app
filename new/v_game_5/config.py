# ==========================================
# ⚙️ 配置常量 - Word=Card 战斗系统
# ==========================================

# Kimi API 配置
KIMI_API_KEY = "sk-tqxUlkDlyX2N2Ka2fJzjv0aDKr5B8hJGVDhFD9N56vGBjlZf"
BASE_URL = "https://api.moonshot.cn/v1"
MODEL_ID = "kimi-k2.5"

# 数据库
DB_NAME = "vocab_spire_v5.db"

# 游戏平衡
TOTAL_FLOORS = 6  # 总层数
INITIAL_GOLD = 50  # 每局初始金币

# ==========================================
# 🎴 卡牌战斗配置
# ==========================================
HAND_SIZE = 6           # 弹仓容量
MIN_ATTACK_CARDS = 3    # 最少红卡数量

# 卡牌效果
ATTACK_DAMAGE = 25      # 🟥 红卡伤害
ATTACK_BACKFIRE = 15    # 答错反噬伤害
DEFENSE_BLOCK = 10      # 🟦 蓝卡护甲
DEFENSE_HEAL = 5        # 蓝卡回血
UTILITY_DRAW = 2        # 🟨 金卡抽牌
UTILITY_DAMAGE_MULT = 2 # 金卡伤害加成

# 敌人配置
ENEMY_HP_BASE = 100     # 基础血量
ENEMY_HP_ELITE = 150    # 精英血量
ENEMY_HP_BOSS = 300     # Boss 血量
ENEMY_ATTACK = 10       # 敌人攻击
ENEMY_ACTION_TIMER = 3  # 几回合攻击一次

# 奖励配置
GOLD_COMBAT = 30
GOLD_ELITE = 50
GOLD_BOSS = 100

# ==========================================
# 默认复习词库
# ==========================================
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
    {"word": "Lethargic", "meaning": "昏昏欲睡的"},
    {"word": "Meticulous", "meaning": "一丝不苟的"},
    {"word": "Nonchalant", "meaning": "漠不关心的"},
    {"word": "Obsolete", "meaning": "过时的"},
    {"word": "Pragmatic", "meaning": "务实的"},
]
