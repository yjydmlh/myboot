"""
任务调度器模块

提供定时任务调度功能
"""

import threading
import time
from datetime import datetime
from typing import Optional, Callable, Any

from loguru import logger

from .config import get_config


class Scheduler:
    """应用任务调度器"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        初始化调度器
        
        Args:
            config_file: 配置文件路径，如果为 None 则使用默认配置
        """
        self._logger = logger.bind(name="scheduler")
        self._running = False
        self._jobs = {}
        self._thread = None
        self._config_file = config_file
        
        # 从配置文件读取调度器配置
        self._enabled = get_config('scheduler.enabled', True)
        self._timezone = get_config('scheduler.timezone', 'UTC')
        self._max_workers = get_config('scheduler.max_workers', 10)
        
        # 设置时区（如果支持）
        self._setup_timezone()
        
        self._logger.debug(f"调度器初始化完成 - enabled: {self._enabled}, timezone: {self._timezone}, max_workers: {self._max_workers}")
    
    def _setup_timezone(self):
        """设置时区"""
        try:
            import pytz
            self._tz = pytz.timezone(self._timezone)
            self._logger.debug(f"时区设置为: {self._timezone}")
        except ImportError:
            self._logger.warning(f"未安装 pytz，无法设置时区，使用系统时区")
            self._tz = None
        except Exception as e:
            self._logger.warning(f"设置时区失败: {e}，使用系统时区")
            self._tz = None
    
    def _get_current_time(self) -> datetime:
        """获取当前时间（考虑时区）"""
        if self._tz:
            try:
                return datetime.now(self._tz)
            except Exception:
                return datetime.now()
        return datetime.now()
    
    def add_cron_job(
        self,
        func: Callable,
        cron: str,
        job_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """添加 Cron 任务"""
        job_id = job_id or f"cron_{func.__name__}"
        
        try:
            job_info = {
                'func': func,
                'cron': cron,
                'type': 'cron',
                'kwargs': kwargs
            }
            
            self._jobs[job_id] = job_info
            self._logger.info(f"已添加 Cron 任务: {job_id} - {cron}")
            
            return job_id
            
        except Exception as e:
            self._logger.error(f"添加 Cron 任务失败: {e}")
            raise
    
    def add_interval_job(
        self,
        func: Callable,
        interval: int,
        job_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """添加间隔任务"""
        job_id = job_id or f"interval_{func.__name__}"
        
        try:
            job_info = {
                'func': func,
                'interval': interval,
                'type': 'interval',
                'kwargs': kwargs
            }
            
            self._jobs[job_id] = job_info
            self._logger.info(f"已添加间隔任务: {job_id} - {interval}秒")
            
            return job_id
            
        except Exception as e:
            self._logger.error(f"添加间隔任务失败: {e}")
            raise
    
    def add_date_job(
        self,
        func: Callable,
        run_date: str,
        job_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """添加一次性任务"""
        job_id = job_id or f"date_{func.__name__}"
        
        try:
            job_info = {
                'func': func,
                'run_date': run_date,
                'type': 'date',
                'kwargs': kwargs
            }
            
            self._jobs[job_id] = job_info
            self._logger.info(f"已添加一次性任务: {job_id} - {run_date}")
            
            return job_id
            
        except Exception as e:
            self._logger.error(f"添加一次性任务失败: {e}")
            raise
    
    def remove_job(self, job_id: str) -> bool:
        """移除任务"""
        try:
            if job_id in self._jobs:
                del self._jobs[job_id]
                self._logger.info(f"已移除任务: {job_id}")
                return True
            return False
        except Exception as e:
            self._logger.error(f"移除任务失败: {e}")
            return False
    
    def get_job(self, job_id: str) -> Optional[Any]:
        """获取任务"""
        return self._jobs.get(job_id)
    
    def list_jobs(self) -> list:
        """列出所有任务"""
        return list(self._jobs.keys())
    
    def start(self) -> None:
        """启动调度器"""
        # 检查是否启用
        if not self._enabled:
            self._logger.info("调度器已禁用，不启动")
            return
        
        if not self._running:
            try:
                self._running = True
                self._thread = threading.Thread(target=self._run_scheduler, daemon=True)
                self._thread.start()
                self._logger.info(f"任务调度器已启动 (时区: {self._timezone}, 最大工作线程: {self._max_workers})")
            except Exception as e:
                self._logger.error(f"启动调度器失败: {e}")
                raise
    
    def stop(self) -> None:
        """停止调度器"""
        if self._running:
            try:
                self._running = False
                if self._thread:
                    self._thread.join(timeout=5)
                self._logger.info("任务调度器已停止")
            except Exception as e:
                self._logger.error(f"停止调度器失败: {e}")
    
    def _run_scheduler(self) -> None:
        """运行调度器"""
        while self._running:
            try:
                current_time = self._get_current_time()
                
                for job_id, job_info in self._jobs.items():
                    if job_info['type'] == 'interval':
                        # 间隔任务实现
                        if not hasattr(job_info['func'], '_last_run'):
                            job_info['func']._last_run = time.time()
                        
                        if time.time() - job_info['func']._last_run >= job_info['interval']:
                            self._execute_job(job_id, job_info)
                    
                    elif job_info['type'] == 'cron':
                        # Cron 任务实现
                        if '_last_run_minute' not in job_info:
                            job_info['_last_run_minute'] = None
                        
                        # 每分钟的第 0 秒检查 cron 表达式
                        current_minute_key = (current_time.year, current_time.month, current_time.day,
                                             current_time.hour, current_time.minute)
                        
                        if current_time.second == 0:
                            # 检查是否已经检查过这一分钟（避免重复检查）
                            if job_info['_last_run_minute'] != current_minute_key:
                                if self._match_cron(job_info['cron'], current_time):
                                    self._execute_job(job_id, job_info)
                                job_info['_last_run_minute'] = current_minute_key
                    
                    elif job_info['type'] == 'date':
                        # 一次性任务实现 - 只执行一次，过期任务不再执行
                        # 如果已经执行过，直接跳过
                        if '_executed' in job_info and job_info['_executed']:
                            continue
                        
                        # 如果已标记为过期，跳过
                        if '_expired' in job_info and job_info['_expired']:
                            continue
                        
                        # 解析运行时间
                        run_date = None
                        try:
                            run_date = datetime.strptime(job_info['run_date'], '%Y-%m-%d %H:%M:%S')
                            # 如果配置了时区，将运行时间转换为时区时间
                            if self._tz:
                                try:
                                    run_date = self._tz.localize(run_date)
                                except (ValueError, AttributeError):
                                    # 如果已经是带时区的，或者转换失败，使用原值
                                    pass
                        except ValueError:
                            try:
                                run_date = datetime.strptime(job_info['run_date'], '%Y-%m-%d %H:%M')
                                if self._tz:
                                    try:
                                        run_date = self._tz.localize(run_date)
                                    except (ValueError, AttributeError):
                                        pass
                            except ValueError:
                                self._logger.error(f"无效的日期格式: {job_info['run_date']}，任务将不再执行")
                                job_info['_executed'] = True  # 标记为已执行，避免重复报错
                                continue
                        
                        # 检查时间是否已过期（如果时间已过且未执行，标记为过期不再执行）
                        if current_time > run_date:
                            # 时间已过期，标记为过期不再执行
                            job_info['_expired'] = True
                            self._logger.warning(f"一次性任务 {job_id} 已过期（运行时间: {run_date}），不再执行")
                            continue
                        
                        # 检查时间是否已到
                        if current_time >= run_date:
                            # 时间已到，执行一次后立即标记为已执行
                            try:
                                self._execute_job(job_id, job_info)
                            except Exception as e:
                                self._logger.error(f"一次性任务 {job_id} 执行失败: {e}")
                            finally:
                                # 无论执行成功与否，都标记为已执行，避免重复执行
                                job_info['_executed'] = True
                                self._logger.debug(f"一次性任务 {job_id} 已标记为执行完成，不再执行")
                
                time.sleep(1)  # 每秒检查一次
                
            except Exception as e:
                self._logger.error(f"调度器运行错误: {e}")
                time.sleep(5)
    
    def _match_cron(self, cron_expr: str, dt: datetime) -> bool:
        """
        检查 cron 表达式是否匹配当前时间
        
        Args:
            cron_expr: Cron 表达式，格式: "秒 分 时 日 月 周"
            dt: 要检查的日期时间
            
        Returns:
            bool: 是否匹配
        """
        try:
            parts = cron_expr.split()
            if len(parts) != 6:
                self._logger.error(f"无效的 Cron 表达式: {cron_expr}，应为 6 个部分（秒 分 时 日 月 周）")
                return False
            
            second, minute, hour, day, month, weekday = parts
            
            # 解析各部分
            def match_field(value: int, field: str) -> bool:
                """检查值是否匹配字段"""
                if field == '*':
                    return True
                if '/' in field:
                    # 处理 */n 格式
                    base, step = field.split('/')
                    step_val = int(step)
                    if base == '*':
                        # */n 表示每 n 个单位执行一次，从 0 开始
                        return value % step_val == 0
                    else:
                        # start/n 格式，表示从 start 开始，每 n 个单位
                        start = int(base)
                        return value >= start and (value - start) % step_val == 0
                if ',' in field:
                    # 处理逗号分隔的值
                    return value in [int(x) for x in field.split(',')]
                if '-' in field:
                    # 处理范围
                    start, end = field.split('-')
                    return int(start) <= value <= int(end)
                return value == int(field)
            
            return (match_field(dt.second, second) and
                    match_field(dt.minute, minute) and
                    match_field(dt.hour, hour) and
                    match_field(dt.day, day) and
                    match_field(dt.month, month) and
                    match_field(dt.weekday(), weekday))
        
        except Exception as e:
            self._logger.error(f"解析 Cron 表达式失败: {cron_expr}, 错误: {e}")
            return False
    
    def _execute_job(self, job_id: str, job_info: dict) -> None:
        """执行任务"""
        try:
            self._logger.debug(f"执行任务: {job_id}")
            job_info['func']()
            # 只为 interval 任务设置 _last_run
            if job_info['type'] == 'interval':
                job_info['func']._last_run = time.time()
            self._logger.debug(f"任务执行完成: {job_id}")
        except Exception as e:
            self._logger.error(f"任务执行失败 {job_id}: {e}", exc_info=True)
    
    def is_running(self) -> bool:
        """检查调度器是否运行中"""
        return self._running
    
    def has_jobs(self) -> bool:
        """检查是否有任务"""
        return len(self._jobs) > 0
    
    def get_job_info(self, job_id: str) -> Optional[dict]:
        """获取任务信息"""
        job_info = self._jobs.get(job_id)
        if job_info:
            info = {
                'job_id': job_id,
                'type': job_info['type'],
                'func_name': job_info['func'].__name__,
            }
            if job_info['type'] == 'cron':
                info['cron'] = job_info['cron']
            elif job_info['type'] == 'interval':
                info['interval'] = job_info['interval']
            elif job_info['type'] == 'date':
                info['run_date'] = job_info['run_date']
                info['executed'] = job_info.get('_executed', False)
                info['expired'] = job_info.get('_expired', False)
            return info
        return None
    
    def list_all_jobs(self) -> list:
        """列出所有任务的详细信息"""
        return [self.get_job_info(job_id) for job_id in self._jobs.keys()]
    
    def pause_job(self, job_id: str) -> bool:
        """暂停任务（暂不支持，返回 False）"""
        # TODO: 实现任务暂停功能
        self._logger.warning(f"暂停任务功能暂未实现: {job_id}")
        return False
    
    def resume_job(self, job_id: str) -> bool:
        """恢复任务（暂不支持，返回 False）"""
        # TODO: 实现任务恢复功能
        self._logger.warning(f"恢复任务功能暂未实现: {job_id}")
        return False
    
    def is_enabled(self) -> bool:
        """检查调度器是否启用"""
        return self._enabled
    
    def get_config(self) -> dict:
        """获取调度器配置"""
        return {
            'enabled': self._enabled,
            'timezone': self._timezone,
            'max_workers': self._max_workers,
            'running': self._running,
            'job_count': len(self._jobs)
        }


# 全局调度器实例
_scheduler: Optional[Scheduler] = None


def get_scheduler() -> Scheduler:
    """获取调度器实例"""
    global _scheduler
    
    if _scheduler is None:
        _scheduler = Scheduler()
    
    return _scheduler