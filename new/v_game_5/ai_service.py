# ==========================================
# 🧠 AI 服务层 (Kimi API) - v5.4
# ==========================================
import json
import re
import sys
import threading
import logging
import random
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
        api_key = ""
        try:
            api_key = st.secrets.get("KIMI_API_KEY", "")
        except Exception:
            api_key = ""
        if not api_key:
            api_key = KIMI_API_KEY

        self.client = OpenAI(api_key=api_key, base_url=BASE_URL) if api_key else None
        self._last_error = None
    
    def _call(self, system: str, user: str, retries: int = 3) -> dict:
        """调用 Kimi API，自动处理 JSON 解析和错误重试"""
        self._last_error = None

        if not self.client:
            if not st.session_state.get("_warned_missing_kimi", False):
                st.warning("KIMI_API_KEY is missing; using Mock generator.")
                st.session_state._warned_missing_kimi = True
            return None
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

    @staticmethod
    def _extract_word_list(words: list) -> list:
        word_list = []
        seen = set()
        for item in words or []:
            if isinstance(item, dict):
                word = str(item.get("word", "")).strip()
            else:
                word = str(item).strip()
            if not word:
                continue
            key = word.lower()
            if key in seen:
                continue
            seen.add(key)
            word_list.append(word)
        return word_list

    @staticmethod
    def normalize_article_payload(raw: dict, words_list: list) -> dict:
        if not isinstance(raw, dict):
            return None

        title = str(raw.get("title") or "Boss Chronicle").strip()
        content = str(raw.get("content") or raw.get("article_english") or "").strip()
        summary_cn = str(raw.get("summary_cn") or raw.get("article_chinese") or "").strip()
        translation_cn = str(raw.get("translation_cn") or raw.get("article_cn") or "").strip()
        if not content:
            return None

        missing_words = []
        lowered_content = content.lower()
        for word in words_list:
            token = str(word).strip()
            if not token:
                continue
            lower_token = token.lower()
            plain_hit = re.search(rf"\b{re.escape(lower_token)}\b", lowered_content) is not None
            bold_hit = re.search(rf"\*\*{re.escape(lower_token)}\*\*", lowered_content) is not None
            if not plain_hit and not bold_hit:
                missing_words.append(token)

        return {
            "title": title,
            "content": content,
            "summary_cn": summary_cn,
            "translation_cn": translation_cn,
            "all_target_words_used": len(missing_words) == 0,
            "missing_words": missing_words,
        }

    @staticmethod
    def normalize_quiz_payload(raw: dict) -> dict:
        if not isinstance(raw, dict):
            return None

        vocab_attacks = []
        boss_ultimates = []

        if isinstance(raw.get("vocab_attacks"), list):
            vocab_attacks.extend(raw.get("vocab_attacks"))
        if isinstance(raw.get("boss_ultimates"), list):
            boss_ultimates.extend(raw.get("boss_ultimates"))

        legacy_quizzes = raw.get("quizzes")
        if isinstance(legacy_quizzes, list):
            for q in legacy_quizzes:
                if not isinstance(q, dict):
                    continue
                vocab_attacks.append(
                    {
                        "type": "vocab",
                        "question": q.get("question", ""),
                        "options": q.get("options", []),
                        "answer": q.get("answer", ""),
                        "damage_to_boss": q.get("damage", 20),
                    }
                )

        def _clean(items: list, quiz_type: str) -> list:
            cleaned = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                question = str(item.get("question", "")).strip()
                answer = str(item.get("answer", "")).strip()
                options = item.get("options")
                if not question or not answer or not isinstance(options, list) or len(options) < 2:
                    continue
                normalized = {
                    "type": quiz_type,
                    "question": question,
                    "options": [str(opt) for opt in options],
                    "answer": answer,
                }
                if quiz_type == "vocab":
                    normalized["damage_to_boss"] = int(item.get("damage_to_boss", item.get("damage", 20)))
                else:
                    normalized["damage_to_player"] = int(item.get("damage_to_player", item.get("damage", 10)))
                cleaned.append(normalized)
            return cleaned

        vocab_attacks = _clean(vocab_attacks, "vocab")
        boss_ultimates = _clean(boss_ultimates, "reading")
        if not vocab_attacks and not boss_ultimates:
            return None
        return {
            "vocab_attacks": vocab_attacks,
            "boss_ultimates": boss_ultimates,
        }

    def generate_article(self, words: list, target_word_count: int = 200) -> dict:
        """生成 Boss 文章（新协议）"""
        word_list = self._extract_word_list(words)
        if not word_list:
            return MockGenerator.generate_article([])

        prompt = """You are a sci-fi/fantasy novelist and a vocabulary expert.
**Task**: Create a "Boss Level" short story/article based on the provided list of words.

**Input Words**: {words_list}

**Requirements**:
1.  **Context**: Create a coherent, engaging story (Cyberpunk, Medieval, or Lovecraftian theme) that naturally incorporates ALL the input words.
2.  **Length**: 200-300 words.
3.  **Formatting**: You MUST wrap every input word used in the text with double asterisks, e.g., **serendipity**.
4.  **Translation**: Provide a full Chinese translation of the story.
5.  **Summary**: Provide a concise Chinese summary of the story.

**Output Format**:
Strictly return a valid JSON object:
{
    "title": "Title of the story",
    "content": "The full story text with **highlighted** words...",
    "translation_cn": "中文全文译文...",
    "summary_cn": "中文故事大意..."
}"""
        raw = self._call(prompt, json.dumps({"words_list": word_list}, ensure_ascii=False))
        normalized = self.normalize_article_payload(raw, word_list)
        if normalized:
            return normalized
        return MockGenerator.generate_article(word_list)

    def generate_quiz(self, words: list, article_context: str) -> dict:
        """生成 Boss 技能题（新协议）"""
        word_list = self._extract_word_list(words)
        if not word_list:
            return MockGenerator.generate_quiz([])

        prompt = """You are a Game Level Designer designing a Boss Fight for a vocabulary game.
**Context**: The player is fighting a Boss represented by the article below.
**Article**: {article_content}
**Target Words**: {words_list}

**Task**: Generate 2 types of battle questions (Quizzes).

**Type 1: Weak Point Attack (Vocabulary Cloze)**
* Select 5 distinct sentences from the article that contain one of the **Target Words**.
* Replace the target word with "______".
* Goal: Test if the player recognizes the word's usage context.
* These are used for the player to deal damage.

**Type 2: Boss Ultimate Move (Reading Comprehension)**
* Create 3 difficult questions based on the *inference* or *main idea* of the article.
* These answers should NOT be explicitly found in the text but require understanding.
* These are "Boss Ultimate Attacks" that hurt the player if answered wrong.

**Output Format**:
Strictly return a valid JSON object:
{
    "vocab_attacks": [
        {
            "type": "vocab",
            "question": "The sentence with ______ blank.",
            "options": ["Correct Word", "Distractor 1", "Distractor 2", "Distractor 3"],
            "answer": "Correct Word",
            "damage_to_boss": 30
        }
    ],
    "boss_ultimates": [
        {
            "type": "reading",
            "question": "A deep reading comprehension question?",
            "options": ["Correct Inference", "Wrong Inference 1", "Wrong Inference 2", "Wrong Inference 3"],
            "answer": "Correct Inference",
            "damage_to_player": 40
        }
    ]
}"""
        payload = {
            "article_content": article_context or "",
            "words_list": word_list,
        }
        raw = self._call(prompt, json.dumps(payload, ensure_ascii=False))
        normalized = self.normalize_quiz_payload(raw)
        if normalized:
            return normalized
        return MockGenerator.generate_quiz(word_list)
    
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
        """使用模板生成 Boss 文章（新协议）"""
        word_list = CyberMind._extract_word_list(words)
        if not word_list:
            word_list = ["signal", "rift", "guardian", "memory", "oath"]

        selected = word_list[: min(10, len(word_list))]
        fragments = []
        for token in selected:
            fragments.append(
                f"In the final corridor, the crew traced **{token}** through rusted terminals and broken sigils."
            )
        content = (
            "Neon rain poured over the tower while ancient bells rang below the reactor. "
            + " ".join(fragments)
            + " When the gate opened, every fragment aligned into a single command: survive the language storm."
        )
        missing = word_list[len(selected):]
        return {
            "title": "Storm Above the Archive",
            "content": content,
            "summary_cn": "队伍在霓虹与古老符文交错的塔中追索线索，最终必须在语言风暴中击败守关者。",
            "translation_cn": "霓虹雨倾泻在塔楼之上，反应堆下方的古老钟声回荡。"
            " 队员们在锈蚀的终端与破碎的符印间追踪线索，"
            + "当大门开启时，所有碎片汇聚成一道命令：在语言风暴中存活。",
            "all_target_words_used": len(missing) == 0,
            "missing_words": missing,
        }
    
    @staticmethod
    def generate_quiz(words: list) -> dict:
        word_list = CyberMind._extract_word_list(words)
        if not word_list:
            word_list = ["vocabulary", "context", "inference"]

        vocab_attacks = []
        for i in range(5):
            token = word_list[i % len(word_list)]
            options = [token, "horizon", "archive", "entropy"]
            random.shuffle(options)
            vocab_attacks.append(
                {
                    "type": "vocab",
                    "question": f"The sentence with ______ should be completed by which word? ({token})",
                    "options": options,
                    "answer": token,
                    "damage_to_boss": 30,
                }
            )

        boss_ultimates = [
            {
                "type": "reading",
                "question": "What is the central conflict of the story?",
                "options": [
                    "Surviving a language-encoded threat",
                    "Building a marketplace",
                    "Planning a vacation",
                    "Repairing a simple tool",
                ],
                "answer": "Surviving a language-encoded threat",
                "damage_to_player": 40,
            },
            {
                "type": "reading",
                "question": "Why does the narrator keep tracing symbols?",
                "options": [
                    "To unlock the final command",
                    "To decorate the corridor",
                    "To avoid all conflict",
                    "To map a river route",
                ],
                "answer": "To unlock the final command",
                "damage_to_player": 40,
            },
            {
                "type": "reading",
                "question": "What does the story emphasize about the tower?",
                "options": [
                    "It is bound to language and memory",
                    "It is a simple training hall",
                    "It is a safe refuge without conflict",
                    "It is unrelated to the crew",
                ],
                "answer": "It is bound to language and memory",
                "damage_to_player": 40,
            },
        ]

        return {
            "vocab_attacks": vocab_attacks,
            "boss_ultimates": boss_ultimates,
        }


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
                article_content = article.get("content") or article.get("article_english") or ""
                quizzes = _ai.generate_quiz(
                    words, 
                    article_content
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
            except Exception:
                logging.exception("BossPreloader wait_result failed")
        return cls._result
    
    @classmethod
    def reset(cls):
        """重置预加载器"""
        cls._result = None
        cls._loading = False
        cls._future = None
