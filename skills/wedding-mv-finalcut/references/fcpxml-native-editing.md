# FCPXML 原素材工程：易错点与核验

## 环境与备份

从当前 Final Cut 工程 / 事件导出资源索引和重剪前备份。`.fcpxmld` 是目录包，XML 入口通常为 `Info.fcpxml`。使用当前应用支持的版本，不把某台机器上的版本、路径、插件、Python 虚拟环境当作别人机器的默认值。

已有成熟能力时优先使用，例如 [CommandPost](https://github.com/CommandPost/CommandPost) 的 Final Cut 自动化与 FCPXML 支持。按用户环境选择，不因本 skill 自动安装插件或改变用户的应用设置。

## 原片与身份

- 优先复用 Final Cut 自己导出的 `asset`、`format`、原始 `media-rep`、UID、媒体签名和 bookmark。不同目录 / 摄像机可能有同名原片，不能只按文件名匹配。
- 原片路径可指向资源库的 Original Media 或用户授权的外部源文件；两者均须检查实际存在、可播放及没有离线提示。
- 工程剪辑引用原片，保留音轨、组件与既有角色。音乐主导只改变静音状态，不以无声中间文件替代原片。
- 重剪项目使用新的项目 UID 和清楚的名称；保持源资源身份。导入同 UID 可能触发替换，确认实际对象是本次重剪版本，而非用户最终成片。

## 时间、帧率、变速

使用精确有理数表示时间，避免浮点累加导致接点偏离帧边界。时间线 offset / duration 按**工程帧率**核对；原片入点按**源帧率**核对。它们未必相同。音乐和音频组件允许样本精度，不能把所有音频时间强制裁成视频帧。

例如60000/1001 fps素材在30 fps工程中，一帧原片对应一帧输出时，播放速度为 `30 / (60000/1001) = 1001/2000`，约50.05%。这不是所有视频通用的50%规则。

`timeMap` 的 `timept.time` 是调整后的局部时间，`value` 是原局部时间；clip 的 `start` 在重映射后时钟中解释。连接项的 offset 也需按实际父项局部时间核对，不能一律写0。参考 [Apple timeMap 文档](https://developer.apple.com/documentation/professional-video-applications/timemap)。

平滑加速要检查首尾、有效源区间、单调性与真实播放；Final Cut 可能在回导时延展或改写 timeMap 端点。不能要求两个 XML 字面完全相同，也不能只比较变速端点而忽略中段越界。受限选材中，只能使用已选源区间；无法可靠证明复杂曲线没越界时，在应用内逐段确认。

## 原生淡入淡出

内建 adjustment 下的 `param.name` 是对应属性名，区分大小写；不是显示给用户的“Opacity”或“Volume”标签。透明度和音量都用 `amount`，数值单位分别为比例和 dB。例如：

```xml
<adjust-blend>
  <param name="amount">
    <fadeOut type="linear" duration="8/30s"/>
  </param>
</adjust-blend>
<adjust-volume>
  <param name="amount">
    <fadeOut type="linear" duration="8/30s"/>
  </param>
</adjust-volume>
```

示例不是固定淡出长度。按音乐和项目帧率设置，并在回导中核对调整仍存在。错误的属性名可能被应用忽略而不报错。参考 [Apple 调整属性与参数文档](https://developer.apple.com/documentation/professional-video-applications/adjustment-attributes-and-effect-parameters)。

## 只读核验工具

`scripts/audit_fcpxml.py` 使用 Python 3.9+ 标准库，无额外 Python 包。读取 `.fcpxml` 或 `.fcpxmld`，不修改工程或媒体。

```bash
python3 scripts/audit_fcpxml.py revised.fcpxmld --project '婚礼预告_重剪' --expected-duration 40
python3 scripts/audit_fcpxml.py revised.fcpxmld --selection selected-before.fcpxmld --selection-project '用户选材'
```

工具检查简单主故事线的连续性、视频编辑帧边界、声明总长、asset引用及本机原始媒体是否存在。可选 `--selection` 限定到备份中已有原片和选定源区间，支持普通切片和分段线性 timeMap；不同源区间的间隔不能跨过。

退出码：0为支持范围内的结构检查通过；1为明确错误；2为输入 / 参数错误；3为存在需要人工复核的复杂结构或平滑 timeMap。`--no-check-media` 仅供没有本机媒体的结构诊断，不代表媒体在线。

此工具不做 DTD 验证、解码质量检查、字幕 / 模板安装检查、光流畸变检测、音乐落点分析或原声恢复测试。复合片段、多机位、同步片段、转场等结构不会被静默跳过当作完全通过。工程中使用复杂结构时按报告进行应用内核对。

## 实际验收

1. 导入后打开正确项目，确认素材仍是原片名，片段可修剪、变速可改、原声可恢复。
2. 查看每一处接点和尾部；修正任何帧边界警告、缺失片段、空隙和误加尾帧。
3. 回导当前项目核对镜头顺序、时长、源身份和源区间。对平滑变速检查实际播放，不仅看XML。
4. 检查 Final Cut 实际导出的分辨率、帧率、总长、声音、字幕和指定结尾。其他程序渲染的近似预览另行标记，不冒充原生导出。

## 连接音轨与时间分母：导入警告排查

配乐或旁白的连接锚点须落在对应父镜头的有效局部区间内；后面几十分钟的配乐不能全部挂到第一个几秒镜头的远端位置。将连接项分配给其时间线起点所在的父镜头，按该父项局部时钟换算 offset；音轨本身可以依法延伸到父镜头之外。变速或复杂父项须按实际局部映射核验，不能只套无变速公式。

以无变速为例：项目第100秒开始的父镜头，局部start为20秒，配乐从项目第102秒开始，则连接offset为22秒，不是102秒。

不要把浮点误差直接变成几万亿分母的Fraction写入XML。CMTime的timescale为有符号32位；用原始有理时钟，音频源入点落到其采样时钟（如44100或48000Hz），并验证整段在音源范围内；视频仍按对应帧率对齐。不在此文中声称已通过所有Final Cut版本的原生导入。

若出现“未包含相应媒体的无效编辑”，定位报错XML节点，检查源区间、媒体身份、连接锚点和时间分母。语法/DTD通过不等于Final Cut原生导入通过。现有audit脚本不完整校验这些音轨约束，仍需专项核验和实际导入，不把它的passed当作此类错误已排除。
