"""
内存级速率限制器
基于 IP 的登录失败尝试次数限制
"""
import time
from collections import defaultdict
from typing import Dict, Tuple


class RateLimiter:
    """简单的内存速率限制器，使用字典 + TTL 实现"""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 900):
        """
        Args:
            max_attempts: 时间窗口内最大尝试次数
            window_seconds: 时间窗口（秒）
        """
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._store: Dict[str, Tuple[int, float]] = defaultdict(lambda: (0, 0.0))

    def _cleanup_expired(self):
        """清理过期的记录"""
        now = time.time()
        expired_keys = []
        for key, (count, timestamp) in self._store.items():
            if now - timestamp > self._window_seconds:
                expired_keys.append(key)
        for key in expired_keys:
            del self._store[key]

    def check(self, key: str) -> Tuple[bool, int]:
        """
        检查是否超过速率限制

        Args:
            key: 标识符（通常是 IP 地址）

        Returns:
            (是否允许, 剩余尝试次数)
        """
        self._cleanup_expired()
        now = time.time()
        count, timestamp = self._store[key]

        if now - timestamp > self._window_seconds:
            # 时间窗口已过期，重置
            count = 0
            timestamp = now

        if count >= self._max_attempts:
            return False, 0

        return True, self._max_attempts - count

    def increment(self, key: str) -> int:
        """
        增加计数

        Returns:
            剩余尝试次数
        """
        now = time.time()
        count, timestamp = self._store[key]

        if now - timestamp > self._window_seconds:
            count = 0
            timestamp = now

        count += 1
        self._store[key] = (count, timestamp)

        remaining = self._max_attempts - count
        return max(0, remaining)

    def reset(self, key: str):
        """重置某个 key 的计数（登录成功后调用）"""
        if key in self._store:
            del self._store[key]


# 全局速率限制器实例
login_rate_limiter = RateLimiter(
    max_attempts=5,
    window_seconds=15 * 60,  # 15 分钟
)