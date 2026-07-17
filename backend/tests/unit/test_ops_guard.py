"""staging 护栏:staging 上带 LLM 的批命令默认小样本;全量须显式 --allow-full。"""

import pytest

from scripts.ops_guard import (
    STAGING_SAMPLE_LIMIT,
    staging_limit,
    staging_require_allow_full,
)


def test_staging_limit_tightens_none_and_large():
    assert staging_limit("staging", None, False) == STAGING_SAMPLE_LIMIT
    assert staging_limit("staging", 5000, False) == STAGING_SAMPLE_LIMIT


def test_staging_limit_keeps_small_prod_and_allow_full():
    assert staging_limit("staging", 10, False) == 10
    assert staging_limit("prod", None, False) is None
    assert staging_limit("staging", None, True) is None


def test_require_allow_full():
    staging_require_allow_full("prod", False)  # prod 不拦
    staging_require_allow_full("staging", True)  # 显式确认放行
    with pytest.raises(SystemExit):
        staging_require_allow_full("staging", False)
