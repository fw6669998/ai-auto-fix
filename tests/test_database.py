# -*- coding: utf-8 -*-
"""
测试数据库模块
"""
import unittest
import tempfile
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestDatabase(unittest.TestCase):
    """测试数据库操作类"""

    def setUp(self):
        """设置测试环境"""
        from src.database import Database
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        db_config = f"sqlite:///{os.path.abspath(self.temp_db.name)}"
        self.db = Database(db_config)

    def tearDown(self):
        """清理测试环境"""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def test_insert_error_log(self):
        """测试插入错误日志"""
        error_content = "Test error message"
        error_message = "Test error"

        result = self.db.insert_error_log(error_content, error_message)

        self.assertIsNotNone(result)
        self.assertEqual(result.error_content, error_content)
        self.assertEqual(result.error_message, error_message)
        self.assertEqual(result.occur_count, 1)
        self.assertEqual(result.status, "pending")

    def test_insert_error_log_deduplication(self):
        """测试错误日志去重"""
        error_content = "Duplicate error message"

        result1 = self.db.insert_error_log(error_content, "msg1")
        result2 = self.db.insert_error_log(error_content, "msg2")

        # 应该返回同一条记录，但count不同
        self.assertEqual(result1.id, result2.id)
        self.assertEqual(result1.occur_count, 1)
        self.assertEqual(result2.occur_count, 2)

    def test_get_pending_errors(self):
        """测试获取待处理错误"""
        self.db.insert_error_log("Error 1", "msg1")
        self.db.insert_error_log("Error 2", "msg2")
        self.db.insert_error_log("Error 3", "msg3")

        pending = self.db.get_pending_errors()

        self.assertEqual(len(pending), 3)
        for error in pending:
            self.assertEqual(error.status, "pending")

    def test_get_pending_errors_count_limit(self):
        """测试处理次数超过3次时不被获取"""
        error = self.db.insert_error_log("Error over limit", "msg")
        # 手动将 count 设为 4（模拟出现超过 3 次）
        with self.db.Session() as session:
            error.occur_count = 4
            session.add(error)
            session.commit()

        pending = self.db.get_pending_errors()
        self.assertEqual(len(pending), 0)

    def test_update_error_fix_result(self):
        """测试更新修复结果"""
        error = self.db.insert_error_log("Test error", "msg")

        self.db.update_error_fix_result(
            error.id,
            branch_name="ai_fix/test",
            status="success",
            fix_details="Fixed successfully"
        )

        updated = self.db.get_error_log_by_id(error.id)
        self.assertEqual(updated.status, "success")
        self.assertEqual(updated.branch_name, "ai_fix/test")

    def test_get_all_errors(self):
        """测试获取所有错误"""
        self.db.insert_error_log("Error 1", "msg1")
        self.db.insert_error_log("Error 2", "msg2")

        all_errors = self.db.get_all_errors()

        self.assertEqual(len(all_errors), 2)

    def test_get_fixed_errors(self):
        """测试获取已修复错误"""
        error1 = self.db.insert_error_log("Error 1", "msg1")
        error2 = self.db.insert_error_log("Error 2", "msg2")

        self.db.update_error_fix_result(error1.id, "branch", "success", "details")

        fixed = self.db.get_fixed_errors()
        self.assertEqual(len(fixed), 1)
        self.assertEqual(fixed[0].id, error1.id)


if __name__ == '__main__':
    unittest.main()
