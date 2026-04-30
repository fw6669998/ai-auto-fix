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
from . import config, tool


class Database:
    """数据库操作类"""

    def __init__(self, db_config: str = None):
        db_config = db_config or config.DATABASE_CONFIG
        self.engine = create_engine(db_config, poolclass=NullPool)
        Base.metadata.create_all(self.engine)
        self._ensure_schema()
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    def _ensure_schema(self):
        """兼容旧SQLite数据库，补齐新增字段，迁移commit_logs表结构。"""
        if not str(self.engine.url).startswith("sqlite"):
            return
        with self.engine.begin() as conn:
            columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(projects)").fetchall()]
            if "worktree_path" not in columns:
                conn.exec_driver_sql("ALTER TABLE projects ADD COLUMN worktree_path VARCHAR")

            # 迁移commit_logs: 合并check_status和check_result为status
            commit_columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(commit_logs)").fetchall()]
            if "status" not in commit_columns:
                conn.exec_driver_sql("ALTER TABLE commit_logs ADD COLUMN status VARCHAR DEFAULT 'pending'")
                conn.exec_driver_sql("""
                    UPDATE commit_logs SET status = CASE
                        WHEN check_result = 'no_issue' THEN 'no_issue'
                        WHEN check_result = 'has_issue' THEN 'has_issue'
                        WHEN check_result = 'skipped' THEN 'skipped'
                        ELSE 'pending'
                    END
                """)

    def insert_error_log(self, error_content: str, project_name, error_message: str = "",
                         hash_content: str = "") -> ErrorLog:
        """
        插入错误日志，如果已存在则更新计数
        返回: ErrorLog对象
        """
        if not hash_content:
            hash_content = error_content
        error_hash = self._compute_hash(hash_content)
        now = datetime.now()

        with self.Session() as session:
            stmt = select(ErrorLog).where(ErrorLog.error_hash == error_hash)
            existing = session.execute(stmt).scalar_one_or_none()

            if existing:
                tool.log(f"错误已存在,当前状态: {existing.status}")
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
        """获取待处理的错误日志（status = 'pending' 且处理次数不超过3的记录）"""
        with self.Session() as session:
            stmt = (
                select(ErrorLog)
                .where(ErrorLog.status == "pending")
                .where(ErrorLog.occur_count <= 3)
                .order_by(ErrorLog.occur_count.desc(), ErrorLog.created_at.asc())
            )
            return list(session.execute(stmt).scalars().all())

    def update_error_fix_result(self, error_id: int, branch_name: str, status: str,
                                fix_details: str):
        """更新错误修复结果"""
        now = datetime.now()
        with self.Session() as session:
            stmt = select(ErrorLog).where(ErrorLog.id == error_id)
            log: ErrorLog = session.execute(stmt).scalar_one_or_none()
            if log:
                log.branch_name = branch_name
                log.status = status
                log.fix_details = fix_details
                log.fix_time = now
                log.fix_count += 1
                log.updated_at = now
                session.commit()

    def update_error_status(self, error_id: int, status: str, context: str = None):
        """手动更新错误状态和上下文"""
        now = datetime.now()
        with self.Session() as session:
            stmt = select(ErrorLog).where(ErrorLog.id == error_id)
            log: ErrorLog = session.execute(stmt).scalar_one_or_none()
            if log:
                log.status = status
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
        """获取已修复的错误日志（status = 'success'）"""
        with self.Session() as session:
            stmt = (
                select(ErrorLog)
                .where(ErrorLog.status == "success")
                .order_by(ErrorLog.fix_time.desc())
                .limit(limit)
            )
            return list(session.execute(stmt).scalars().all())

    def get_failed_errors(self, limit: int = 100) -> List[ErrorLog]:
        """获取修复失败的错误日志（status IN ('failure', 'skipped')）"""
        with self.Session() as session:
            stmt = (
                select(ErrorLog)
                .where(ErrorLog.status.in_(["failure", "skipped"]))
                .order_by(ErrorLog.fix_time.desc())
                .limit(limit)
            )
            return list(session.execute(stmt).scalars().all())

    # ---------- Commit 相关操作 ----------

    def insert_commit_log(self, project_name: str, commit_id: str, message: str = "") -> CommitLog:
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
                message=message,
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
                .where(CommitLog.status == "pending")
                .order_by(CommitLog.created_at.asc())
            )
            return list(session.execute(stmt).scalars().all())

    def update_commit_check_result(self, commit_id: int, status: str,
                                   check_details: Optional[str] = None,
                                   branch_name: Optional[str] = None):
        """更新commit检查结果"""
        now = datetime.now()
        with self.Session() as session:
            stmt = select(CommitLog).where(CommitLog.id == commit_id)
            log: CommitLog = session.execute(stmt).scalar_one_or_none()
            if log:
                log.status = status
                log.check_details = check_details
                log.updated_at = now
                log.branch_name = branch_name
                session.commit()

    def update_commit_status(self, commit_id: int, status: str, context: str = None):
        """手动更新commit状态和上下文"""
        now = datetime.now()
        with self.Session() as session:
            stmt = select(CommitLog).where(CommitLog.id == commit_id)
            log: CommitLog = session.execute(stmt).scalar_one_or_none()
            if log:
                log.status = status
                log.context = context
                log.updated_at = now
                session.commit()
                return True
            return False

    def get_error_logs_paginated(self, page: int = 1, per_page: int = 20, status: str = None, project_name: str = None) -> dict:
        """分页查询错误日志"""
        from sqlalchemy import func
        with self.Session() as session:
            stmt = select(ErrorLog)
            if status == "success":
                stmt = stmt.where(ErrorLog.status == "success")
            elif status == "failure":
                stmt = stmt.where(ErrorLog.status == "failure")
            elif status == "skipped":
                stmt = stmt.where(ErrorLog.status == "skipped")
            elif status == "pending":
                stmt = stmt.where(ErrorLog.status == "pending")
            if project_name:
                stmt = stmt.where(ErrorLog.project_name == project_name)

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

    def get_commit_logs_paginated(self, page: int = 1, per_page: int = 20, status: str = None, project_name: str = None) -> dict:
        """分页查询commit记录"""
        from sqlalchemy import func
        with self.Session() as session:
            stmt = select(CommitLog)
            if status and status != "None":
                stmt = stmt.where(CommitLog.status == status)
            if project_name:
                stmt = stmt.where(CommitLog.project_name == project_name)

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

    def get_projects_from_errors(self) -> List[str]:
        """获取错误日志表中所有出现的项目名称"""
        from sqlalchemy import distinct
        with self.Session() as session:
            stmt = select(distinct(ErrorLog.project_name)).where(ErrorLog.project_name.isnot(None))
            return [row[0] for row in session.execute(stmt).all() if row[0]]

    def get_projects_from_commits(self) -> List[str]:
        """获取Commit记录表中所有出现的项目名称"""
        from sqlalchemy import distinct
        with self.Session() as session:
            stmt = select(distinct(CommitLog.project_name)).where(CommitLog.project_name.isnot(None))
            return [row[0] for row in session.execute(stmt).all() if row[0]]

    def get_stats(self) -> dict:
        """获取统计数据"""
        from sqlalchemy import func
        with self.Session() as session:
            # 错误统计
            total_errors = session.execute(select(func.count(ErrorLog.id))).scalar()
            fixed_errors = session.execute(
                select(func.count(ErrorLog.id)).where(ErrorLog.status == "success")).scalar()
            pending_errors = session.execute(
                select(func.count(ErrorLog.id)).where(ErrorLog.status == "pending")).scalar()

            # Commit统计
            total_commits = session.execute(select(func.count(CommitLog.id))).scalar()
            success_commits = session.execute(
                select(func.count(CommitLog.id)).where(CommitLog.status == "no_issue")).scalar()
            failure_commits = session.execute(
                select(func.count(CommitLog.id)).where(CommitLog.status == "has_issue")).scalar()

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

    def delete_error_log(self, error_id: int) -> bool:
        """删除错误日志"""
        with self.Session() as session:
            stmt = select(ErrorLog).where(ErrorLog.id == error_id)
            log = session.execute(stmt).scalar_one_or_none()
            if log:
                session.delete(log)
                session.commit()
                return True
            return False

    def delete_commit_log(self, commit_id: int) -> bool:
        """删除Commit记录"""
        with self.Session() as session:
            stmt = select(CommitLog).where(CommitLog.id == commit_id)
            log = session.execute(stmt).scalar_one_or_none()
            if log:
                session.delete(log)
                session.commit()
                return True
            return False

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
