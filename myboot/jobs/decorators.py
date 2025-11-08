"""
任务装饰器模块

提供类似 Spring Boot 的任务装饰器
"""

import functools
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Union

from .job import ScheduledJob, FunctionJob
from .manager import JobManager


def _is_job_enabled(name: str, enabled: Optional[bool] = None) -> bool:
    """
    检查任务是否启用
    
    Args:
        name: 任务名称
        enabled: 直接指定的启用状态，如果为 None 则默认启用
        
    Returns:
        bool: 任务是否启用
    """
    # 如果直接指定了 enabled，则使用该值
    if enabled is not None:
        return enabled
    
    # 默认启用
    return True


def scheduled(
    trigger: Union[str, Dict[str, Any]],
    name: Optional[str] = None,
    description: Optional[str] = None,
    args: tuple = (),
    kwargs: Dict[str, Any] = None,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    timeout: Optional[float] = None,
    max_instances: int = 1,
    coalesce: bool = True,
    enabled: Optional[bool] = None
) -> Callable:
    """
    定时任务装饰器
    
    Args:
        trigger: 触发器，可以是 cron 表达式或字典
        name: 任务名称
        description: 任务描述
        args: 位置参数
        kwargs: 关键字参数
        max_retries: 最大重试次数
        retry_delay: 重试延迟（秒）
        timeout: 超时时间（秒）
        max_instances: 最大实例数
        coalesce: 是否合并任务
        enabled: 是否启用任务，如果为 None 则默认启用
                 可以通过手动获取配置来传递，例如：
                 from myboot.core.config import get_config
                 enabled = get_config('jobs.heartbeat.enabled', True)
    """
    def decorator(func: Callable) -> Callable:
        # 确定任务名称
        job_name = name or func.__name__
        
        # 检查任务是否启用
        if not _is_job_enabled(job_name, enabled):
            # 任务被禁用，返回原始函数但不注册
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            
            wrapper._job = None
            wrapper._is_scheduled = False
            wrapper._is_disabled = True
            
            return wrapper
        
        # 创建定时任务
        job = ScheduledJob(
            func=func,
            trigger=trigger,
            name=job_name,
            description=description or func.__doc__ or "",
            args=args,
            kwargs=kwargs or {},
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=timeout,
            max_instances=max_instances,
            coalesce=coalesce
        )
        
        # 添加到任务管理器
        JobManager.add_job(job)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # 添加任务属性
        wrapper._job = job
        wrapper._is_scheduled = True
        wrapper._is_disabled = False
        
        return wrapper
    
    return decorator


def cron(
    expression: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    enabled: Optional[bool] = None,
    **kwargs
) -> Callable:
    """
    Cron 表达式装饰器
    
    Args:
        expression: Cron 表达式，如 "0 0 * * *"（每天午夜）
        name: 任务名称
        description: 任务描述
        enabled: 是否启用任务，如果为 None 则默认启用
                 可以通过手动获取配置来传递，例如：
                 from myboot.core.config import get_config
                 enabled = get_config('jobs.heartbeat.enabled', True)
        **kwargs: 其他任务参数
    """
    return scheduled(
        trigger=expression,
        name=name,
        description=description,
        enabled=enabled,
        **kwargs
    )


def interval(
    seconds: int = None,
    minutes: int = None,
    hours: int = None,
    days: int = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    enabled: Optional[bool] = None,
    **kwargs
) -> Callable:
    """
    间隔任务装饰器
    
    Args:
        seconds: 秒数
        minutes: 分钟数
        hours: 小时数
        days: 天数
        name: 任务名称
        description: 任务描述
        enabled: 是否启用任务，如果为 None 则默认启用
                 可以通过手动获取配置来传递，例如：
                 from myboot.core.config import get_config
                 enabled = get_config('jobs.heartbeat.enabled', True)
        **kwargs: 其他任务参数
    """
    trigger = {
        'type': 'interval',
        'seconds': seconds,
        'minutes': minutes,
        'hours': hours,
        'days': days
    }
    
    return scheduled(
        trigger=trigger,
        name=name,
        description=description,
        enabled=enabled,
        **kwargs
    )


