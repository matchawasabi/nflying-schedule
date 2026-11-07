# N.Flying 行程日历

自动追踪 N.Flying 团体及成员公开行程。GitHub Actions 每天北京时间 09:37、16:37 运行；GitHub Pages 发布日历。

## 当前自动化范围

- FNC 韩国官网行程页：按月读取并尝试打开逐日详情。
- N.Flying 日本官网：读取官方 schedule 页面及可识别的结构化活动数据。
- 只将可识别的官方明确日期/标题写入日历；不可识别内容写入 `reports/latest.json` 待人工核查。
- 社交媒体 X、Instagram、Weverse 当前未配置稳定的官方读取接口，报告中会标明不可读取。
- 上次数据作为基线保留，官网暂时不可用不会导致旧行程被批量删除。

## 首次启用

1. 在仓库 Settings → Pages 中，将 Source 设为 **GitHub Actions**。
2. 在 Actions 页面启用 workflow，运行一次 **Update N.Flying schedule**。
3. Pages 部署成功后，网址为 https://matchawasabi.github.io/nflying-schedule/ 。

## 定时

GitHub Actions 使用 UTC cron `37 1,8 * * *`，对应北京时间每天 09:37、16:37。

## 重要限制

这是基于公开网页结构的保守抓取器，不是搜索引擎级别的全网检索。FNC 页面结构变化、反爬、或日本官网动态加载可能造成漏抓；人工核查报告会保留可疑页面。当前工作流负责更新仓库和网页，不会自动向 ChatGPT 对话发送消息。要实现 ChatGPT 对话内通知，仍需单独配置可用的 ChatGPT 自动化/通知能力；不能将 GitHub Actions 运行成功等同于 ChatGPT 已推送。
