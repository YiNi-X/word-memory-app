# ==========================================
# ⚙️ 配置常量
# ==========================================

# Kimi API 配置
KIMI_API_KEY = "sk-tqxUlkDlyX2N2Ka2fJzjv0aDKr5B8hJGVDhFD9N56vGBjlZf"
BASE_URL = "https://api.moonshot.cn/v1"
MODEL_ID = "kimi-k2.5"

# 数据库
DB_NAME = "vocab_spire_v5.db"

# 游戏平衡
TOTAL_FLOORS = 6  # 总层数

# 战斗配置
COMBAT_NEW_WORD_COUNT = (4, 6)      # 普通战斗：4-6 新词
COMBAT_RECALL_WORD_COUNT = (4, 6)   # 回溯战斗：4-6 旧词
ELITE_MIXED_WORD_COUNT = (7, 10)    # 混合精英：7-10 混合
ELITE_STRONG_WORD_COUNT = (7, 10)   # 强力精英：7-10 新词
EVENT_QUIZ_WORD_COUNT = (7, 10)     # 福利事件：7-10 旧词

# 奖励配置
GOLD_COMBAT_NEW = 20
GOLD_COMBAT_RECALL = 15
GOLD_ELITE_MIXED = 40
GOLD_ELITE_STRONG = 50
GOLD_BOSS = 100

# 伤害配置
DAMAGE_NORMAL = 10
DAMAGE_ELITE = 15

# 默认复习词库 (当 deck 表为空时使用)
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
