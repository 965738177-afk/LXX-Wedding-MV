# LXX-Wedding-MV

**婚礼全程、预告与MV：可复用的剪辑规则与 Final Cut 原素材工程 skill。**

这是从真实婚礼剪辑协作中整理的 Agent Skill，适合婚礼预告、MV、微电影的制作和重剪，并补充独立的婚礼全程规则。它包含工作流程、选镜原则、原素材工程注意事项和一个只读 FCPXML 核验工具。实际选镜仍需观看画面、听音乐；不是一键自动成片软件，也不包含 Final Cut 控制连接器。

## 核心原则

- **保护用户选材：**指定只用现有时间线时，严格限于已有原片及已选源区间。
- **保护用户版本：**重剪前备份，另建项目；用户最终成片优先，不用助手初稿覆盖。
- **音乐与故事：**按指定参考音乐组织场布、新人、亲友互动及婚礼情绪，时长和结尾服从当次要求。
- **原片可编辑：**直接引用源文件，保留原声组件，变速、字幕和音量在工程中可调整。
- **导入后验收：**核对帧率、时长、空隙、缺失媒体、选材越界和实际导出。

全程按时间顺序覆盖有效内容，短片按叙事精选；两套规则分开执行。没有固定33秒 / 40秒、固定歌曲、固定蓝金或黑金色调。

## 当前规则（2026-10-29）

- [稳定核心与重复取舍](skills/wedding-mv-finalcut/references/shot-selection.md)：掐头尾、往返运镜只取稳定一段、近似空镜优先后拍有效段、保留暗场与不同人物组合。
- [婚礼全程与事件防漏](skills/wedding-mv-finalcut/references/full-wedding.md)：逐条覆盖、场景开头先空镜、重要过程与原声、全场宾客大合影、事件范围与未用素材对账。
- [誓言旁白与语义匹配](skills/wedding-mv-finalcut/references/vows-and-semantic-editing.md)：完整句、说话人确认、实际采用区间匹配、独立人声和配乐避让。
- [预告／MV结构与风格](skills/wedding-mv-finalcut/references/story-and-style.md)：预告通常30～60秒、MV通常3～6分钟；按当次音乐、结构、节奏和侧重调整。
- [FCPXML检查](skills/wedding-mv-finalcut/references/fcpxml-native-editing.md)：授权范围、帧率、变速、连接音轨锚点、时间分母与真实导入检查。

这是规则与 Agent Skill 仓库，**不包含桌面软件源码、应用安装包、模型权重或客户素材**。规则要求不等于自动能力已全部实现；声纹、识别、审美及原生导入需要实际验证。初稿可以保留待复核标记交付，不替用户勾选已核对。

## 安装

在支持本地 Agent Skills 的 Codex 中，将整个 skill 文件夹放到个人技能目录。当前目录规范见 [OpenAI 官方 Build skills 文档](https://learn.chatgpt.com/docs/build-skills)。

```bash
git clone https://github.com/965738177-afk/LXX-Wedding-MV.git
mkdir -p "$HOME/.agents/skills"
cp -R LXX-Wedding-MV/skills/wedding-mv-finalcut "$HOME/.agents/skills/"
```

目标目录已有同名 skill 时先备份，避免覆盖本地修改。也可以让 `$skill-installer` 从本仓库的 `skills/wedding-mv-finalcut` 目录安装。无法识别时检查所在客户端的技能路径并重新打开会话。

支持读取 `SKILL.md` 的其他代理可按自己的技能目录规则安装。实际剪辑需要可访问用户原片、参考音乐，并有当前环境允许的 Final Cut 控制或 FCPXML 导入能力；只有云端对话、无法访问本地应用时不能声称已在 Final Cut 剪好。

## 使用示例

```text
使用 $wedding-mv-finalcut：
我已在 Final Cut 挑好素材，只用当前时间线已有片段和区间。
按我提供的参考音乐剪40秒预告，场布空镜和场内摆拍为主，
少量大堂摆拍，楼梯大合影结尾。
先备份，另建“婚礼预告_重剪”，保留原素材和可恢复原声。
```

没有预选素材时，明确指定可选素材目录。提供目标时长、参考视频或音乐、工程名，以及任何必须出现的画面。重剪的主体是可编辑时间线，预览成片用于确认风格。

## 时间线核验

核验工具使用 **Python 3.9+ 标准库**，不需安装 Python 第三方库，也不改变工程：

```bash
python3 skills/wedding-mv-finalcut/scripts/audit_fcpxml.py \
  after.fcpxmld --expected-duration 40 --selection before.fcpxmld
```

`before` 是用户选材的备份，`after` 是 Final Cut 实际回导。多个项目时使用 `--project` 和 `--selection-project` 选择名字。复杂 timeMap / 结构会提示人工复核；脚本通过也不等于画面和音乐已经验收。完整边界与退出码见 [FCPXML 说明](skills/wedding-mv-finalcut/references/fcpxml-native-editing.md)。

运行测试：

```bash
python3 -m unittest discover -s tests -v
```

## 文件

```text
skills/wedding-mv-finalcut/
├── SKILL.md
├── agents/openai.yaml
├── references/full-wedding.md
├── references/shot-selection.md
├── references/vows-and-semantic-editing.md
├── references/story-and-style.md
├── references/fcpxml-native-editing.md
└── scripts/audit_fcpxml.py
tests/test_audit_fcpxml.py
```

## 开源范围与贡献

本仓库的原创工作流程与代码采用 [MIT License](LICENSE)，可使用、修改和再分发。婚礼客户视频、参考音乐、字体、商业排版模板、Final Cut 本身及第三方工具不包含在仓库中，其权利不由本许可证授予。

提交问题时使用合成 XML 或已脱敏的小示例，说明帧率、期望行为与实际报错。不要提交客户影像、本机绝对路径、媒体 bookmark、账号凭据或未经许可的音乐。欢迎完善不同帧率、复杂时间线核验和跨环境使用说明。

**English:** An Agent Skill for editable wedding teasers and MVs in Final Cut Pro. It protects user-selected source ranges and manual edits, follows the supplied music and brief, keeps original media and recoverable audio, and verifies the imported timeline. Documentation is primarily in Chinese; the audit helper needs only Python's standard library. No client footage or music is distributed.
