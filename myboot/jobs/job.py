"""
任务基类模块

提供任务的基础功能和抽象类
"""

import asyncio
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from loguru import logger


class Job(ABC):
    """任务基类"""
    
    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: Optional[float] = None
    ):
        """
        初始化任务
        
        Args:
            name: 任务名称
            description: 任务描述
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
            timeout: 超时时间（秒）
        """
        self.name = name or self.__class__.__name__
        self.description = description or self.__doc__ or ""
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        
        # 任务状态
        self.status = "pending"  # pending, running, completed, failed, cancelled
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.last_run: Optional[datetime] = None
        self.run_count = 0
        self.failure_count = 0
        self.last_error: Optional[Exception] = None
        
        # 日志
        self.logger = logger.bind(name=f"job.{self.name}")
    
    def execute(self, *args, **kwargs) -> Any:
        """
        执行任务的主入口
        
        Args:
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            Any: 任务执行结果
        """
        self.status = "running"
        self.started_at = datetime.now()
        self.run_count += 1
        
        self.logger.info(f"开始执行任务: {self.name}")
        
        try:
            # 检查超时
            if self.timeout:
                result = self._execute_with_timeout(*args, **kwargs)
            else:
                result = self._execute_task(*args, **kwargs)
            
            self.status = "completed"
            self.completed_at = datetime.now()
            self.last_run = self.started_at
            
            duration = (self.completed_at - self.started_at).total_seconds()
            self.logger.info(f"任务执行完成: {self.name}, 耗时: {duration:.2f}秒")
            
            return result
            
        except Exception as e:
            self.status = "failed"
            self.failure_count += 1
            self.last_error = e
            self.completed_at = datetime.now()
            self.last_run = self.started_at
            
            self.logger.error(f"任务执行失败: {self.name}, 错误: {e}", exc_info=True)
            
            # 重试逻辑
            if self.failure_count <= self.max_retries:
                self.logger.info(f"任务将在 {self.retry_delay} 秒后重试: {self.name}")
                time.sleep(self.retry_delay)
                return self.execute(*args, **kwargs)
            else:
                self.logger.error(f"任务重试次数已达上限: {self.name}")
                raise
    
    def _execute_with_timeout(self, *args, **kwargs) -> Any:
        """带超时的任务执行（跨平台实现）"""
        if asyncio.iscoroutinefunction(self.run):
            # 异步任务
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    asyncio.wait_for(self.run(*args, **kwargs), timeout=self.timeout)
                )
            finally:
                loop.close()
        else:
            # 同步任务 - 使用 ThreadPoolExecutor 实现跨平台超时
            from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
            
            def run_task():
                return self.run(*args, **kwargs)
            
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_task)
                try:
                    return future.result(timeout=self.timeout)
                except FutureTimeoutError:
                    # 尝试取消任务（虽然可能无法立即中断）
                    future.cancel()
                    raise TimeoutError(f"任务执行超时: {self.name}")
    
    def _execute_task(self, *args, **kwargs) -> Any:
        """执行任务"""
        if asyncio.iscoroutinefunction(self.run):
            # 异步任务
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.run(*args, **kwargs))
            finally:
                loop.close()
        else:
            # 同步任务
            return self.run(*args, **kwargs)
    
    @abstractmethod
    def run(self, *args, **kwargs) -> Any:
        """
        子类需要实现的具体任务逻辑
        
        Args:
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            Any: 任务执行结果
        """
        pass
    
    def cancel(self) -> None:
        """取消任务"""
        self.status = "cancelled"
        self.completed_at = datetime.now()
        self.logger.info(f"任务已取消: {self.name}")
    
    def reset(self) -> None:
        """重置任务状态"""
        self.status = "pending"
        self.started_at = None
        self.completed_at = None
        self.failure_count = 0
        self.last_error = None
        self.logger.info(f"任务状态已重置: {self.name}")
    
    def get_info(self) -> Dict[str, Any]:
        """获取任务信息"""
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "run_count": self.run_count,
            "failure_count": self.failure_count,
            "last_error": str(self.last_error) if self.last_error else None,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "timeout": self.timeout
        }
    
    def __str__(self) -> str:
        return f"Job(name={self.name}, status={self.status})"
    
    def __repr__(self) -> str:
        return f"Job(name={self.name}, status={self.status}, run_count={self.run_count})"


class ScheduledJob(Job):
    """定时任务类"""
    
    def __init__(
        self,
        func: callable,
        trigger: Union[str, Dict[str, Any]],
        name: Optional[str] = None,
        description: Optional[str] = None,
        args: tuple = (),
        kwargs: Dict[str, Any] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: Optional[float] = None,
        max_instances: int = 1,
        coalesce: bool = True
    ):
        """
        初始化定时任务
        
        Args:
            func: 任务函数
            trigger: 触发器
            name: 任务名称
            description: 任务描述
            args: 位置参数
            kwargs: 关键字参数
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
            timeout: 超时时间（秒）
            max_instances: 最大实例数
            coalesce: 是否合并任务
        """
        super().__init__(name, description, max_retries, retry_delay, timeout)
        
        self.func = func
        self.trigger = trigger
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.max_instances = max_instances
        self.coalesce = coalesce
        
        # 调度相关
        self.job_id: Optional[str] = None
        self.next_run: Optional[datetime] = None
        self.last_success: Optional[datetime] = None
        self.last_failure: Optional[datetime] = None
    
    def run(self, *args, **kwargs) -> Any:
        """执行定时任务"""
        # 合并参数
        merged_args = self.args + args
        merged_kwargs = {**self.kwargs, **kwargs}
        
        # 执行函数
        if asyncio.iscoroutinefunction(self.func):
            # 异步函数
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.func(*merged_args, **merged_kwargs))
            finally:
                loop.close()
        else:
            # 同步函数
            return self.func(*merged_args, **merged_kwargs)
    
    def get_info(self) -> Dict[str, Any]:
        """获取定时任务信息"""
        info = super().get_info()
        info.update({
            "trigger": str(self.trigger),
            "args": self.args,
            "kwargs": self.kwargs,
            "job_id": self.job_id,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_failure": self.last_failure.isoformat() if self.last_failure else None,
            "max_instances": self.max_instances,
            "coalesce": self.coalesce
        })
        return info


class FunctionJob(Job):
    """函数任务类"""
    
    def __init__(
        self,
        func: callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        args: tuple = (),
        kwargs: Dict[str, Any] = None,
        **job_kwargs
    ):
        """
        初始化函数任务
        
        Args:
            func: 任务函数
            name: 任务名称
            description: 任务描述
            args: 位置参数
            kwargs: 关键字参数
            **job_kwargs: 其他任务参数
        """
        super().__init__(name, description, **job_kwargs)
        
        self.func = func
        self.args = args or ()
        self.kwargs = kwargs or {}
    
    def run(self, *args, **kwargs) -> Any:
        """执行函数任务"""
        # 合并参数
        merged_args = self.args + args
        merged_kwargs = {**self.kwargs, **kwargs}
        
        # 执行函数
        if asyncio.iscoroutinefunction(self.func):
            # 异步函数
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.func(*merged_args, **merged_kwargs))
            finally:
                loop.close()
        else:
            # 同步函数
            return self.func(*merged_args, **merged_kwargs)
    
    def get_info(self) -> Dict[str, Any]:
        """获取函数任务信息"""
        info = super().get_info()
        info.update({
            "func": self.func.__name__,
            "args": self.args,
            "kwargs": self.kwargs
        })
        return info
