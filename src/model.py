# -*- coding: utf-8 -*-
"""
数据模型模块
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, Text


class Base(DeclarativeBase):
    """SQLAlchemy 声明性基类"""
    pass


class Project(Base):
    """工程管理数据模型"""
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    project_path: Mapped[str] = mapped_column(String, nullable=False)
    worktree_path: Mapped[Optional[str]] = mapped_column(String, default=None)
    main_branch: Mapped[str] = mapped_column(String, default="master")
    status: Mapped[str] = mapped_column(String, default="pending")  # pending/active/failed
    status_msg: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        """转换为字典"""
        data = {}
        for column in inspect(self.__class__).columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                data[column.name] = value.isoformat() if value else None
            else:
                data[column.name] = value
        return data


class CommitLog(Base):
    """Commit提交记录数据模型"""
    __tablename__ = "commit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_name: Mapped[str] = mapped_column(String, default="")
    commit_id: Mapped[str] = mapped_column(String, nullable=False)
    branch_name: Mapped[str] = mapped_column(String, default="")
    message: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="pending")  # pending/no_issue/has_issue/skipped
    check_details: Mapped[Optional[str]] = mapped_column(Text, default=None)
    context: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        """转换为字典"""
        data = {}
        for column in inspect(self.__class__).columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                data[column.name] = value.isoformat() if value else None
            else:
                data[column.name] = value
        return data


class ErrorLog(Base):
    """错误日志数据模型"""
    __tablename__ = "error_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_name: Mapped[str] = mapped_column(String, default="")
    error_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    error_content: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, default=None)
    occur_count: Mapped[int] = mapped_column(Integer, default=1)
    occur_last: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    branch_name: Mapped[Optional[str]] = mapped_column(String, default=None)
    fix_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending/success/failure/skipped
    fix_details: Mapped[Optional[str]] = mapped_column(Text, default=None)
    fix_time: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    context: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        """转换为字典"""
        data = {}
        for column in inspect(self.__class__).columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                data[column.name] = value.isoformat() if value else None
            else:
                data[column.name] = value
        return data
