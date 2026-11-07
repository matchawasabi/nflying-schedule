# N.Flying 行程日历

自动追踪 N.Flying 团体及成员公开行程。GitHub Actions 每天北京时间 09:37、16:37 运行；GitHub Pages 发布日历。

## 来源核验原则

详见 [SOURCE_POLICY.md](SOURCE_POLICY.md)。官方官网及经核验身份的官方 X、Instagram、Weverse 原帖可单一来源确认；第三方非官方信息必须由至少两个独立发布主体分别提供原始证据。转载、镜像、翻译版、多个账号转发同一链接均只计一个源。单一非官方线索仅进入待核实报告，不进入正式日历。

## 当前自动化范围

- FNC 韩国官网：按月读取行程日历并尝试打开逐日详情。
- N.Flying 日本官网：读取官方 schedule 页面及可识别的结构化活动数据。
- 官方 X：通过 X API v2 读取 @NFlyingofficial、@NF_official_jp 的原创帖子。
- 官方 Instagram：通过 Meta Graph API Business Discovery 读取 @letsroll_nf 的公开媒体帖文。
- 只将含明确日期和活动关键词的官方社媒内容提取为行程；日期或活动性质不明确的原帖保存在 `reports/social_review.json`，供人工核查。
- 原始帖子和来源链接保存在 `reports/social_posts.json`；平台访问失败会写入 `reports/latest.json`，不会把“读取失败”解释为“没有行程”。
- Weverse 暂未接入自动读取；官方社区入口确认后再接入。
- 第三方非官方信息当前不会自动从全网发现；未来接入时仍必须满足两个独立原始来源的核验门槛。

## 配置 X / Instagram 自动抓取（必做）

在 GitHub 仓库 `Settings → Secrets and variables → Actions → New repository secret` 添加以下 Secrets。**不要把 Token 粘贴到聊天、代码或公开仓库。**

| Secret 名称 | 用途 |
|---|---|
| `X_BEARER_TOKEN` | X Developer Portal 中应用的 Bearer Token；需要有读取公开用户帖子时间线的 API 权限/套餐 |
| `META_ACCESS_TOKEN` | Meta Developer App 的有效 Graph API User Access Token |
| `META_IG_USER_ID` | 与该 Meta App / Facebook Page 关联的 Instagram 专业账号 ID（用于调用 Business Discovery） |

Instagram 侧需要一个可调用 Instagram Graph API 的 Meta App，以及与 Facebook Page 关联的 Business/Creator 专业账号和相应权限。Business Discovery 的目标账号是官方公开账号 `letsroll_nf`；这里的 `META_IG_USER_ID` 是你用于发起 API 请求的专业账号 ID，不是 N.Flying 的账号 ID。Meta 权限、Token 有效期和 API 版本以 Meta 当前开发者后台为准。

可选变量：在 `Settings → Secrets and variables → Actions → Variables` 添加 `META_GRAPH_VERSION`，例如 `v24.0`；未设置时使用脚本默认值。

配置完成后，在仓库 `Actions → Update N.Flying schedule → Run workflow` 手动运行一次。检查运行日志以及 `reports/latest.json`、`reports/social_posts.json`、`reports/social_review.json`，确认 X 与 Instagram 均有成功读取记录，再由每天两次的定时任务持续更新。

## 首次启用 GitHub Pages

1. 在仓库 `Settings → Pages` 中，将 Source 设为 **GitHub Actions**。
2. 在 Actions 页面启用 workflow，并手动运行一次 **Update N.Flying schedule**。
3. Pages 部署成功后，网址为 https://matchawasabi.github.io/nflying-schedule/ 。

## 定时

GitHub Actions 使用 UTC cron `37 1,8 * * *`，对应北京时间每天 09:37、16:37。

## 重要限制

X API 访问取决于开发者账号的 API 权限/套餐；Instagram Business Discovery 仅适用于符合 Meta API 要求的专业账号和授权 Token。凭证未配置、失效或权限不足时，报告会明确标记平台不可读取。当前工作流负责更新 GitHub 仓库和网页，不会自动向 ChatGPT 对话发送消息；不能将 GitHub Actions 运行成功等同于 ChatGPT 已推送。
