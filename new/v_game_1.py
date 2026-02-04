import streamlit as st
import time
import random
import json
from datetime import datetime

# ==========================================
# ⚙️ CONFIG & MOCK DATA (测试模式)
# ==========================================


class MockGenerator:
    """用于测试游戏循环的假数据生成器"""
    @staticmethod
    def generate_level_data(topic):
        # 模拟生成的单词
        words = [
            {"word": "Ephemeral", "meaning": "短暂的", "options": ["持久的", "短暂的", "巨大的", "快乐的"]},
            {"word": "Serendipity", "meaning": "意外发现珍宝的运气", "options": ["厄运", "意外发现珍宝的运气", "努力", "悲伤"]},
            {"word": "Oblivion", "meaning": "遗忘; 湮没", "options": ["记忆", "遗忘; 湮没", "名声", "起源"]},
            {"word": "Resilience", "meaning": "韧性; 恢复力", "options": ["脆弱", "韧性; 恢复力", "懒惰", "攻击性"]}
        ]
        # 模拟生成的文章 (Boss)
        article = """
        In the <span class='highlight'>ephemeral</span> dance of digital existence, we often stumble upon moments of <span class='highlight'>serendipity</span>. 
        However, the fear of <span class='highlight'>oblivion</span> drives us to document every second. 
        True psychological <span class='highlight'>resilience</span> is required to navigate this era of information overload.
        """
        # 模拟生成的题目 (Boss Skills)
        quizzes = [
            {
                "question": "What is the main theme of the short passage?",
                "options": ["Digital anxiety", "Cooking skills", "History of war", "Space travel"],
                "answer": "Digital anxiety",
                "damage": 20
            },
            {
                "question": "The word 'ephemeral' implies that digital existence is...",
                "options": ["Lasting forever", "Short-lived", "Very heavy", "Expensive"],
                "answer": "Short-lived",
                "damage": 25
            }
        ]
        return words, article, quizzes

# ==========================================
# 🛠️ GAME ENGINE (状态机核心)
# ==========================================
class GameEngine:
    def __init__(self):
        # 初始化游戏状态
        if 'phase' not in st.session_state:
            st.session_state.phase = 'LOBBY' # 状态: LOBBY, TRAINING, SHOP, BOSS, VICTORY, GAMEOVER
        
        if 'player' not in st.session_state:
            st.session_state.player = {
                'hp': 100, 'max_hp': 100,
                'gold': 0,
                'xp': 0,
                'inventory': []
            }
        
        if 'level_data' not in st.session_state:
            st.session_state.level_data = {
                'words': [],     # 小怪
                'article': "",   # 地图背景
                'quizzes': [],   # Boss 技能
                'boss_hp': 100,
                'boss_max_hp': 100
            }

        # 训练营进度
        if 'training_idx' not in st.session_state:
            st.session_state.training_idx = 0

    def switch_phase(self, new_phase):
        st.session_state.phase = new_phase
        st.rerun()

    def add_gold(self, amount):
        st.session_state.player['gold'] += amount
        st.toast(f"💰 金币 +{amount}")

    def take_damage(self, amount, source="Enemy"):
        st.session_state.player['hp'] -= amount
        st.toast(f"💔 受到 {amount} 点伤害 ({source})")
        if st.session_state.player['hp'] <= 0:
            self.switch_phase('GAMEOVER')

    def heal(self, amount):
        p = st.session_state.player
        p['hp'] = min(p['max_hp'], p['hp'] + amount)
        st.toast(f"💚 恢复 {amount} 点 HP")

