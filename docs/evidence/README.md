# 实测证据

- regression.json：六组预设回归，正常工程 accept，五类缺陷 reject，全部符合预期。
- tests.txt：最终独立 Ubuntu 镜像内运行 13 项集成与 HTTP 测试，全部通过。
- model-demo.json：两次真实模型调用统计及提案；model-variant.json / model-clearance.json：对应验收结果。
- native-versions.txt：实际工具版本；native-image-id.txt：本次本地镜像标识（不是公开镜像下载地址）。

模型提案在独立镜像中再次应用并通过 8/8 检查。详细工件在发布包 evidence/ 中，运行时可自行用 CLI 重放。

这些是合成工程回归和接入演示。不得据此推导工业总体检出率、模型困难度或生产安全认证。模型名为网关返回标识，底层身份未独立认证；API 费用 unknown；pass@K 未测。

GitHub Actions x86_64 独立构建、生成、六组回归和 13 项测试亦已通过，运行链接与对应 commit 见 github-ci-summary.json。
