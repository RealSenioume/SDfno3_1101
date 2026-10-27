[English](README.md) | 简体中文

# lolping

一个 Windows 11 桌面端的"标记轮盘"叠加层，视觉风格参考《英雄联盟》的 ping 轮盘。
按住一个修饰键和鼠标键，朝八个带标签的扇形之一拖动，然后松开。轮盘关闭，一段短促的
爆裂动画确认你的选择，这次标记被追加到本地日志文件。

**lolping 不是游戏内工具。** 它不读写《英雄联盟》的内存，不注入游戏进程、不与游戏进程
通信，不使用 Riot API，也不建立任何网络连接。它只是一个普通的桌面叠加层：在鼠标位置
画一个半透明轮盘，并把用户选中的标记记录到本地 JSONL 文件。

本项目不附带任何第三方美术或音频资源。扇区图标是 `src/lolping/assets.py` 里用
`QPainterPath` 生成的原创矢量图形，音效由 `src/lolping/sounds.py` 实时合成，因此仓库中
不含任何 Riot Games 素材，也没有二进制媒体文件。

- 版本：**0.3.1**
- 平台：**Windows 11**（64 位）
- 运行时：**Python 3.14**、**PyQt5 5.15.11**、**pynput 1.8.2**
- 无其他运行时依赖，运行期间不访问网络

## 功能

- 八扇区径向菜单，通过"按住并拖动"的手势在鼠标位置展开（默认：按住 **Alt + 鼠标左键**）。
- 默认扇区（从 3 点钟方向顺时针）：On My Way、All-In、Assist Me、Need Vision、
  Enemy Missing、Enemy Vision、Retreat、Push。八个扇区都可重命名。
- 每个扇区显示一个矢量图标：每个扇区有默认图标，可在十个图标中选择，也可用自定义 PNG
  替换单个扇区。不使用 Riot Games 美术素材。
- 简短的展开动画（130 ms 内缩放并淡入）。提交时播放分层爆裂动画：两个扩散圆环、五条
  方向性光束、图标弹出以及扇区名称。
- 四个合成音效：展开、悬停咔哒、提交铃音、取消下滑音。声音默认关闭，音量默认 50%。
- 在死区外松开即提交；在 34 px 死区内松开、按 **Esc**、或点击其他鼠标键则取消。
- 触发方式可配置：Ctrl/Alt/Shift/Win 的任意组合，配合左/右/中/X1/X2 鼠标键。
- 半透明、无边框、始终置顶的轮盘，不会从下层窗口抢走焦点。每块显示器一个叠加层，
  显示在光标所在屏幕。
- 设置窗口：轮盘半径、死区、扇区名称、每扇区图标选择、图标大小、是否显示图标、
  动画速度、标记持续时间、声音、音量、悬停咔哒、退出热键、开机启动、主题、恢复默认。
- 系统托盘菜单：Settings（设置）、Ping history log（标记历史）、Open config folder
  （打开配置目录）、Pause/Resume（暂停/恢复）、Quit（退出）。
- 每次提交的标记都会写入本地 JSONL 日志；另有可选的延迟测量模式。
- 配置读取容错：损坏或被手工改错的配置文件会回退到默认值，而不是导致无法启动。
- 单实例运行；可选开机启动。

## 快速开始

```powershell
git clone https://github.com/RealSenioume/SDfno3_1101
cd SDfno3_1101

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:PYTHONPATH = "src"   # 直接从源码运行，无需安装
python -m lolping
```

已经有代码了？跳过前两行，直接 `cd` 进入包含 `src`、`requirements.txt` 和
`pyproject.toml` 的目录。

程序会常驻系统托盘。按住 **Alt**，按下并保持**鼠标左键**，从光标位置向外拖动，
在想要的扇区上松开。要取消：按 **Esc**、点鼠标右键，或在死区内松开。退出可从托盘菜单
或按 **Ctrl+Shift+Q**。

打包成可执行文件的方法见 `docs/07-build-and-release.md`。

## 发送一次标记

1. 按住 **Alt** 并按下**鼠标左键**。轮盘在光标处出现。
2. 从中心向外拖动。光标下的扇区会被强调，图标放大，名称显示在中心。
3. 松开鼠标键即提交。轮盘中心绘制一段爆裂动画，同时向 `pings.jsonl` 写入一行记录。
4. 取消：在死区内（默认 34 px）松开、按 **Esc**，或在轮盘打开时点鼠标右键。