# ==========================================
# 🧠 SERVICE 2: CyberMind (AI 智能体)
# ==========================================
class CyberMind:
    def __init__(self):
        # 优化：Client 只初始化一次
        self.client = OpenAI(api_key=KIMI_API_KEY, base_url=BASE_URL)

    def _call(self, system, user, retries=3):
        for attempt in range(retries):
            try:
                response = self.client.chat.completions.create(
                    model=MODEL_ID,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user}
                    ],
                    temperature=1, 
                    response_format={"type": "json_object"}
                )
                content = response.choices[0].message.content
                
                # 🛠️ 清洗步骤：使用正则提取 Markdown 代码块中的 JSON
                if "```" in content:
                    # 匹配 ```json {...} ``` 或 ``` {...} ```
                    match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
                    if match:
                        content = match.group(1)
                
                # 去除首尾空白字符
                content = content.strip()

                # 尝试解析
                return json.loads(content)
                
            except json.JSONDecodeError as e:
                print(f"⚠️ [Attempt {attempt+1}/{retries}] JSON 解析失败: {e}")
                print(f"📄 原始内容片段: {content[:100]}...") # 只看前100个字符用于诊断
                
                if attempt == retries - 1:
                    st.error("AI 生成的数据格式异常，请重试或检查 Input Stream 内容。")
                    return {} # 返回空字典防止后续代码崩溃
                continue
                
            except Exception as e:
                st.error(f"API 网络或未知错误: {e}")
                return {}

    def generate_article(self, words):
        prompt = """
        ## 角色设定
        你是一位《经济学人》(The Economist) 或《纽约时报》的资深专栏作家。你的文风专业、逻辑严密，擅长将离散的概念串联成有深度的社会、科技或文化评论。

        ## 任务目标
        请基于用户提供的【单词列表】，撰写一篇 CET-6 (中国大学英语六级) 难度的短文。

        ## 严格要求
        1. **主题与逻辑**：严禁生硬堆砌单词。文章必须有一个明确的核心主题（如数字时代的焦虑、环保悖论、职场心理等），所有单词必须自然地服务于上下文。
        2. **语言标准**：
           - **难度**：CET-6/考研英语级别。
           - **句式**：必须包含至少 2 种复杂句型（如：倒装句、虚拟语气、独立主格、定语从句），避免通篇简单句。
           - **篇幅**：150 - 220 词。
        3. **格式高亮（关键）**：
           - 必须且只能将【单词列表】中的词（包含其时态/复数变形）用 `<span class='highlight-word'>...</span>` 包裹。
           - 例如：如果输入 "apply"，文中用了 "applied"，请输出 `<span class='highlight-word'>applied</span>`。
        4. **翻译要求**：
           - 提供意译而非直译。译文应流畅优美，符合中文表达习惯（信达雅）。

        ## 输出格式
        请仅返回纯 JSON 格式，不要使用 Markdown 代码块包裹：
        {
            "article_english": "Your English article content here...",
            "article_chinese": "你的中文翻译内容..."
        }
        """
        return self._call(prompt, f"单词列表: {words}")

    def analyze_words(self, words):
        # 修改建议
        prompt = """
        你是一个英语教学专家。分析单词。
        要求：
        1. "is_core" 字段逻辑：如果是 CET-6 (六级) 或 考研英语 的高频词汇，设为 true，否则为 false。
        2. 返回 JSON:
        { "words": [ {"word": "...", "meaning": "...", "root": "...", "imagery": "...", "is_core": true/false} ] }
        """
        return self._call(prompt, f"单词列表: {words}")

    def generate_quiz(self, words, article_context=None):
        # 优化：上下文联动
        # 如果有文章上下文，AI 将基于文章出题
        context_str = f"文章内容:\n{article_context}" if article_context else "无文章上下文（请基于单词构造通用场景）"
        
        prompt = f"""
        ## 角色设定
        你是一位经验丰富的 CET-6 (六级) 和 IELTS (雅思) 命题组专家。你需要根据提供的单词和文章内容，设计高质量的阅读理解或词汇辨析题。

        ## 输入数据
        1. 考察单词: {words}
        2. {context_str}

        ## 出题标准 (Strict Guidelines)
        1. **深度结合语境**：
           - 严禁出简单的“词义匹配”题。
           - 题目必须考察单词在**当前特定文章语境**下的深层含义、隐喻或它对情节发展的推动作用。
           - 正确选项必须是文章中具体信息的推论，而不仅仅是单词的字典定义。

        2. **干扰项设计 (Distractors)**：
           - 错误选项必须具有迷惑性（例如：通过偷换概念、因果倒置、或利用单词的字面意思设置陷阱）。
           - 避免出现一眼就能排除的荒谬选项。

        3. **题目类型**：
           - 请混合设计：词汇推断题 (Vocabulary in Context) 和 细节理解题 (Detail Comprehension)。

        ## 输出格式
        请返回纯 JSON 格式，不要使用 Markdown 代码块。
        JSON 结构如下（注意：key 必须严格对应）：
        {{
            "quizzes": [
                {{
                    "question": "题干内容 (英文)...",
                    "options": ["A. 选项内容", "B. 选项内容", "C. 选项内容", "D. 选项内容"],
                    "answer": "A. 选项内容", 
                    "explanation": "中文解析：1. 为什么选这个答案（结合文章引用）；2. 其他选项为什么错（解析干扰点）。"
                }}
            ]
        }}
        """
        return self._call(prompt, f"请为这些单词设计 3-5 道题目: {words}")

