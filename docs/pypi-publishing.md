# PyPI 自动发布配置指南

本文档说明如何配置 GitHub Actions 自动发布到 PyPI。

## 工作流说明

项目已配置 GitHub Actions 工作流 (`.github/workflows/publish.yml`)，当创建新的 tag（以 `v` 开头，如 `v1.0.0`）时，会自动构建并发布到 PyPI。

## 配置 Trusted Publishing（推荐方式）

Trusted Publishing 是 PyPI 推荐的安全发布方式，无需使用 API token，通过 OIDC 进行身份验证。

### 步骤 1: 在 PyPI 上配置 Trusted Publisher

1. 登录 [PyPI](https://pypi.org/)
2. 进入您的项目页面
3. 点击左侧菜单的 **"Publishing"** 或 **"Manage"** → **"Publishing"**
4. 在 **"Trusted publishers"** 部分，点击 **"Add"**
5. 填写以下信息：
   - **PyPI project name**: `myboot`（您的项目名称）
   - **Publisher name**: 自定义名称，如 `github-actions`
   - **Workflow filename**: `publish.yml`
   - **Environment name**: 留空（或填写特定环境名称）
   - **GitHub Owner**: 您的 GitHub 用户名或组织名
   - **GitHub Repository**: `myboot`（您的仓库名）
   - **Workflow filename**: `publish.yml`
6. 点击 **"Add"** 保存

### 步骤 2: 验证配置

配置完成后，当您创建新的 tag 时，GitHub Actions 会自动触发发布流程：

```bash
# 创建并推送 tag
git tag v1.0.0
git push origin v1.0.0
```

工作流会自动：

1. 检出代码
2. 安装构建依赖
3. 构建分发包（wheel 和 sdist）
4. 使用 trusted publishing 发布到 PyPI

## 使用 API Token 方式（备选）

如果您不想使用 trusted publishing，也可以使用传统的 API token 方式：

### 步骤 1: 创建 PyPI API Token

1. 登录 [PyPI](https://pypi.org/)
2. 进入 **"Account settings"** → **"API tokens"**
3. 点击 **"Add API token"**
4. 填写：
   - **Token name**: 如 `github-actions-publish`
   - **Scope**: 选择 **"Project: myboot"**（项目范围）或 **"Entire account"**（账户范围）
5. 复制生成的 token（只显示一次，请妥善保存）

### 步骤 2: 在 GitHub 中配置 Secret

1. 进入您的 GitHub 仓库
2. 点击 **"Settings"** → **"Secrets and variables"** → **"Actions"**
3. 点击 **"New repository secret"**
4. 填写：
   - **Name**: `PYPI_API_TOKEN`
   - **Secret**: 粘贴刚才复制的 API token
5. 点击 **"Add secret"**

### 步骤 3: 修改工作流文件

修改 `.github/workflows/publish.yml`，添加 `password` 参数：

```yaml
- name: Publish to PyPI
  uses: pypa/gh-action-pypi-publish@release/v1
  with:
    password: ${{ secrets.PYPI_API_TOKEN }}
    print-hash: true
```

**注意**: 使用 API token 会禁用 trusted publishing，但两种方式不能同时使用。

## Tag 命名规则

工作流配置为匹配以 `v` 开头的 tag：

- ✅ `v1.0.0` - 匹配
- ✅ `v0.1.0` - 匹配
- ✅ `v2.3.4` - 匹配
- ❌ `1.0.0` - 不匹配（缺少 `v` 前缀）
- ❌ `release-1.0.0` - 不匹配

## 发布流程

1. **更新版本号**: 在 `pyproject.toml` 中更新 `version` 字段
2. **提交更改**: 提交并推送代码到仓库
3. **创建 Tag**: 创建并推送以 `v` 开头的 tag
4. **自动发布**: GitHub Actions 会自动触发发布流程

```bash
# 示例流程
# 1. 更新 pyproject.toml 中的版本号
# version = "1.0.0"

# 2. 提交更改
git add pyproject.toml
git commit -m "Bump version to 1.0.0"
git push

# 3. 创建并推送 tag
git tag v1.0.0
git push origin v1.0.0
```

## 验证发布

发布完成后，您可以：

1. 在 [PyPI 项目页面](https://pypi.org/project/myboot/) 查看新版本
2. 使用 pip 安装测试：
   ```bash
   pip install myboot==1.0.0
   ```

## 故障排查

### 问题 1: Trusted Publishing 配置失败

**错误信息**: `403 Client Error: Invalid or non-existent authentication information`

**解决方案**:

- 检查 PyPI 上的 trusted publisher 配置是否正确
- 确认 GitHub 仓库名称、工作流文件名等信息匹配
- 确保工作流文件中的 `permissions` 包含 `id-token: write`

### 问题 2: 版本已存在

**错误信息**: `File already exists`

**解决方案**:

- 检查 PyPI 上是否已存在该版本
- 如果确实需要重新发布，需要先删除 PyPI 上的版本（不推荐）
- 或者使用新的版本号

### 问题 3: 构建失败

**错误信息**: 构建步骤失败

**解决方案**:

- 检查 `pyproject.toml` 配置是否正确
- 确认所有必需的文件都已包含在分发包中
- 查看 GitHub Actions 日志获取详细错误信息

## 参考资源

- [PyPI Trusted Publishers 文档](https://docs.pypi.org/trusted-publishers/)
- [pypa/gh-action-pypi-publish 项目](https://github.com/pypa/gh-action-pypi-publish)
- [PyPI 发布指南](https://packaging.python.org/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/)
