# ==========================================
# 🧠 AI 服务层 (Kimi API) - v5.4
# ==========================================
import json
import re
import sys
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

_current_dir = Path(__file__).parent
if str(_current_dir) not in sys.path:
    sys.path.insert(0, str(_current_dir))

import streamlit as st
from openai import OpenAI
from config import KIMI_API_KEY, BASE_URL, MODEL_ID


class CyberMind:
    """
    AI 智能体，负责：
    1. 生成文章 (generate_article)
    2. 生成阅读理解题 (generate_quiz)
    3. 分析单词 (analyze_words)
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=KIMI_API_KEY, base_url=BASE_URL)
        self._last_error = None
    
    def _call(self, system: str, user: str, retries: int = 3) -> dict:
        """调用 Kimi API，自动处理 JSON 解析和错误重试"""
        self._last_error = None
        
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
                
                if "```" in content:
                    match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
                    if match:
                        content = match.group(1)
                
                content = content.strip()
                return json.loads(content)
                
            except json.JSONDecodeError as e:
                self._last_error = f"JSON 解析失败: {e}"
                if attempt == retries - 1:
                    return None
                    
            except Exception as e:
                self._last_error = f"API 错误: {e}"
                if attempt == retries - 1:
                    return None
        
        return None
    
    def get_last_error(self) -> str:
        return self._last_error
    
    def generate_article(self, words: list, target_word_count: int = 200) -> dict:
        """生成包含所有单词的 CET-6 难度文章"""
        if not words:
            return MockGenerator.generate_article([])
        
        if isinstance(words[0], dict):
            word_list = [w.get('word', str(w)) for w in words]
        else:
            word_list = [str(w) for w in words]
        
        min_words = max(120, len(word_list) * 12)
        max_words = max(180, len(word_list) * 18)
        
        prompt = f"""
## 角色
你是《经济学人》(The Economist) 资深专栏作家，擅长将专业词汇自然融入叙事。

## 任务
将以下单词列表融入一篇 **CET-6 阅读理解** 难度的短文。

## ⚠️ 严禁（违反将导致失败）
1. ❌ **禁止词汇堆砌**：
   - 错误示例: "Words like temptation, trajectory, leverage are important."
   - 错误示例: "Learners often encounter A, B, C, D, E."
2. ❌ **禁止使用罗列句式**：
   - 禁止: "such as", "including", "like A, B, C"
   - 禁止: "terms like", "words such as"

## ✅ 必须遵守
1. **每个单词必须出现在不同的句子中**
2. **单词必须是句子的核心成分**（主语/谓语/宾语/表语）
3. **文章必须讲述一个完整的故事或论点**
4. **使用多样句式**：定语从句、被动语态、倒装句
5. **高亮格式**：`<span class='highlight-word'>word</span>`（包括时态变形）

## 📝 优秀示例
单词: ["temptation", "trajectory"]
输出:
> The <span class='highlight-word'>temptation</span> to prioritize short-term gains 
> ultimately disrupted the startup's growth 
> <span class='highlight-word'>trajectory</span>. This mistake served as a critical lesson.

## 篇幅
{min_words} - {max_words} 词

## 输出格式
纯 JSON，不要 Markdown 代码块：
{{
    "article_english": "英文文章（高亮标记单词）",
    "article_chinese": "中文翻译（信达雅，意译）"
}}
"""
        result = self._call(prompt, f"单词列表: {word_list}")
        return result if result else MockGenerator.generate_article(words)
    
    def generate_quiz(self, words: list, article_context: str) -> dict:
        """基于文章生成阅读理解题"""
        if not words:
            return MockGenerator.generate_quiz([])
        
        if isinstance(words[0], dict):
            word_list = [w.get('word', str(w)) for w in words]
        else:
            word_list = [str(w) for w in words]
        
        quiz_count = max(3, min(len(word_list) // 3, 6))
        
        prompt = f"""
## 任务
根据单词和文章，设计 {quiz_count} 道阅读理解题。

