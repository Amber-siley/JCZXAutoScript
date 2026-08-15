"""共享 fixture：方案 3（regression）基于真实 jczx/Config 的只读副本。"""
import shutil
from os.path import abspath, dirname, join

import pytest

PROJECT_ROOT = dirname(dirname(abspath(__file__)))
CONFIG_DIR = join(PROJECT_ROOT, "jczx", "Config")


@pytest.fixture
def real_config_dir(tmp_path):
    """拷贝真实 jczx/Config 到临时目录，避免污染源文件。"""
    dst = tmp_path / "cfg"
    shutil.copytree(CONFIG_DIR, dst)
    return str(dst)
