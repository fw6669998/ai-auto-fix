# -*- coding: utf-8 -*-
"""
数据库操作模块 - SQLAlchemy 实现
"""
import hashlib
import os
from datetime import datetime
from typing import List, Optional

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from .model import ErrorLog, CommitLog, Project, Base
import config


class Database:
    """数据库操作类"""

    def __init__(self, db_config: str = None):
        db_config = db_config or config.DATABASE_CONFIG
        self.engine = create_engine(db_config, poolclass=NullPool)
        Base.metadata.create_all(self.engine)
        self._ensure_schema()
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    def _ensure_schema(self):
        """兼容旧SQLite数据库，补齐新增字段。"""
        if not str(self.engine.url).startswith("sqlite"):
            return
        with self.engine.begin() as conn:
            columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(projects)").fetchall()]
            if "worktree_path" not in columns:
                conn.exec_driver_sql("ALTER TABLE projects ADD COLUMN worktree_path VARCHAR")

    def insert_error_log(self, error_content: str, error_message: str = "", project_name: str = "") -> ErrorLog:
        """
        插入错误日志，如果已存在则更新计数
        返回: ErrorLog对象
        """
        error_hash = self._compute_hash(error_content)
        now = datetime.now()

        with self.Session() as session:
            stmt = select(ErrorLog).where(ErrorLog.error_hash == error_hash)
            existing = session.execute(stmt).scalar_one_or_none()

            if existing:
                existing.occur_count += 1
                existing.occur_last = now
                existing.updated_at = now
                session.commit()
                session.refresh(existing)
                return existing
            else:
                log = ErrorLog(
                    error_hash=error_hash,
                    error_content=error_content,
                    error_message=error_message,
                    project_name=project_name,
                    occur_count=1,
                    occur_last=now,
                    created_at=now,
                    updated_at=now,
                )
                session.add(log)
                session.commit()
                session.refresh(log)
                return log

    def get_error_log_by_id(self, error_id: int) -> Optional[ErrorLog]:
        """根据ID获取错误日志"""
        with self.Session() as session:
            stmt = select(ErrorLog).where(ErrorLog.id == error_id)
            return session.execute(stmt).scalar_one_or_none()

    def get_error_log_by_hash(self, error_hash: str) -> Optional[ErrorLog]:
        """根据hash获取错误日志"""
        with self.Session() as session:
            stmt = select(ErrorLog).where(ErrorLog.error_hash == error_hash)
            return session.execute(stmt).scalar_one_or_none()

    def get_pending_errors(self) -> List[ErrorLog]:
        """获取待处理的错误日志（fix_result 为空且处理次数不超过3的记录）"""
        with self.Session() as session:
            stmt = (
                select(ErrorLog)
                .where(ErrorLog.fix_result.is_(None))
                .where(ErrorLog.occur_count <= 3)
                .order_by(ErrorLog.occur_count.desc(), ErrorLog.created_at.asc())
            )
            return list(session.execute(stmt).scalars().all())

    def update_error_fix_result(self, error_id: int, branch_name: str, fix_result: str,
                                fix_details: str):
        """更新错误修复结果"""
        now = datetime.now()
        with self.Session() as session:
            stmt = select(ErrorLog).where(ErrorLog.id == error_id)
            log: ErrorLog = session.execute(stmt).scalar_one_or_none()
            if log:
                log.branch_name = branch_name
                log.fix_result = fix_result
                log.fix_details = fix_details
                log.fix_time = now
                log.fix_count += 1
                log.updated_at = now
                session.commit()

    def update_error_status(self, error_id: int, fix_result: str, context: str = None):
        """手动更新错误状态和上下文"""
        now = datetime.now()
        with self.Session() as session:
            stmt = select(ErrorLog).where(ErrorLog.id == error_id)
            log: ErrorLog = session.execute(stmt).scalar_one_or_none()
            if log:
                log.fix_result = fix_result
                log.context = context
                log.updated_at = now
                session.commit()
                return True
            return False

    def get_all_errors(self, limit: int = 100) -> List[ErrorLog]:
        """获取所有错误日志"""
        with self.Session() as session:
            stmt = select(ErrorLog).order_by(ErrorLog.occur_last.desc()).limit(limit)
            return list(session.execute(stmt).scalars().all())

    def get_fixed_errors(self, limit: int = 100) -> List[ErrorLog]:
        """获取已修复的错误日志（fix_result = 'success'）"""
        with self.Session() as session:
            stmt = (
                select(ErrorLog)
                .where(ErrorLog.fix_result == "success")
                .order_by(ErrorLog.fix_time.desc())
                .limit(limit)
            )
            return list(session.execute(stmt).scalars().all())

    def get_failed_errors(self, limit: int = 100) -> List[ErrorLog]:
        """获取修复失败的错误日志（fix_result IN ('failure', 'skipped')）"""
        with self.Session() as session:
            stmt = (
                select(ErrorLog)
                .where(ErrorLog.fix_result.in_(["failure", "skipped"]))
                .order_by(ErrorLog.fix_time.desc())
                .limit(limit)
            )
            return list(session.execute(stmt).scalars().all())

    # ---------- Commit 相关操作 ----------

    def insert_commit_log(self, project_name: str, commit_id: str, branch: str = "") -> CommitLog:
        """插入commit记录，如果已存在则返回已有记录"""
        with self.Session() as session:
            stmt = select(CommitLog).where(
                CommitLog.project_name == project_name,
                CommitLog.commit_id == commit_id
            )
            existing = session.execute(stmt).scalar_one_or_none()
            if existing:
                return existing

            log = CommitLog(
                project_name=project_name,
                commit_id=commit_id,
                branch=branch,
                check_status="pending",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            session.add(log)
            session.commit()
            session.refresh(log)
            return log

    def get_pending_commits(self) -> List[CommitLog]:
        """获取待检查的commit"""
        with self.Session() as session:
            stmt = (
                select(CommitLog)
                .where(CommitLog.check_result.is_(None))
                .order_by(CommitLog.created_at.asc())
            )
            return list(session.execute(stmt).scalars().all())

    def update_commit_check_result(self, commit_id: int, check_status: str,
                                   check_result: Optional[str] = None,
                                   check_details: Optional[str] = None):
        """更新commit检查结果"""
        now = datetime.now()
        with self.Session() as session:
            stmt = select(CommitLog).where(CommitLog.id == commit_id)
            log: CommitLog = session.execute(stmt).scalar_one_or_none()
            if log:
                log.check_status = check_status
                log.check_result = check_result
                log.check_details = check_details
                log.updated_at = now
                session.commit()

    def update_commit_status(self, commit_id: int, check_result: str, context: str = None):
        """手动更新commit状态和上下文"""
        now = datetime.now()
        with self.Session() as session:
            stmt = select(CommitLog).where(CommitLog.id == commit_id)
            log: CommitLog = session.execute(stmt).scalar_one_or_none()
            if log:
                log.check_result = check_result
                log.context = context
                log.updated_at = now
                session.commit()
                return True
            return False

    def get_error_logs_paginated(self, page: int = 1, per_page: int = 20, status: str = None) -> dict:
        """分页查询错误日志"""
        from sqlalchemy import func
        with self.Session() as session:
            stmt = select(ErrorLog)
            if status == "success":
                stmt = stmt.where(ErrorLog.fix_result == "success")
            elif status == "failure":
                stmt = stmt.where(ErrorLog.fix_result == "failure")
            elif status == "skipped":
                stmt = stmt.where(ErrorLog.fix_result == "skipped")
            elif status == "pending":
                stmt = stmt.where(ErrorLog.fix_result.is_(None))

            # 总数
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = session.execute(count_stmt).scalar()

            # 分页数据
            offset = (page - 1) * per_page
            stmt = stmt.order_by(ErrorLog.occur_last.desc()).offset(offset).limit(per_page)
            items = list(session.execute(stmt).scalars().all())

            return {
                "items": items,
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": (total + per_page - 1) // per_page if total > 0 else 1
            }

    def get_commit_logs_paginated(self, page: int = 1, per_page: int = 20, status: str = None) -> dict:
        """分页查询commit记录"""
        from sqlalchemy import func
        with self.Session() as session:
            stmt = select(CommitLog)
            if status == "success":
                stmt = stmt.where(CommitLog.check_result == "no_issue")
            elif status == "failure":
                stmt = stmt.where(CommitLog.check_result == "has_issue")
            elif status == "skipped":
                stmt = stmt.where(CommitLog.check_result == "skipped")
            elif status == "pending":
                stmt = stmt.where(CommitLog.check_result.is_(None))

            # 总数
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = session.execute(count_stmt).scalar()

            # 分页数据
            offset = (page - 1) * per_page
            stmt = stmt.order_by(CommitLog.created_at.desc()).offset(offset).limit(per_page)
            items = list(session.execute(stmt).scalars().all())

            return {
                "items": items,
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": (total + per_page - 1) // per_page if total > 0 else 1
            }

    def get_commit_log_by_id(self, commit_id: int) -> Optional[CommitLog]:
        """根据ID获取commit记录"""
        with self.Session() as session:
            stmt = select(CommitLog).where(CommitLog.id == commit_id)
            return session.execute(stmt).scalar_one_or_none()

    def get_stats(self) -> dict:
        """获取统计数据"""
        from sqlalchemy import func
        with self.Session() as session:
            # 错误统计
            total_errors = session.execute(select(func.count(ErrorLog.id))).scalar()
            fixed_errors = session.execute(select(func.count(ErrorLog.id)).where(ErrorLog.fix_result == "success")).scalar()
            pending_errors = session.execute(select(func.count(ErrorLog.id)).where(ErrorLog.fix_result.is_(None))).scalar()

            # Commit统计
            total_commits = session.execute(select(func.count(CommitLog.id))).scalar()
            success_commits = session.execute(select(func.count(CommitLog.id)).where(CommitLog.check_result == "no_issue")).scalar()
            failure_commits = session.execute(select(func.count(CommitLog.id)).where(CommitLog.check_result == "has_issue")).scalar()

            # 项目统计
            total_projects = session.execute(select(func.count(Project.id))).scalar()
            active_projects = session.execute(select(func.count(Project.id)).where(Project.status == "active")).scalar()

            return {
                "total_errors": total_errors or 0,
                "fixed_errors": fixed_errors or 0,
                "pending_errors": pending_errors or 0,
                "total_commits": total_commits or 0,
                "success_commits": success_commits or 0,
                "failure_commits": failure_commits or 0,
                "total_projects": total_projects or 0,
                "active_projects": active_projects or 0
            }

    # ---------- Project 相关操作 ----------

    def insert_project(self, project_name: str, project_path: str, main_branch: str = "master",
                       worktree_path: str = None) -> Project:
        """插入项目"""
        with self.Session() as session:
            project = Project(
                project_name=project_name,
                project_path=project_path,
                worktree_path=worktree_path,
                main_branch=main_branch,
                status="pending",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            session.add(project)
            session.commit()
            session.refresh(project)
            return project

    def get_project_by_id(self, project_id: int) -> Optional[Project]:
        """根据ID获取项目"""
        with self.Session() as session:
            stmt = select(Project).where(Project.id == project_id)
            return session.execute(stmt).scalar_one_or_none()

    def get_project_by_name(self, project_name: str) -> Optional[Project]:
        """根据名称获取项目"""
        with self.Session() as session:
            stmt = select(Project).where(Project.project_name == project_name)
            return session.execute(stmt).scalar_one_or_none()

    def get_all_projects(self) -> List[Project]:
        """获取所有项目"""
        with self.Session() as session:
            stmt = select(Project).order_by(Project.created_at.desc())
            return list(session.execute(stmt).scalars().all())

    def update_project_status(self, project_id: int, status: str, status_msg: str = None):
        """更新项目状态"""
        now = datetime.now()
        with self.Session() as session:
            stmt = select(Project).where(Project.id == project_id)
            project: Project = session.execute(stmt).scalar_one_or_none()
            if project:
                project.status = status
                project.status_msg = status_msg
                project.updated_at = now
                session.commit()

    def update_project_worktree_path(self, project_id: int, worktree_path: str):
        """更新项目工作树路径"""
        now = datetime.now()
        with self.Session() as session:
            stmt = select(Project).where(Project.id == project_id)
            project: Project = session.execute(stmt).scalar_one_or_none()
            if project:
                project.worktree_path = worktree_path
                project.updated_at = now
                session.commit()

    def delete_project(self, project_id: int):
        """删除项目"""
        with self.Session() as session:
            stmt = select(Project).where(Project.id == project_id)
            project = session.execute(stmt).scalar_one_or_none()
            if project:
                session.delete(project)
                session.commit()

    @staticmethod
    def _compute_hash(content: str) -> str:
        """计算MD5哈希"""
        return hashlib.md5(content.encode("utf-8")).hexdigest()


# 全局数据库实例
_db_instance = None


def get_database() -> Database:
    """获取数据库单例实例"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