## 题目要求
1. **考察重点**：单词在**当前文章语境**下的含义（Contextual Meaning）。
2. **选项设计**（重要）：
   - 必须包含 4 个选项（A/B/C/D）。
   - **所有选项必须是中文**。
   - 正确选项：该单词在文中的含义。
   - 干扰选项：该单词的其他含义，或形近词/意近词的含义。**严禁出现 "Something else", "None of the above" 等凑数选项。**
3. **难度**：中等偏难，干扰项要有迷惑性。

## 输出格式
{{
    "quizzes": [
        {{
            "question": "What is the meaning of 'word' in the context?",
            "options": ["A. 正确含义", "B. 干扰含义1", "C. 干扰含义2", "D. 干扰含义3"],
            "answer": "A. 正确含义",
            "damage": 25,
            "explanation": "解析：在文中..."
        }}
    ]
}}
"""
        result = self._call(prompt, "请设计题目")
        return result if result else MockGenerator.generate_quiz(words)
    
    def analyze_words(self, words: list) -> dict:
        """分析单词，生成释义"""
        prompt = """
你是一个英语教学专家。分析单词并提供：
1. meaning: 中文释义
2. root: 词根词缀分析
3. imagery: 记忆场景联想

返回 JSON:
{ "words": [ {"word": "...", "meaning": "...", "root": "...", "imagery": "..."} ] }
"""
        return self._call(prompt, f"单词列表: {words}")


# ==========================================
# 🔧 Mock 数据生成器 (API 失败时降级使用)
# ==========================================
class MockGenerator:
    """当 API 失败时，提供 Mock 数据"""
    
    @staticmethod
    def generate_article(words: list) -> dict:
        """使用模板生成文章，将单词自然融入叙事"""
        word_list = []
        if words:
            for w in words:
                if isinstance(w, dict):
                    word_list.append(w.get('word', str(w)))
                else:
                    word_list.append(str(w))
        
        if not word_list:
            word_list = ["challenge", "strategy", "innovation", "perspective", "outcome"]
        
        # 确保至少有5个词
        while len(word_list) < 5:
            word_list.append("approach")
        
        w = word_list[:5]
        h = lambda x: f"<span class='highlight-word'>{x}</span>"
        
        return {
            "article_english": f"""
The tech industry faces a profound <span class='highlight-word'>{w[0]}</span> that few executives anticipated. 
When Sarah Chen took over as CEO, her first priority was to {h(w[1])} a complete restructuring of the company's R&D department.

The board, initially skeptical of her unconventional methods, soon witnessed a remarkable transformation. 
Her {h(w[2])} approach not only reduced costs by thirty percent but also fostered a culture of creativity 
that had been absent for years. Critics who had dismissed her {h(w[3])} as naive were forced to reconsider 
their assumptions.

By the end of her first year, the results spoke for themselves: a forty percent increase in productivity 
and a renewed sense of purpose among employees. The {h(w[4])} exceeded all expectations, 
proving that bold leadership, when executed with precision, can reshape even the most entrenched organizations.
""",
            "article_chinese": f"""
科技行业正面临一个鲜有高管预见到的深刻{w[0]}。当陈思雅接任CEO时，她的首要任务是对公司研发部门进行彻底的{w[1]}重组。

董事会最初对她非传统的方法持怀疑态度，但很快便见证了令人瞩目的转变。她{w[2]}的方式不仅将成本降低了三成，
还培育了一种多年来一直缺失的创新文化。那些曾嘲笑她{w[3]}太过天真的批评者不得不重新审视自己的判断。