| 扇区 | 时钟位置 | 默认标签 | 默认图标 |
| --- | --- | --- | --- |
| 0 | 3 点钟 | On My Way | `on_my_way` |
| 1 | 4:30 | All-In | `all_in` |
| 2 | 6 点钟 | Assist Me | `assist` |
| 3 | 7:30 | Need Vision | `vision` |
| 4 | 9 点钟 | Enemy Missing | `missing` |
| 5 | 10:30 | Enemy Vision | `enemy_vision` |
| 6 | 12 点钟 | Retreat | `retreat` |
| 7 | 1:30 | Push | `push` |

图标 id `danger` 和 `generic` 同样可用，可在设置中指派给任意扇区。自定义 PNG 可以替换
某个扇区的图标；详见 `docs/05-user-manual.md`。

## 命令行

```text
python -m lolping [--config PATH] [--latency-probe] [--debug] [--self-test]
```

| 参数 | 含义 |
| --- | --- |
| `--config PATH` | 使用 `PATH` 代替 `%APPDATA%\lolping-desktop\config.json`。 |
| `--latency-probe` | 每次手势向 `latency.jsonl` 写入一行（`frame_ms`、`commit_ms`）。用于测量，不适合日常使用。 |
| `--debug` | 输出详细的诊断日志。 |
| `--self-test` | 运行内置的无界面自检后退出，安装后可用于验证。 |

## 文件

所有用户数据位于 `%APPDATA%\lolping-desktop\`：

| 文件 | 内容 |
| --- | --- |
| `config.json` | 设置窗口保存的配置。首次保存时创建；读取时容错。 |
| `pings.jsonl` | 每次提交的标记一行 JSON：`ts`、`sector`、`name`、`x`、`y`。 |
| `latency.jsonl` | 仅在 `--latency-probe` 时写入：`ts`、`frame_ms`、`commit_ms`。 |
| `lolping.log` | 滚动写入的诊断日志；反馈问题时请附上。 |

## 文档

| 文档 | 用途 |
| --- | --- |
| `docs/00-interfaces.md` | 冻结的模块接口契约（内部使用）。 |
| `docs/01-proposal.md` | 问题、目标、范围、技术选型、风险、计划。 |
| `docs/02-requirements.md` | 用户故事、功能与非功能需求、用例。 |
| `docs/03-design.md` | 设计理由与模块说明（维护者阅读）。 |
| `docs/04-test-plan.md` | 测试策略、矩阵、测试用例、测量协议。 |
| `docs/05-user-manual.md` | 安装、手势、设置项参考、故障排查。 |
| `docs/06-report-outline.md` | 最终报告的大纲与证据计划。 |
| `docs/07-build-and-release.md` | 打包与发布步骤。 |
| `docs/08-report-draft.md` | 报告正文草稿，未测量的数字标记为 TBD。 |

## 已知限制

- **独占全屏。** Windows 桌面叠加层通常无法显示在独占全屏应用之上。若需要看到轮盘，
  请以无边框或窗口化模式运行游戏。
- **管理员权限窗口。** 在 Windows 的用户界面特权隔离（UIPI）下，普通权限的 lolping
  无法绘制在管理员权限窗口之上，也收不到这些窗口的输入。必要时请以相同或更高的完整性
  级别运行 lolping。
- **全局输入钩子。** 部分安全软件会限制全局鼠标/键盘钩子。lolping 会监控并重启失效的
  监听器，但可能需要在安全软件中将其加入白名单。
- **触发冲突。** Alt + 鼠标左键被一些应用用作自己的快捷键。触发方式可配置，请在设置中
  更改。
- **声音不叠加。** Windows 的 `winsound` API 一次只能异步播放一个声音，因此新的音效会
  打断上一个。对于短音效而言这是刻意的取舍，不是缺陷。
- **范围。** 仅支持 Windows；v0.3.1 固定为八个扇区；不具备游戏感知能力；没有队伍或房间
  功能；不支持跨平台。

## 许可证

MIT 许可证。见仓库根目录的 `LICENSE` 文件。

## Riot Games 免责声明

该 lolping 未获得 Riot Games 的认可，也不代表 Riot Games 或任何正式参与制作或管理
《英雄联盟》的人士的观点或意见。《英雄联盟》与 Riot Games 是 Riot Games, Inc. 的商标或注册商标。
