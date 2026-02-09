# ==========================================
# ⚙️ 配置常量 - Word=Card 战斗系统
# ==========================================
import os

# Kimi API 配置
KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")
BASE_URL = "https://api.moonshot.cn/v1"
MODEL_ID = "kimi-k2.5"

# 数据库
DB_NAME = "vocab_spire_v5.db"

# 游戏平衡
TOTAL_FLOORS = 22  # 总层数 (8小+5精+8事+1Boss = 22)
INITIAL_GOLD = 50  # 每局初始金币

# 强制战斗配置
MANDATORY_NORMAL_COMBATS = 8   # 必须遇到的小怪数量
MANDATORY_ELITE_COMBATS = 5    # 必须遇到的精英数量
MAX_NON_COMBAT_STREAK = 2     # 连续非战斗最大允许次数
UTILITY_OFFER_BASE = 0.8      # 非战斗出现基准概率
UTILITY_OFFER_DECAY = 0.3     # 连续非战斗时的概率衰减
UTILITY_OFFER_MIN = 0.2       # 非战斗出现最小概率

# ==========================================
# 🎴 卡牌战斗配置
# ==========================================
HAND_SIZE = 6           # ????
MIN_HAND_AFTER_TURN = 3 # ???????????
MIN_ATTACK_CARDS = 3    # 最少红卡数量
BATTLE_HAND_SIZE = 6    # ????????

# 本局单词池配置
GAME_POOL_RED = 30      #每局游戏红卡总数（小怪+精英+Boss）(??????)
GAME_POOL_BLUE = 10     #每局游戏蓝卡总数（小怪+精英+Boss）(??????)
GAME_POOL_GOLD = 6      #每局游戏金卡总数（小怪+精英+Boss）(??????)

# 初始卡组配置
INITIAL_DECK_RED = 6    # 开局红卡数
INITIAL_DECK_BLUE = 2   # 开局蓝卡数
INITIAL_DECK_GOLD = 1   # 开局金卡数
INITIAL_DECK_SIZE = 9   # 初始抓牌数量 (Tower Prep)

# 局内升级阈值
IN_GAME_UPGRADE_THRESHOLD = 3  # ??????
RED_TO_BLUE_UPGRADE_THRESHOLD = 4
BLUE_TO_GOLD_UPGRADE_THRESHOLD = 3

# 卡牌效果
ATTACK_BACKFIRE = 5     # ????
BLACK_BACKFIRE = 15     # ??????
GOLD_CARD_USES = 1      # gold uses per combat

# 敌人配置
ENEMY_HP_BASE = 50      # enemy base HP
ENEMY_HP_ELITE = 75     # elite base HP
ENEMY_HP_GROWTH = 2     # enemy HP growth per floor
ENEMY_HP_BOSS = 150     # Boss ??
ENEMY_ATTACK = 8        # ????
ENEMY_ACTION_TIMER = 3  # ???????(???)

# UI 停留时间额外延迟
UI_PAUSE_EXTRA = 1.0

# 商店购卡价格
SHOP_RED_CARD_BASE_PRICE = 20   # 红卡基础价格（递增 20/40/60...）
SHOP_BLUE_CARD_BASE_PRICE = 50  # 蓝卡基础价格（递增 50/100/150...）
SHOP_GOLD_CARD_PRICE = 100      # 金卡固定价格（每局仅一次）
SHOP_PRICE_SURCHARGE = 50       # 商店道具/圣遗物加价

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