她上任第一年结束时，结果不言自明：生产力提升了四成，员工们重新找到了工作的意义。这个{w[4]}超出了所有人的预期，
证明了大胆的领导力在精准执行时，能够重塑即便是最根深蒂固的组织。
"""
        }
    
    @staticmethod
    def generate_quiz(words: list) -> dict:
        # 安全获取单词和释义
        word_list = []
        if words:
            for w in words:
                if isinstance(w, dict):
                    word_list.append({
                        "word": w.get('word', 'vocabulary'),
                        "meaning": w.get('meaning', '词汇')
                    })
                else:
                    word_list.append({"word": str(w), "meaning": "词汇"})
        
        if not word_list:
            word_list = [{"word": "vocabulary", "meaning": "词汇"}]
        
        quizzes = []
        # 预定义一组干扰项库 (通用高频词义)
        distractors_pool = [
            "巨大的，宏伟的", "微小的，精致的", "迅速的，敏捷的", "缓慢的，迟钝的",
            "困难的，艰巨的", "容易的，简单的", "积极的，乐观的", "消极的，悲观的",
            "永久的，持久的", "暂时的，短暂的", "准确的，精确的", "模糊的，不清楚的",
            "美丽的，迷人的", "丑陋的，难看的", "重要的，关键的", "琐碎的，不重要的"
        ]
        
        quizzes = []
        for i, w in enumerate(word_list[:min(len(word_list), 5)]): # 最多生成5题
            correct_meaning = w['meaning']
            
            # 构建干扰项
            current_distractors = random.sample(distractors_pool, 3)
            # 确保干扰项和正确答案不重复 (简单检查)
            current_distractors = [d for d in current_distractors if d != correct_meaning]
            while len(current_distractors) < 3:
                current_distractors.append("其他的含义")
                
            options_raw = [correct_meaning] + current_distractors[:3]
            random.shuffle(options_raw)
            
            # 找到正确答案的新索引
            correct_idx = options_raw.index(correct_meaning)
            letters = ['A', 'B', 'C', 'D']
            
            formatted_options = [f"{letters[j]}. {opt}" for j, opt in enumerate(options_raw)]
            answer_str = formatted_options[correct_idx]
            
            quizzes.append({
                "question": f"What is the meaning of '{w['word']}' in the context?",
                "options": formatted_options,
                "answer": answer_str,
                "damage": 20,
                "explanation": f"在文章语境中，{w['word']} 意为 {w['meaning']}。"
            })
        
        return {"quizzes": quizzes if quizzes else [
            {
                "question": "Which word best describes the text?",
                "options": ["A. Learning", "B. Playing", "C. Sleeping", "D. Running"],
                "answer": "A. Learning",
                "damage": 20,
                "explanation": "文章主要讨论学习。"
            }
        ]}


# ==========================================
# 🚀 后台预加载器 (Elite 战斗时预生成 Boss 文章)
# ==========================================
class BossPreloader:
    """
    在 Elite 战斗时，后台预生成 Boss 文章
    使用多线程避免阻塞游戏
    """
    
    _executor = ThreadPoolExecutor(max_workers=1)
    _future = None
    _result = None
    _loading = False
    
    @classmethod
    def start_preload(cls, words: list, ai: CyberMind = None):
        """
        开始后台预加载
        
        Args:
            words: 当前卡组单词列表
            ai: CyberMind 实例
        """
        if cls._loading:
            return  # 已在加载中
        
        cls._loading = True
        cls._result = None
        
        def _generate():
            try:
                _ai = ai or CyberMind()
                # 生成文章
                article = _ai.generate_article(words)
                if not article:
                    article = MockGenerator.generate_article(words)
                
                # 生成题目
                quizzes = _ai.generate_quiz(
                    words, 
                    article.get('article_english', '')
                )
                if not quizzes:
                    quizzes = MockGenerator.generate_quiz(words)
                
                cls._result = {
                    'article': article,
                    'quizzes': quizzes
                }
            except Exception as e:
                cls._result = {
                    'article': MockGenerator.generate_article(words),
                    'quizzes': MockGenerator.generate_quiz(words),
                    'error': str(e)
                }
            finally:
                cls._loading = False
        
        cls._future = cls._executor.submit(_generate)
    
    @classmethod
    def get_result(cls) -> dict:
        """获取预加载结果。如果还在加载，返回 None"""
        if cls._loading:
            return None
        return cls._result
    
    @classmethod
    def is_loading(cls) -> bool:
        return cls._loading
    
    @classmethod
    def wait_result(cls, timeout: float = 30) -> dict:
        """等待预加载完成"""
        if cls._future:
            try:
                cls._future.result(timeout=timeout)
            except:
                pass
        return cls._result
    
    @classmethod
    def reset(cls):
        """重置预加载器"""
        cls._result = None
        cls._loading = False
        cls._future = None
