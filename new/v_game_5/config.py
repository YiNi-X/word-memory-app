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
TOTAL_FLOORS = 22  # 总层数 (10小+6精+5事+1Boss = 22)
INITIAL_GOLD = 50  # 每局初始金币

# 强制战斗配置
MANDATORY_NORMAL_COMBATS = 10  # 必须遇到的小怪数量
MANDATORY_ELITE_COMBATS = 6   # 必须遇到的精英数量

# ==========================================
# 🎴 卡牌战斗配置
# ==========================================
HAND_SIZE = 6           # 弹仓容量
MIN_ATTACK_CARDS = 3    # 最少红卡数量
BATTLE_HAND_SIZE = 5    # 每场战斗抽牌数量

# 本局单词池配置
GAME_POOL_RED = 20      # 本局红卡总数
GAME_POOL_BLUE = 6     # 本局蓝卡总数
GAME_POOL_GOLD = 3      # 本局金卡总数

# 初始卡组配置
INITIAL_DECK_RED = 6    # 开局红卡数
INITIAL_DECK_BLUE = 2   # 开局蓝卡数
INITIAL_DECK_GOLD = 1   # 开局金卡数
DECK_LIMIT = 9          # 卡组上限
DECK_MAX_RED = 8        # 红卡上限
DECK_MAX_BLUE = 5       # 蓝卡上限
DECK_MAX_GOLD = 1       # 金卡上限

# 局内升级阈值
IN_GAME_UPGRADE_THRESHOLD = 2  # 答对几次升级

# 卡牌效果
ATTACK_DAMAGE = 25      # 🟥 红卡伤害
ATTACK_BACKFIRE = 10    # 答错反噬伤害
DEFENSE_BLOCK = 10      # 🟦 蓝卡护甲
DEFENSE_DAMAGE = 15     # 🟦 蓝卡伤害（新增）
DEFENSE_HEAL = 5        # 蓝卡回血（升级后效果）
BLACK_DAMAGE = 50       # 🖤 黑卡伤害
BLACK_BACKFIRE = 75     # 🖤 黑卡答错伤害 (从50改为75)
UTILITY_DRAW = 2        # 🟨 金卡抽牌
UTILITY_DAMAGE_MULT = 2 # 金卡伤害加成

# 敌人配置
ENEMY_HP_BASE = 125     # 基础血量（小怪）
ENEMY_HP_ELITE = 150    # 精英血量
ENEMY_HP_BOSS = 200     # Boss 血量
ENEMY_ATTACK = 10       # 敌人攻击
ENEMY_ACTION_TIMER = 2  # 几回合攻击一次（从3改为2）

# 商店购卡价格
SHOP_RED_CARD_BASE_PRICE = 25   # 红卡基础价格（递增 25/50/75...）
SHOP_BLUE_CARD_BASE_PRICE = 50  # 蓝卡基础价格（递增 50/100/150...）
SHOP_GOLD_CARD_PRICE = 100      # 金卡固定价格（每局仅一次）

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
