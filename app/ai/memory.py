# -*- coding: utf-8 -*-
"""
记忆管理模块
"""

from typing import Dict, List
from datetime import datetime

class ConversationMemory:
    """对话记忆管理"""
    
    def __init__(self, max_messages: int = 10):
        self.max_messages = max_messages
        self.conversations: Dict[str, List[Dict]] = {}
