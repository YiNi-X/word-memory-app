# ==========================================
# 🧠 AI 服务层 (Kimi API)
# ==========================================
import json
import re
import sys
from pathlib import Path

# 添加当前目录到路径
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
        """
        调用 Kimi API，自动处理 JSON 解析和错误重试
        """
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
                
                # 清洗 Markdown 代码块
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
        """
        生成包含所有单词的 CET-6 难度文章
        
        Args:
            words: 单词列表 [{"word": "xxx", "meaning": "xxx"}, ...]
            target_word_count: 目标文章词数，与单词数成正比
        
        Returns:
            {"article_english": "...", "article_chinese": "..."}
        """
        word_list = [w['word'] for w in words]
        
        # 文章长度与单词数成正比
        min_words = max(100, len(words) * 10)
        max_words = max(150, len(words) * 15)
        
        prompt = f"""
## 角色设定
你是一位《经济学人》(The Economist) 或《纽约时报》的资深专栏作家。你的文风专业、逻辑严密，擅长将离散的概念串联成有深度的社会、科技或文化评论。

## 任务目标
请基于用户提供的【单词列表】，撰写一篇 CET-6 (中国大学英语六级) 难度的短文。

## 严格要求
1. **主题与逻辑**：严禁生硬堆砌单词。文章必须有一个明确的核心主题（如数字时代的焦虑、环保悖论、职场心理等），所有单词必须自然地服务于上下文。
2. **语言标准**：
   - **难度**：CET-6/考研英语级别。
   - **句式**：必须包含至少 2 种复杂句型（如：倒装句、虚拟语气、独立主格、定语从句），避免通篇简单句。
   - **篇幅**：{min_words} - {max_words} 词。
3. **格式高亮（关键）**：
   - 必须且只能将【单词列表】中的词（包含其时态/复数变形）用 `<span class='highlight-word'>...</span>` 包裹。
   - 例如：如果输入 "apply"，文中用了 "applied"，请输出 `<span class='highlight-word'>applied</span>`。
4. **翻译要求**：
   - 提供意译而非直译。译文应流畅优美，符合中文表达习惯（信达雅）。

## 输出格式
请仅返回纯 JSON 格式，不要使用 Markdown 代码块包裹：
{{
    "article_english": "Your English article content here...",
    "article_chinese": "你的中文翻译内容..."
}}
"""
        return self._call(prompt, f"单词列表: {word_list}")
    
    def generate_quiz(self, words: list, article_context: str) -> dict:
        """
        基于文章生成阅读理解题
        
        Returns:
            {"quizzes": [{"question": "...", "options": [...], "answer": "...", "explanation": "...", "damage": 25}, ...]}
        """
        word_list = [w['word'] for w in words]
        quiz_count = max(3, min(len(words) // 3, 6))  # 3-6 道题
        
        prompt = f"""
## 角色设定
你是一位经验丰富的 CET-6 (六级) 和 IELTS (雅思) 命题组专家。你需要根据提供的单词和文章内容，设计高质量的阅读理解或词汇辨析题。

## 输入数据
1. 考察单词: {word_list}
2. 文章内容:
{article_context}

## 出题标准 (Strict Guidelines)
1. **深度结合语境**：
   - 严禁出简单的"词义匹配"题。
   - 题目必须考察单词在**当前特定文章语境**下的深层含义、隐喻或它对情节发展的推动作用。
   - 正确选项必须是文章中具体信息的推论，而不仅仅是单词的字典定义。

2. **干扰项设计 (Distractors)**：
   - 错误选项必须具有迷惑性（例如：通过偷换概念、因果倒置、或利用单词的字面意思设置陷阱）。
   - 避免出现一眼就能排除的荒谬选项。

3. **题目类型**：
   - 请混合设计：词汇推断题 (Vocabulary in Context) 和 细节理解题 (Detail Comprehension)。

4. **题目数量**：{quiz_count} 道题

## 输出格式
请返回纯 JSON 格式，不要使用 Markdown 代码块。
JSON 结构如下（注意：key 必须严格对应）：
{{
    "quizzes": [
        {{
            "question": "题干内容 (英文)...",
            "options": ["A. 选项内容", "B. 选项内容", "C. 选项内容", "D. 选项内容"],
            "answer": "A. 选项内容",
            "damage": 25,
            "explanation": "中文解析：1. 为什么选这个答案（结合文章引用）；2. 其他选项为什么错（解析干扰点）。"
        }}
    ]
}}
"""
        return self._call(prompt, "请为这些单词设计题目")
    
    def analyze_words(self, words: list) -> dict:
        """
        分析单词，生成释义、词根、场景联想
        
        Returns:
            {"words": [{"word": "...", "meaning": "...", "root": "...", "imagery": "...", "is_core": true/false}, ...]}
        """
        prompt = """
你是一个英语教学专家。分析单词并提供：
1. meaning: 中文释义
2. root: 词根词缀分析
3. imagery: 记忆场景联想
4. is_core: 是否为 CET-6/考研高频词汇

返回 JSON:
{ "words": [ {"word": "...", "meaning": "...", "root": "...", "imagery": "...", "is_core": true/false} ] }
"""
        return self._call(prompt, f"单词列表: {words}")


# ==========================================
# 🔧 Mock 数据生成器 (API 失败时降级使用)
# ==========================================
class MockGenerator:
    """当 API 失败时，提供 Mock 数据"""
    
    @staticmethod
    def generate_article(words: list) -> dict:
        word_list = [w['word'] for w in words]
        highlighted = " ".join([f"<span class='highlight-word'>{w}</span>" for w in word_list[:5]])
        
        return {
            "article_english": f"""
In the realm of modern vocabulary acquisition, learners often encounter words like {highlighted}. 
These terms, while seemingly complex, carry profound meanings that shape our understanding of the world.
The journey of mastering vocabulary is not merely about memorization, but about comprehending 
the subtle nuances that each word brings to our linguistic arsenal.
""",
            "article_chinese": f"""
在现代词汇习得领域，学习者经常会遇到诸如 {', '.join(word_list[:5])} 等词汇。
这些术语虽然看似复杂，但却承载着深刻的含义，塑造着我们对世界的理解。
掌握词汇的旅程不仅仅是死记硬背，更是要理解每个词给我们语言库带来的微妙内涵。
"""
        }
    
    @staticmethod
    def generate_quiz(words: list) -> dict:
        return {
            "quizzes": [
                {
                    "question": f"What is the primary meaning of '{words[0]['word']}' in the context?",
                    "options": [
                        f"A. {words[0]['meaning']}",
                        "B. Something completely different",
                        "C. A random meaning",
                        "D. None of the above"
                    ],
                    "answer": f"A. {words[0]['meaning']}",
                    "damage": 20,
                    "explanation": f"在文章语境中，{words[0]['word']} 意为 {words[0]['meaning']}。"
                }
            ]
        }