# ==========================================
# 🖥️ UI COMPONENTS (界面渲染)
# ==========================================
def render_hud():
    """始终显示的顶部状态栏"""
    p = st.session_state.player
    
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
        with c1:
            st.markdown(f"❤️ **HP: {p['hp']}/{p['max_hp']}**")
            st.progress(p['hp'] / p['max_hp'])
        with c2:
            phase_map = {'LOBBY': '🏠', 'TRAINING': '⚔️', 'SHOP': '🛒', 'BOSS': '👹'}
            current_icon = phase_map.get(st.session_state.phase, '❓')
            st.markdown(f"**当前阶段:** {current_icon} {st.session_state.phase}")
        with c3:
            st.metric("Gold", p['gold'])
        with c4:
            st.metric("XP", p['xp'])

def render_lobby(game):
    st.title("🏰 单词地牢 (The Word Dungeon)")
    st.markdown("欢迎来到认知深渊。你需要通过**学习单词**来赚取金币，购买装备，最后击败**阅读理解 Boss**。")
    
    topic = st.text_input("输入本局主题 (例如: Technology, Biology...)", "Technology")
    
    if st.button("🚀 开启冒险 (Start Run)", type="primary"):
        with st.spinner("正在生成地牢..."):
            ai = CyberMind()
            words_data = ai.analyze_words(topic) # 需适配返回格式
            article_data = ai.generate_article([w['word'] for w in words_data['words']])
            quiz_data = ai.generate_quiz(...)
            
            # 2. 存入 Session
            st.session_state.level_data['words'] = words
            st.session_state.level_data['article'] = article
            st.session_state.level_data['quizzes'] = quizzes
            st.session_state.level_data['boss_hp'] = len(quizzes) * 30 # Boss血量动态设定
            st.session_state.level_data['boss_max_hp'] = len(quizzes) * 30
            
            # 3. 重置进度
            st.session_state.training_idx = 0
            
            # 4. 切换到训练营
            game.switch_phase('TRAINING')

def render_training(game):
    st.header("🌲 迷雾森林 (Training Phase)")
    st.info("任务：击杀（学习）所有单词小怪以赚取金币。答对 +20G，答错 -10HP。")
    
    words = st.session_state.level_data['words']
    idx = st.session_state.training_idx
    
    # 检查是否通关训练营
    if idx >= len(words):
        st.success("🎉 所有小怪已清除！你带着战利品来到了黑市。")
        if st.button("前往商店 ->"):
            game.switch_phase('SHOP')
        return

    word = words[idx]
    
    # === 战斗卡片 ===
    with st.container(border=True):
        c1, c2 = st.columns([1, 2])
        
        with c1:
            st.markdown(f"# 👾")
            st.markdown(f"### {word['word']}")
        
        with c2:
            # 状态控制：是否翻面
            card_key = f"card_flipped_{idx}"
            if card_key not in st.session_state:
                st.session_state[card_key] = False

            if not st.session_state[card_key]:
                st.markdown("⚠️ 遇到野生单词！")
                if st.button("🔍 观察弱点 (学习)", use_container_width=True):
                    st.session_state[card_key] = True
                    st.rerun()
            else:
                st.markdown(f"**释义:** {word['meaning']}")
                st.markdown("---")
                st.write("⚔️ **选择正确的攻击方式 (释义):**")
                
                # 乱序选项
                opts = list(word['options']) # 复制一份防止修改原数据
                # 简单的打乱逻辑可以加在这里
                
                sel = st.radio("Options", opts, key=f"radio_{idx}", label_visibility="collapsed")
                
                col_act1, col_act2 = st.columns(2)
                with col_act1:
                    if st.button("⚔️ 攻击 (提交)", type="primary", use_container_width=True):
                        if sel == word['meaning']:
                            game.add_gold(20)
                            st.session_state.training_idx += 1
                            st.rerun()
                        else:
                            game.take_damage(10, "Word Monster")
                            st.error("攻击被格挡！(答案错误)")

def render_shop(game):
    st.header("🛒 黑市 (The Merchant)")
    st.caption("Boss 战即将来临。你的金币只能在这里使用。")
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown("### 🧪 生命药水")
        st.markdown("**价格: 30G**\n\n恢复 50 点 HP")
        if st.button("购买 🧪"):
            if st.session_state.player['gold'] >= 30:
                st.session_state.player['gold'] -= 30
                game.heal(50)
                st.rerun()
            else:
                st.error("穷鬼！走开！")

    with c2:
        st.markdown("### 🛡️ 逻辑护盾")
        st.markdown("**价格: 50G**\n\nBoss 战第一次伤害免疫")
        if st.button("购买 🛡️"):
            if st.session_state.player['gold'] >= 50:
                st.session_state.player['gold'] -= 50
                st.session_state.player['inventory'].append('SHIELD')
                st.toast("获得物品：逻辑护盾")
                st.rerun()
            else:
                st.error("金币不足")
                
    with c3:
        st.markdown("### 🏹 暴击透镜")
        st.markdown("**价格: 80G**\n\nBoss 战伤害翻倍")
        # 逻辑待实现
        st.button("缺货中", disabled=True)

    st.divider()
    if st.button("👹 进入 Boss 房间 (不可回头)", type="primary", use_container_width=True):
        game.switch_phase('BOSS')

