# REST API 统一响应格式

MyBoot 框架提供了统一的 REST API 响应格式封装，确保所有 API 返回一致的格式。

## 响应格式结构

### 成功响应

```json
{
  "success": true,
  "code": 200,
  "message": "操作成功",
  "data": {
    // 实际业务数据
  }
}
```

### 错误响应

```json
{
  "success": false,
  "code": 422,
  "message": "参数校验失败",
  "data": {
    "fieldErrors": [
      {
        "field": "username",
        "message": "用户名长度必须在3-20个字符之间"
      }
    ]
  }
}
```

## 使用方法

### 1. 自动格式化（推荐）

默认情况下，框架会自动将所有路由的响应包装为统一格式。你只需要在路由函数中返回业务数据即可：

```python
from myboot.core.decorators import get, post
from myboot.core.application import app

@get('/users')
def get_users():
    """获取用户列表"""
    users = [{"id": 1, "name": "张三"}, {"id": 2, "name": "李四"}]
    return {"users": users}  # 自动包装为统一格式
```

实际返回：

```json
{
  "success": true,
  "code": 200,
  "message": "操作成功",
  "data": {
    "users": [
      { "id": 1, "name": "张三" },
      { "id": 2, "name": "李四" }
    ]
  }
}
```

### 2. 手动使用响应包装器

如果你需要自定义响应消息，可以使用响应包装器：

```python
from myboot.web.response import response

@get('/users/{user_id}')
def get_user(user_id: int):
    """获取单个用户"""
    user = {"id": user_id, "name": "张三"}

    # 使用响应包装器
    return response.success(
        data=user,
        message="查询成功",
        code=200
    )
```

### 3. 便捷方法

响应包装器提供了多个便捷方法：

```python
from myboot.web.response import response

# 创建成功（201）
@post('/users')
def create_user(name: str, email: str):
    user = create_user_service(name, email)
    return response.created(data=user, message="用户创建成功")

# 更新成功
@put('/users/{user_id}')
def update_user(user_id: int, name: str):
    user = update_user_service(user_id, name)
    return response.updated(data=user, message="用户更新成功")

# 删除成功
@delete('/users/{user_id}')
def delete_user(user_id: int):
    delete_user_service(user_id)
    return response.deleted(message="用户删除成功")

# 分页响应
@get('/users')
def get_users(page: int = 1, size: int = 10):
    users, total = get_users_service(page, size)
    return response.pagination(
        data=users,
        total=total,
        page=page,
        size=size,
        message="查询成功"
    )
```

## 配置选项

### 启用/禁用自动格式化

在配置文件中设置：

```yaml
server:
  response_format:
    enabled: true # 是否启用自动格式化
    exclude_paths: # 排除的路径（这些路径不会自动格式化）
      - "/custom/path"
      - "/another/path"
```

或者在代码中（通过配置参数）：

```python
app = Application(
    name="My App"
)
# 配置在 config.yaml 中设置：
# server:
#   response_format:
#     enabled: true
#     exclude_paths:
#       - "/custom/path"
```

### 默认排除的路径

以下路径默认不会被格式化（系统路径和文档路径）：

- `/docs`
- `/openapi.json`
- `/redoc`
- `/health`
- `/health/ready`
- `/health/live`

## 异常响应格式

框架已经统一了异常响应格式，所有异常都会自动返回统一格式：

### 验证错误（422）

```json
{
  "success": false,
  "code": 422,
  "message": "Validation Error",
  "data": {
    "fieldErrors": [
      {
        "field": "username",
        "message": "用户名格式不正确"
      }
    ]
  }
}
```

### HTTP 错误（4xx, 5xx）

```json
{
  "success": false,
  "code": 404,
  "message": "HTTP Error",
  "data": {}
}
```

### 服务器错误（500）

```json
{
  "success": false,
  "code": 500,
  "message": "Internal Server Error",
  "data": {
    "type": "ExceptionClassName"
  }
}
```

## 注意事项

1. **已经是统一格式的响应不会被重复包装**：如果你手动返回统一格式的响应，中间件会检测并直接返回。

2. **非 JSON 响应不会格式化**：只有 `JSONResponse` 类型的响应会被格式化。

3. **排除路径不会被格式化**：配置在排除列表中的路径不会被自动格式化，适用于需要返回原始格式的接口。

4. **中间件执行顺序**：响应格式化中间件是最后添加的，因此会最先执行（FastAPI 中间件是 LIFO）。

## 示例代码

完整示例：

```python
from myboot.core.application import Application
from myboot.core.decorators import get, post, put, delete
from myboot.web.response import response

app = Application(name="My API")

# 自动格式化
@get('/users')
def get_users():
    return {"users": [...]}  # 自动包装

# 手动格式化（自定义消息）
@get('/users/{user_id}')
def get_user(user_id: int):
    user = get_user_by_id(user_id)
    return response.success(data=user, message="查询成功")

# 创建操作
@post('/users')
def create_user(name: str, email: str):
    user = create_user(name, email)
    return response.created(data=user, message="用户创建成功")

# 分页
@get('/posts')
def get_posts(page: int = 1, size: int = 10):
    posts, total = get_posts_paged(page, size)
    return response.pagination(
        data=posts,
        total=total,
        page=page,
        size=size
    )
```
