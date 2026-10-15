# 第三方软件说明

本仓库的自有代码与合成示例使用 Apache-2.0。运行依赖以下独立项目；此表用于透明披露，不将第三方代码重新许可为 Apache-2.0。

| 项目 | 许可 / 使用方式 | 上游 |
|---|---|---|
| CadQuery | Apache-2.0；Python API | https://github.com/CadQuery/cadquery |
| Open CASCADE / OCP | LGPL-2.1 系及上游例外；CadQuery 几何依赖 | https://github.com/CadQuery/OCP |
| Gmsh | GPL-2.0-or-later；系统包及 Python API | https://gmsh.info/ |
| CalculiX | GPL-2.0-or-later；独立求解进程 | https://www.calculix.de/ |
| meshio | MIT | https://github.com/nschloe/meshio |
| NumPy | BSD-3-Clause | https://numpy.org/ |
| Ubuntu / Python 及传递依赖 | 各自许可证；Dockerfile 构建时获取 | https://ubuntu.com/ / https://www.python.org/ |

当前交付开源源代码和 Docker 构建配方，不分发包含第三方二进制的预构建镜像。若后续分发镜像或整合为其他产品，需要按对应版本许可证保留通知、提供所需源码/书面要约并重新评估组合与分发义务。此说明不代替完整法律审查。

参赛 HTML 路演材料使用的 deck-stage.js 为 Lark Technologies 的 MIT 组件，文件保留版权头；不属于本产品运行时依赖。参赛文档和视频为本次制作，软件截图来自本作品。旁白为系统合成语音。