def render_boss(game):
    st.header("👹 最终试炼 (The Syntax Demon)")
    
    ld = st.session_state.level_data
    
    # 胜利判定
    if ld['boss_hp'] <= 0:
        game.switch_phase('VICTORY')
        return

    # 1. 显示文章 (Boss 本体)
    with st.expander("📜 阅读卷轴 (Boss Body)", expanded=True):
        st.markdown(ld['article'], unsafe_allow_html=True)

    # 2. Boss 血条
    boss_pct = max(0, ld['boss_hp'] / ld['boss_max_hp'])
    st.progress(boss_pct, text=f"Boss HP: {ld['boss_hp']}/{ld['boss_max_hp']}")

    # 3. 战斗 (题目)
    # 获取当前未解决的第一个问题
    quizzes = ld['quizzes']
    # 我们可以用一个 set 来记录已解决的问题索引
    if 'solved_quizzes' not in st.session_state:
        st.session_state.solved_quizzes = set()
    
    # 找到第一个没做对的题
    current_q_idx = -1
    for i in range(len(quizzes)):
        if i not in st.session_state.solved_quizzes:
            current_q_idx = i
            break
            
    if current_q_idx == -1:
        # 理论上血量扣完就赢了，这里是双重保险
        game.switch_phase('VICTORY')
        return

    q = quizzes[current_q_idx]
    
    st.markdown(f"### 🔥 Boss 正在蓄力: [技能 {current_q_idx + 1}]")
    with st.container(border=True):
        st.markdown(f"**{q['question']}**")
        
        sel = st.radio("选择防御手段:", q['options'], key=f"boss_q_{current_q_idx}")
        
        if st.button("✨ 释放反击"):
            if sel == q['answer']:
                dmg = 30
                # 检查有没有暴击道具
                # if 'CRIT' in inventory: dmg *= 2
                
                ld['boss_hp'] -= dmg
                st.session_state.solved_quizzes.add(current_q_idx)
                st.toast(f"暴击！Boss 受到 {dmg} 点伤害！")
                st.rerun()
            else:
                # 检查护盾
                player_dmg = q['damage']
                if 'SHIELD' in st.session_state.player['inventory']:
                    st.session_state.player['inventory'].remove('SHIELD')
                    player_dmg = 0
                    st.toast("🛡️ 护盾抵消了所有伤害！")
                else:
                    game.take_damage(player_dmg, "Boss Skill")
                    st.error(f"反击失败！你受到了 {player_dmg} 点逻辑伤害！")

# ==========================================
# 🚀 APP ENTRY POINT
# ==========================================
st.set_page_config(page_title="Cognitive Dungeon", page_icon="🏰")

# 注入 CSS 让界面更像游戏
st.markdown("""
<style>
    .stApp { background-color: #1a1a1a; color: #f0f0f0; }
    div.stButton > button { border-radius: 8px; font-weight: bold; }
    div[data-testid="stMetricValue"] { color: #ffd700; }
</style>
""", unsafe_allow_html=True)

# 实例化引擎
game = GameEngine()

# 渲染 HUD (除了 Lobby 外都显示)
if st.session_state.phase != 'LOBBY':
    render_hud()

# 状态机路由
if st.session_state.phase == 'LOBBY':
    render_lobby(game)
elif st.session_state.phase == 'TRAINING':
    render_training(game)
elif st.session_state.phase == 'SHOP':
    render_shop(game)
elif st.session_state.phase == 'BOSS':
    render_boss(game)
elif st.session_state.phase == 'VICTORY':
    st.balloons()
    st.title("🏆 传说达成！")
    st.markdown("你成功净化了这篇复杂的文章。")
    st.metric("获得总经验", 500)
    if st.button("回到大厅"):
        # 重置游戏
        st.session_state.phase = 'LOBBY'
        st.rerun()
elif st.session_state.phase == 'GAMEOVER':
    st.error("💀 你的意识消散了...")
    st.markdown("请休息片刻，重新整理思绪。")
    if st.button("复活 (重置)"):
        st.session_state.player['hp'] = 100
        st.session_state.player['gold'] = 0
        st.session_state.phase = 'LOBBY'
        st.rerun()