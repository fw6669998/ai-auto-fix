# -*- coding: utf-8 -*-
"""
测试Flask应用接口
"""
import unittest
import tempfile
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app import app


class TestFlaskAPI(unittest.TestCase):
    """测试Flask HTTP接口"""

    def setUp(self):
        """设置测试环境"""
        from src.database import Database, _db_instance
        from src import config

        # 使用临时数据库
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()

        config.DATABASE_PATH = self.temp_db.name

        # 重置数据库实例
        _db_instance = None

        self.client = app.test_client()
        self.client.testing = True

    def tearDown(self):
        """清理测试环境"""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

        # 重置数据库实例
        from src.database import _db_instance
        _db_instance = None

    def test_receive_error(self):
        """测试接收错误日志"""
        response = self.client.post('/api/push/error', json={
            'error_content': 'Test error message',
            'error_message': 'Test error'
        })

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])

    def test_receive_error_without_content(self):
        """测试缺少error_content字段"""
        response = self.client.post('/api/push/error', json={})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data['success'])

    def test_receive_commit_missing_params(self):
        """测试接收commit信息缺少必填参数"""
        response = self.client.get('/api/push/commit?project=app1')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data['success'])


if __name__ == '__main__':
    unittest.main()
