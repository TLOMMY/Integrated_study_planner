# -*- coding: utf-8 -*-
"""
规则引擎模块
"""

from datetime import datetime

class EnergyAwareScheduler:
    """精力感知调度器"""
    
    def get_energy_level(self, current_time: str = None) -> str:
        """根据时间获取精力等级"""
        if not current_time:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
        
        hour = int(current_time.split(":")[0])
        
        if 9 <= hour <= 11:
            return "high"
        elif 14 <= hour <= 16:
            return "medium"
        elif 19 <= hour <= 21:
            return "medium"
        else:
            return "low"
