# CLAUDE_CN.md

此文件为 Claude Code (claude.ai/code) 在此代码仓库中工作时提供中文指导。

## 项目概述

这是一个使用 Python 和 Playwright 构建的自动化 FRP (NATFRP) 签到机器人。该应用程序可以自动在 www.natfrp.com 上进行每日签到，具备验证码破解能力。

## 架构设计

### 核心组件

- **main.py**: 包含所有自动化逻辑的单文件应用程序
- **计算机视觉模块** (`get_gap_offset`): 使用 OpenCV 通过检测背景图像缺口来破解滑动验证码
- **浏览器自动化**: 使用 Playwright 与 NATFRP 网站交互
- **状态管理**: 使用 `state.json` 保存登录会话以避免重复登录
- **重试机制**: 内置重试逻辑，支持配置最大重试次数

### 关键函数

- `get_gap_offset()`: 验证码破解器，使用图像差异检测 (main.py:7-51)
- `main()`: 主要自动化工作流程 (main.py:251-324)
- `solve_geetest_puzzle()`: 处理极验验证码破解 (main.py:220-235)
- `wait_signed_text_and_shoot()`: 成功检测和截图保存 (main.py:238-248)

## 运行应用程序

### 基本执行
```bash
python main.py
```

### 依赖项
项目需要以下依赖：
- playwright
- opencv-python (cv2)
- pathlib (内置模块)

安装 Playwright 浏览器：
```bash
playwright install chromium
```

## 配置文件

- **account.txt**: 包含 NATFRP 登录用户名（第1行）和密码（第2行）
- **state.json**: 浏览器会话状态，用于保持登录状态
- **.gitignore**: 排除敏感文件和调试图像

## 生成文件

- **bg.png, fullbg.png**: 验证码破解过程中提取的背景图像
- **debug_*.png**: 验证码破解分析的调试图像（当 debug=True 时）
- **checkin.png**: 签到成功时保存的截图

## 配置变量

main.py:53-64 中的关键设置：
- `MAX_RETRY`: 最大重试次数（0表示无限重试）
- `ALREADY_SIGNED_TEXT`: 成功检测文本（"今天已经签到过啦"）
- `SIGNED_ANCESTOR_LEVELS`: 截图捕获深度（3层父级元素）
- `SIGNED_ANCESTOR_SCREENSHOT`: 成功截图文件名

## 验证码破解流程

1. 提取带缺口的背景图像（`bg.png`）
2. 提取完整背景图像（`fullbg.png`）
3. 计算两张图像的绝对差异
4. 应用二值化阈值并查找轮廓
5. 根据最大轮廓选择缺口位置
6. 模拟人类般的鼠标拖拽来破解验证码

## 浏览器配置

- 默认以非无头模式运行（`headless=False`）
- 使用 `slow_mo=200` 实现类人交互时序
- 通过 `state.json` 在运行间保持会话状态

## 使用说明

1. 确保 `account.txt` 文件包含正确的用户名和密码
2. 首次运行会创建 `state.json` 保存登录状态
3. 程序会自动检测是否已签到，避免重复操作
4. 遇到验证码时会自动进行图像识别和破解
5. 签到成功后会保存截图作为凭证