def once(
    run_date: Union[str, datetime],
    name: Optional[str] = None,
    description: Optional[str] = None,
    enabled: Optional[bool] = None,
    **kwargs
) -> Callable:
    """
    一次性任务装饰器
    
    Args:
        run_date: 运行时间
        name: 任务名称
        description: 任务描述
        enabled: 是否启用任务，如果为 None 则默认启用
                 可以通过手动获取配置来传递，例如：
                 from myboot.core.config import get_config
                 enabled = get_config('jobs.heartbeat.enabled', True)
        **kwargs: 其他任务参数
    """
    trigger = {
        'type': 'date',
        'run_date': run_date
    }
    
    return scheduled(
        trigger=trigger,
        name=name,
        description=description,
        enabled=enabled,
        **kwargs
    )


def job(
    name: Optional[str] = None,
    description: Optional[str] = None,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    timeout: Optional[float] = None
) -> Callable:
    """
    普通任务装饰器
    
    Args:
        name: 任务名称
        description: 任务描述
        max_retries: 最大重试次数
        retry_delay: 重试延迟（秒）
        timeout: 超时时间（秒）
    """
    def decorator(func: Callable) -> Callable:
        # 创建函数任务
        job = FunctionJob(
            func=func,
            name=name or func.__name__,
            description=description or func.__doc__ or "",
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=timeout
        )
        
        # 添加到任务管理器
        JobManager.add_job(job)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # 添加任务属性
        wrapper._job = job
        wrapper._is_job = True
        
        return wrapper
    
    return decorator


def retry(
    max_retries: int = 3,
    retry_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """
    重试装饰器
    
    Args:
        max_retries: 最大重试次数
        retry_delay: 重试延迟（秒）
        backoff_factor: 退避因子
        exceptions: 需要重试的异常类型
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            delay = retry_delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        raise last_exception
            
            return None
        
        return wrapper
    
    return decorator


def timeout(seconds: float) -> Callable:
    """
    超时装饰器
    
    Args:
        seconds: 超时时间（秒）
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError(f"函数 {func.__name__} 执行超时")
            
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(seconds))
            
            try:
                return func(*args, **kwargs)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        
        return wrapper
    
    return decorator


def async_job(
    name: Optional[str] = None,
    description: Optional[str] = None,
    **kwargs
) -> Callable:
    """
    异步任务装饰器
    
    Args:
        name: 任务名称
        description: 任务描述
        **kwargs: 其他任务参数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        # 添加任务属性
        wrapper._is_async_job = True
        wrapper._job_name = name or func.__name__
        wrapper._job_description = description or func.__doc__ or ""
        
        return wrapper
    
    return decorator


def rate_limit(
    calls: int = 100,
    period: int = 60,
    burst: int = 10
) -> Callable:
    """
    限流装饰器
    
    Args:
        calls: 时间窗口内允许的调用次数
        period: 时间窗口（秒）
        burst: 突发请求数
    """
    def decorator(func: Callable) -> Callable:
        # 简单的令牌桶实现
        tokens = burst
        last_update = time.time()
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal tokens, last_update
            
            now = time.time()
            # 添加令牌
            tokens = min(burst, tokens + (now - last_update) * calls / period)
            last_update = now
            
            if tokens >= 1:
                tokens -= 1
                return func(*args, **kwargs)
            else:
                raise Exception(f"函数 {func.__name__} 调用频率过高")
        
        return wrapper
    
    return decorator


def cache_result(ttl: int = 300) -> Callable:
    """
    结果缓存装饰器
    
    Args:
        ttl: 缓存生存时间（秒）
    """
    def decorator(func: Callable) -> Callable:
        cache = {}
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # 检查缓存
            if cache_key in cache:
                result, timestamp = cache[cache_key]
                if time.time() - timestamp < ttl:
                    return result
            
            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            cache[cache_key] = (result, time.time())
            
            return result
        
        return wrapper
    
    return decorator
