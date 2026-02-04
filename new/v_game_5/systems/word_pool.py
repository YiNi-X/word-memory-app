# ==========================================
# 📚 单词池管理系统
# ==========================================
"""
WordPool 负责：
1. 管理新词和复习词
2. 按需抽取单词给战斗
3. 追踪本局遇到的所有词 (用于 Boss)
"""

import random
import sys
from pathlib import Path
from typing import List, Dict, Optional

# 添加父目录到路径
_parent = Path(__file__).parent.parent
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))


class WordPool:
    """
    单词池管理器
    
    核心功能：
    - draw_new(): 抽取新词
    - draw_review(): 抽取复习词
    - draw_mixed(): 混合抽取
    - get_all_encountered(): 获取本局所有战斗过的词 (Boss 用)
    """
    
    def __init__(self, new_words: List[Dict], review_words: List[Dict]):
        """
        Args:
            new_words: 用户输入的新词 [{"word": "xxx", "meaning": "xxx"}, ...]
            review_words: 从 deck 获取的复习词
        """
        # 转换为内部格式并标记来源
        self.new_words = [
            {**w, "is_review": False} for w in new_words
        ]
        self.review_words = [
            {**w, "is_review": True} for w in review_words
        ]
        
        # 可用词池 (会被消耗)
        self._available_new = list(self.new_words)
        self._available_review = list(self.review_words)
        
        # 打乱顺序
        random.shuffle(self._available_new)
        random.shuffle(self._available_review)
        
        # 追踪本局遇到的词 (用于 Boss)
        self.encountered: List[Dict] = []
    
    def draw_new(self, count: int) -> List[Dict]:
        """
        抽取新词
        
        Args:
            count: 需要的数量
            
        Returns:
            抽取的单词列表 (可能少于请求数量)
        """
        drawn = []
        for _ in range(count):
            if self._available_new:
                word = self._available_new.pop()
                drawn.append(word)
                self.encountered.append(word)
        return drawn
    
    def draw_review(self, count: int) -> List[Dict]:
        """抽取复习词 (可重复抽取)"""
        if not self.review_words:
            return []
        
        drawn = random.sample(
            self.review_words, 
            min(count, len(self.review_words))
        )
        
        for word in drawn:
            if word not in self.encountered:
                self.encountered.append(word)
        
        return drawn
    
    def draw_mixed(self, count: int, new_ratio: float = 0.6) -> List[Dict]:
        """
        混合抽取新词和复习词
        
        Args:
            count: 总数量
            new_ratio: 新词占比 (默认 60%)
        """
        new_count = int(count * new_ratio)
        review_count = count - new_count
        
        drawn = self.draw_new(new_count) + self.draw_review(review_count)
        random.shuffle(drawn)
        return drawn
    
    def get_all_encountered(self) -> List[Dict]:
        """获取本局所有遇到过的词 (用于 Boss)"""
        return list(self.encountered)
    
    def get_new_word_count(self) -> int:
        """获取剩余新词数量"""
        return len(self._available_new)
    
    def get_total_new_words(self) -> int:
        """获取总新词数量"""
        return len(self.new_words)
    
    def peek_new(self, count: int) -> List[Dict]:
        """预览新词 (不消耗)"""
        return self._available_new[:count]
