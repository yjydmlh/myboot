# myboot 依赖注入「随机」失败 — 根因分析与规避

## 现象

- 删除 `.myboot_cache_*.json` 后重启，出现 `SymbolService.__init__() missing 1 required positional argument: 'symbol_crypto_repository'`（或 `KlineService` 缺 `kline_view_repository` 等）。
- **有时是这个类报错，有时是别的类**，失败次数较多但不是每次都复现。
- 日志里**没有**「导入模块失败」，且所有服务都打印了「已注册服务到容器」。
- 日志里会出现：**「以下服务无法确定初始化顺序: { ... }」**。

---

## 根因（基于你提供的完整失败日志 + myboot 源码）

### 1. 直接原因：Registry 在注册时覆盖了 `dependents`（myboot 框架 bug）

在 **`myboot/core/di/registry.py`** 的 `register_service()` 中：

```python
self.dependencies[service_name] = set()
self.dependents[service_name] = set()   # ← 问题在这里
# 然后才调用 _analyze_dependencies(service_name, service_class)
```

- **`dependents[service_name]`** 表示「哪些服务依赖了当前服务」，应由**其他服务在注册时**通过 `_analyze_dependencies` 往 `dependents[dep_service_name].add(service_name)` 里填。
- 若 **B 先注册、A 后注册**，且 A 依赖 B，则注册 A 时会执行 `dependents[B].add(A)`，此时 `dependents[B]` 已有 A。
- 但等到 **注册 B 时**，上面代码会执行 **`self.dependents[B] = set()`**，把之前已经记在 `dependents[B]` 里的 A **清空**。
- 结果是：**谁后注册，谁就会把自己作为「被依赖方」时已经收集到的 dependents 清掉**。拓扑排序依赖 `dependents` 来正确减少下游的入度，一旦被清空，这些下游的入度永远减不到 0，就会进入「无法确定初始化顺序」的 remaining 集合。

因此：**注册顺序里只要出现「被依赖的服务」晚于「依赖它的服务」注册，就会破坏 `dependents`，进而导致拓扑序错误。**

### 2. 为什么会出现「以下服务无法确定初始化顺序」

- `get_initialization_order()` 做拓扑排序：从入度为 0 的节点开始，每处理一个节点就根据 **`dependents[该节点]`** 去把「依赖它的服务」的入度减 1。
- 因为上面说的覆盖，**部分服务的 `dependents` 被清空**，这些节点被处理时不会去减下游的入度，导致像 `chan_service`、`kline_service`、`symbol_service` 等永远入度不为 0，无法进入排序结果。
- 代码里对「排不出顺序」的服务做了兜底：**把 remaining 集合直接 append 到 result 末尾**（且 set 迭代顺序不确定），所以：
  - 初始化顺序里会出现 **chan_service 排在 kline_service / kline_view_repository 前面** 的情况；
  - `build_container` 按这个错误顺序构建时，在创建 `chan_service` 的 provider 时会「先创建」`kline_service`，但**再创建 kline_service 时只注入「已经创建好的」依赖**，不会递归先创建 `kline_view_repository`，于是 `KlineService` 的 provider 被以缺参方式创建 → 后续 `get_service` 报错。

### 3. 为什么「有时成功有时失败」

- **有缓存时**：发现列表和注册顺序来自缓存，可能**恰好**是「被依赖者先注册、依赖者后注册」，`dependents` 没被后面覆盖，拓扑序正确，所以能跑。
- **删缓存或缓存失效时**：重新 AST 扫描，`discovered_components['services']` 的顺序由 `rglob` + 文件顺序决定，和上次可能不同，一旦变成「依赖者先于被依赖者」注册，就会触发上述 bug，表现为失败。
- 报错类名不固定，是因为第三步 `get_service` 的遍历顺序和「第一个撞上缺参」的服务有关，所以有时是 `chan_service`（缺 kline_service 的完整依赖），有时是别的。

**结论**：根因是 **myboot 的 `register_service` 里对 `self.dependents[service_name] = set()` 的覆盖**，导致拓扑序错误 + 懒创建不递归 → 构造缺参；「随机」来自发现/注册顺序是否恰好把被依赖者先注册。

---

## 你需要做的排查（与本次根因无关时仍可参考）

- 若日志里出现 **「导入模块失败」**：说明有模块没加载成功，其下 `@service` 未注册，需先修该模块的导入（如循环导入）。
- 若**没有**「导入模块失败」但出现 **「以下服务无法确定初始化顺序」**：就是本文描述的 **dependents 被覆盖** 导致的拓扑序错误，按下面「修复与规避」处理即可。

---

## 修复与规避

### 方案一：本地修补 myboot（推荐，一劳永逸）

在 **`myboot/core/di/registry.py`** 的 `register_service` 中，**不要覆盖已有的 `dependents[service_name]`**，只在该键不存在时初始化：

**原代码：**

```python
self.dependents[service_name] = set()
```

**改为：**

```python
if service_name not in self.dependents:
    self.dependents[service_name] = set()
```

或：

```python
self.dependents.setdefault(service_name, set())
```

这样，其他服务在**先**注册时已经写进的 `dependents[service_name]` 不会被清空，拓扑排序能正确得到初始化顺序。

**修改位置**：`.venv\Lib\site-packages\myboot\core\di\registry.py`，在 `register_service` 方法里，把 `self.dependents[service_name] = set()` 按上面方式改掉即可。若 myboot 以 editable 方式安装或你 fork 了仓库，在源码里改并重新安装/部署。

### 方案二：向 myboot 提 Issue / PR

把根因（`register_service` 覆盖 `dependents` 导致拓扑序错误 + 懒创建不递归）和复现方式（多级依赖 + 删缓存后偶发）整理成 Issue，建议维护者按方案一修复；若有权限可直接提 PR。

### 方案三：仅缓解（不治本）

- **不删缓存**：有缓存时注册顺序固定，可能「恰好」是被依赖者先注册，从而不触发 bug；但一旦删缓存或换环境，顺序可能变，仍会失败。
- **无法在业务侧保证注册顺序**：`discovered_components['services']` 的顺序由 myboot 发现逻辑决定，业务代码无法稳定控制，因此无法通过改项目结构彻底规避。

---

## 小结

- **直接原因**：`registry.register_service()` 里对 `self.dependents[service_name] = set()` 的赋值会清掉「依赖当前服务的其他服务」的记录，导致拓扑排序时部分服务永远入度不为 0，被丢进 remaining 并得到错误的初始化顺序；`build_container` 在错误顺序下懒创建依赖时又不递归，最终以缺参创建 Singleton → `get_service` 报错。
- **「随机」原因**：有无缓存、rglob 顺序等会影响「谁先注册」；当「被依赖者」晚于「依赖者」注册时就会触发 dependents 被覆盖，表现为有时成功有时失败。
- **推荐动作**：在本地 myboot 的 `registry.py` 中按方案一修改一行（不覆盖已有 `dependents[service_name]`），并建议向 myboot 上游提交修复。
