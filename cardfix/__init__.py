"""cardfix 子包：对外暴露补丁 API（薄接口，细节在 patch 模块）。"""

from .patch import ensure_applied, is_applied, self_check

__all__ = ["ensure_applied", "is_applied", "self_check"]
