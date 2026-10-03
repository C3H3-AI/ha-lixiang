"""pytest 配置

★ 架构方案 T0：先测 render() 纯函数，不碰 HA 运行时。
  rendering.py 刻意不依赖 homeassistant 包，所以测试无需 HA 环境。
"""

import sys
from pathlib import Path

# 把集成目录加入 sys.path，使 `import rendering` 可用
INTEGRATION_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
sys.path.insert(0, str(INTEGRATION_DIR))
