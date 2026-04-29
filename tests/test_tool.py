# -*- coding: utf-8 -*-
"""
测试工具方法模块
"""
import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.tool import compute_error_hash


class TestToolUtil(unittest.TestCase):
    """测试工具方法类"""

    def test_compute_error_hash(self):
        """测试MD5哈希计算"""
        content1 = "Test error message"
        content2 = "Test error message"
        content3 = "Different message"

        hash1 = compute_error_hash(content1)
        hash2 = compute_error_hash(content2)
        hash3 = compute_error_hash(content3)

        self.assertEqual(hash1, hash2)
        self.assertNotEqual(hash1, hash3)
        self.assertEqual(len(hash1), 32)


if __name__ == '__main__':
    unittest.main()
