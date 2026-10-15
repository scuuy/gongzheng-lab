# 工证 Lab

面向 CAD/CAE 智能体的工程验证与回归测试平台。接收工程交付与参数修改提案，重新打开 STEP、检验参数变型、重建网格、调用 CalculiX，并把验收结论绑定到原生证据。

当前版本 **0.1.0 · 研究原型**。六组自行构造的合成支架工程展示：正常交付、装配净空不足、参数变型失效、旧网格沿用、载荷方向错误、报告失配。支持的几何模型和线弹性工况范围见 [工程契约](docs/contract.md)。

## 从源码启动

需要 Docker（建议可用内存 ≥ 4 GB）、Python ≥ 3.10。首次构建需要网络；运行原生工具时不使用网络。已验证 Linux ARM64（macOS Docker Desktop）和 Linux x86_64（GitHub Actions Ubuntu 24.04）；构建、六组回归与 13 项测试均通过。

```sh
docker build -t gongzheng-native:0.1.0 .
scripts/docker-run.sh generate
scripts/docker-run.sh regression
python3 -m gongzheng.cli serve --port 8770
```

打开 http://127.0.0.1:8770 。页面首次展示的是已保存回归结果；点击“启动独立验收”才会启动新的工具容器。首次镜像构建可能需要数分钟。

页面的“重放此模型提案”按钮会应用已保存的真实模型提案并重新进行原生验收；不会在浏览器中再次调用模型 API。

## 命令行与模型接入

```sh
scripts/docker-run.sh verify examples/variant --out runs/my-review
scripts/docker-run.sh repair examples/variant --out runs/my-repair
scripts/docker-run.sh apply-proposal examples/variant examples/variant-model-proposal.json --out runs/my-model-proposal
scripts/docker-run.sh verify runs/my-model-proposal/candidate --requirements examples/variant/requirements.json --out runs/my-independent-check
scripts/docker-run.sh --help
```

`repair` 是确定性的演示配方，不调用模型。`apply-proposal` 接收模型或人工生成的 JSON 参数提案，只允许预定字段；验收要求来自原工程，模型不能通过提案修改它。调用方自行连接模型和管理密钥，平台不要求某一家模型服务。示例提案在本次制作中由网关模型实际生成，具体统计以发布证据为准；它们不是困难 benchmark。

```json
{"schema":"gongzheng.proposal.v1","parameters":{"length_mm":72,"width_mm":24,"height_mm":10,"boss_height_mm":4},"rationale_zh":"移除固定孔位覆盖，恢复孔位随宽度变化。"}
```

**信任边界：**自带案例中的 requirements.json 是演示公开契约。对外部智能体使用时，验收端必须通过 `--requirements` 传入不可由候选修改的独立规范路径。当前 Web 端仅接受六个内置案例，不提供任意文件上传，也不是多租户服务。

## 验证

```sh
scripts/docker-run.sh regression
scripts/docker-run.sh --help
docker run --rm --network none --entrypoint python gongzheng-native:0.1.0 -m unittest discover -s tests -v
```

测试包括五种缺陷的修复复验、STEP 与参数失配、修改材料后伪造哈希、合法注释等价、净空边界及提案权限。需先生成 examples（仓库附带可重放示例）。完整镜像中 13 项集成与 HTTP 测试已通过；六组回归符合预期。结果见 [实测证据](docs/evidence/README.md)。

## 能力边界

- 实际调用 CadQuery/Open CASCADE、Gmsh、CalculiX；工程产物包含 STEP、MSH、INP、DAT、FRD、JSON。
- 当前支持一个受限参数化支架适配器；不是任意 CAD 工程理解器。
- 网格与 STEP 的检查只有包络和体积粗一致性，不能证明任意网格等价。
- 原生求解输入按受支持适配器规范归一化比对；额外或不支持的求解卡片会被拒绝，不是通用 CalculiX 解析器。
- 未实现接触、非线性、疲劳、网格收敛认证。示例通过不代表生产安全认证。
- 六个预设回归案例不能推导总体检出率，也不支持“达到 ALE 难度”的声明。

## 开源与协作

自有代码采用 Apache-2.0，合成示例随项目以同一许可提供。外部原生工具保留各自许可证，见 [第三方说明](THIRD_PARTY_NOTICES.md)。欢迎贡献适配器、反例和可重放测试；请阅读 [贡献规范](CONTRIBUTING.md)、[安全边界](SECURITY.md) 和 [路线图](ROADMAP.md)。

## 参赛材料

在线入口：[工证 Lab 参赛材料](https://scuuy.github.io/gongzheng-lab/site/)。

作品介绍、演示视频和路演材料见 [v0.1.0 发布页](https://github.com/scuuy/gongzheng-lab/releases/tag/v0.1.0)。本仓库按源码运行；当前不提供包含 Web 资源的独立 wheel 安装包。
