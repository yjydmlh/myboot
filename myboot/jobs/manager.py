"""
任务管理器模块

提供任务的统一管理和调度功能
"""

import threading
from typing import Any, Dict, List, Optional, Union

from loguru import logger

from ..core.scheduler import Scheduler
from .job import Job, ScheduledJob


class JobManager:
    """任务管理器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._jobs: Dict[str, Job] = {}
            self._scheduler = Scheduler()
            self._logger = logger.bind(name="job_manager")
            self._initialized = True
    
    @classmethod
    def add_job(cls, job: Job) -> str:
        """添加任务"""
        instance = cls()
        return instance._add_job(job)
    
    def _add_job(self, job: Job) -> str:
        """添加任务到管理器"""
        job_id = f"{job.name}_{id(job)}"
        self._jobs[job_id] = job
        
        # 如果是定时任务，添加到调度器
        if isinstance(job, ScheduledJob):
            self._scheduler.add_job(
                func=job.execute,
                trigger=job.trigger,
                job_id=job_id,
                name=job.name,
                max_instances=job.max_instances,
                coalesce=job.coalesce
            )
            
            # 更新任务信息
            job.job_id = job_id
        
        self._logger.info(f"已添加任务: {job.name} (ID: {job_id})")
        return job_id
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """获取任务"""
        return self._jobs.get(job_id)
    
    def get_jobs(self) -> List[Job]:
        """获取所有任务"""
        return list(self._jobs.values())
    
    def get_job_by_name(self, name: str) -> Optional[Job]:
        """根据名称获取任务"""
        for job in self._jobs.values():
            if job.name == name:
                return job
        return None
    
    def remove_job(self, job_id: str) -> bool:
        """移除任务"""
        if job_id in self._jobs:
            job = self._jobs[job_id]
            
            # 从调度器中移除
            if isinstance(job, ScheduledJob):
                self._scheduler.remove_job(job_id)
            
            # 从管理器中移除
            del self._jobs[job_id]
            
            self._logger.info(f"已移除任务: {job.name} (ID: {job_id})")
            return True
        
        return False
    
    def execute_job(self, job_id: str, *args, **kwargs) -> Any:
        """执行任务"""
        job = self._jobs.get(job_id)
        if job:
            return job.execute(*args, **kwargs)
        else:
            raise ValueError(f"任务不存在: {job_id}")
    
    def execute_job_by_name(self, name: str, *args, **kwargs) -> Any:
        """根据名称执行任务"""
        job = self.get_job_by_name(name)
        if job:
            return job.execute(*args, **kwargs)
        else:
            raise ValueError(f"任务不存在: {name}")
    
    def start_scheduler(self) -> None:
        """启动调度器"""
        if self._scheduler.has_jobs():
            self._scheduler.start()
            self._logger.info("任务调度器已启动")
    
    def stop_scheduler(self) -> None:
        """停止调度器"""
        if self._scheduler.is_running():
            self._scheduler.stop()
            self._logger.info("任务调度器已停止")
    
    def get_job_status(self, job_id: str) -> Optional[str]:
        """获取任务状态"""
        job = self._jobs.get(job_id)
        return job.status if job else None
    
    def get_job_info(self, job_id: str) -> Optional[Dict[str, Any]]:
        """获取任务信息"""
        job = self._jobs.get(job_id)
        return job.get_info() if job else None
    
    def get_all_job_info(self) -> List[Dict[str, Any]]:
        """获取所有任务信息"""
        return [job.get_info() for job in self._jobs.values()]
    
    def pause_job(self, job_id: str) -> bool:
        """暂停任务"""
        if isinstance(self._jobs.get(job_id), ScheduledJob):
            return self._scheduler.pause_job(job_id)
        return False
    
    def resume_job(self, job_id: str) -> bool:
        """恢复任务"""
        if isinstance(self._jobs.get(job_id), ScheduledJob):
            return self._scheduler.resume_job(job_id)
        return False
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        return {
            "running": self._scheduler.is_running(),
            "has_jobs": self._scheduler.has_jobs(),
            "job_count": len(self._jobs)
        }
    
    def get_job_statistics(self) -> Dict[str, Any]:
        """获取任务统计信息"""
        total_jobs = len(self._jobs)
        scheduled_jobs = sum(1 for job in self._jobs.values() if isinstance(job, ScheduledJob))
        running_jobs = sum(1 for job in self._jobs.values() if job.status == "running")
        completed_jobs = sum(1 for job in self._jobs.values() if job.status == "completed")
        failed_jobs = sum(1 for job in self._jobs.values() if job.status == "failed")
        
        return {
            "total_jobs": total_jobs,
            "scheduled_jobs": scheduled_jobs,
            "running_jobs": running_jobs,
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "success_rate": completed_jobs / total_jobs if total_jobs > 0 else 0
        }
    
    def clear_completed_jobs(self) -> int:
        """清理已完成的任务"""
        completed_job_ids = [
            job_id for job_id, job in self._jobs.items()
            if job.status in ["completed", "failed", "cancelled"]
        ]
        
        for job_id in completed_job_ids:
            self.remove_job(job_id)
        
        self._logger.info(f"已清理 {len(completed_job_ids)} 个已完成的任务")
        return len(completed_job_ids)
    
    def reset_job(self, job_id: str) -> bool:
        """重置任务状态"""
        job = self._jobs.get(job_id)
        if job:
            job.reset()
            self._logger.info(f"已重置任务: {job.name} (ID: {job_id})")
            return True
        return False
    
    def get_job_logs(self, job_id: str, limit: int = 100) -> List[str]:
        """获取任务日志（简化实现）"""
        # 这里可以集成实际的日志系统
        job = self._jobs.get(job_id)
        if job:
            return [f"任务 {job.name} 的日志记录"]
        return []
    
    def export_job_config(self) -> Dict[str, Any]:
        """导出任务配置"""
        config = {
            "jobs": [],
            "scheduler": self.get_scheduler_status()
        }
        
        for job in self._jobs.values():
            job_config = {
                "name": job.name,
                "description": job.description,
                "type": job.__class__.__name__,
                "status": job.status,
                "max_retries": job.max_retries,
                "retry_delay": job.retry_delay,
                "timeout": job.timeout
            }
            
            if isinstance(job, ScheduledJob):
                job_config.update({
                    "trigger": str(job.trigger),
                    "args": job.args,
                    "kwargs": job.kwargs,
                    "max_instances": job.max_instances,
                    "coalesce": job.coalesce
                })
            
            config["jobs"].append(job_config)
        
        return config
    
    def import_job_config(self, config: Dict[str, Any]) -> int:
        """导入任务配置"""
        imported_count = 0
        
        for job_config in config.get("jobs", []):
            try:
                # 这里可以根据配置创建任务
                # 简化实现，实际应用中需要更复杂的逻辑
                self._logger.info(f"导入任务配置: {job_config.get('name', 'unknown')}")
                imported_count += 1
            except Exception as e:
                self._logger.error(f"导入任务配置失败: {e}")
        
        return imported_count
