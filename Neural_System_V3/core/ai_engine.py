import json
from openai import OpenAI
# 引用配置文件 (请确保 config.py 已创建)
from config import KIMI_API_KEY, BASE_URL, MODEL_ID
# 引用提示词仓库 (请确保 utils/prompts.py 已创建)
from utils.prompts import ARTICLE_PROMPT, ANALYSIS_PROMPT, QUIZ_PROMPT_TEMPLATE

class CyberMind:
    def __init__(self):
        # 初始化 OpenAI 客户端
        self.client = OpenAI(api_key=KIMI_API_KEY, base_url=BASE_URL)

    def _call(self, system_prompt, user_content):
        """底层 API 调用方法的通用封装"""
        try:
            response = self.client.chat.completions.create(
                model=MODEL_ID,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=1, 
                response_format={"type": "json_object"}
            )
            # 解析返回的 JSON 字符串
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            # 简单错误处理，实际生产中可以加日志
            print(f"AI Error: {e}")
            raise e

    def generate_article(self, words):
        """生成文章任务"""
        # 直接使用导入的常量提示词
        return self._call(ARTICLE_PROMPT, f"单词列表: {words}")

    def analyze_words(self, words):
        """单词深度解析任务"""
        return self._call(ANALYSIS_PROMPT, f"单词列表: {words}")

    def generate_quiz(self, words, article_context=None):
        """生成题目任务"""
        # 处理上下文逻辑
        context_str = f"文章内容:\n{article_context}" if article_context else "无文章上下文（请基于单词构造通用场景）"
        
        # 使用 format 方法将变量注入到模板中
        # 对应 utils/prompts.py 中的 {words} 和 {context_str}
        formatted_prompt = QUIZ_PROMPT_TEMPLATE.format(
            words=words, 
            context_str=context_str
        )
        
        return self._call(formatted_prompt, f"请为这些单词设计 3-5 道题目: {words}")