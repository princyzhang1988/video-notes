# 小红书视频帖子 HTML 模板

小红书视频帖子（2-5 分钟短视频）不用 `note-template.html`，因为它为长视频设计（侧边导航、字幕面板、章节跳转、关键帧画廊都不适用）。

改用**居中单页布局**，深色主题 CSS 变量与视频笔记完全一致。

## 模板特性

| 区域 | 内容 |
|------|------|
| Hero | 平台标识 + 时长、标题、作者/IP属地、互动数据、标签 chips、金句引用 |
| 核心洞察 | 2-3 段，直接下判断（Thiel 式） |
| 方法论步骤 | `.step` 组件：编号圆圈 + 标题 + 说明，用于拆解方法论/流程类内容 |
| 金句区 | `.ql` 引用块，提取最有冲击力的原话 |
| 转录折叠 | `<details>` 包裹的完整转录文本 |
| 属性尾注 | 来源、帖子ID、链接、工具链接、日期 |

## CSS 关键类

```css
.steps{counter-reset:step}
.step{background:var(--card);border:1px solid var(--border);border-radius:var(--r);
      padding:18px 22px;margin-bottom:10px;padding-left:60px;position:relative}
.step::before{counter-increment:step;content:counter(step);
              position:absolute;left:18px;top:18px;
              width:28px;height:28px;background:var(--accent);
              color:var(--text);border-radius:50%;
              display:flex;align-items:center;justify-content:center;
              font-size:13px;font-weight:700}
.transcript{background:var(--card);border:1px solid var(--border);
            border-radius:var(--r);padding:16px 20px;
            font-size:13px;color:var(--text2);line-height:2;
            max-height:300px;overflow-y:auto}
```

## 生成流程

1. 转录视频获取文本（Step S2）
2. 从转录中提取核心论点和步骤结构
3. 按模板生成 HTML → 保存到 `/tmp/`
4. `cp` 到 vault `知识库/30.Resources/视频/`
5. `open` 预览

## 已完成示例

- `cheat-on-content` 视频（2m23s）：5 步方法论 + 金句区 + 完整转录折叠
- 保存路径：`知识库/30.Resources/视频/爆款不是抄出来的是AhaMoment-cheat-on-content.html`
