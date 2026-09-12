"""探活脚本的判定逻辑(不打真网)。

值得测的只有一件事:**这个脚本会不会在该喊的时候喊**。
一个永远返回 0 的探活脚本比没有探活更糟 —— 它让人以为有人看着了。
真源的连通性由脚本自己的 --self-test 在 cron 里每天验,不在这里模拟。
"""

import pytest

from scripts import probe_sources as ps


@pytest.fixture()
def probes(monkeypatch):
    """装一组可控探针,替换真实的(避免打网)。"""

    def install(behaviour: dict):
        monkeypatch.setattr(ps, "PROBES", {k: v for k, v in behaviour.items()})
        monkeypatch.setattr(ps, "BROKEN", {k: {} for k in behaviour})
        return sorted(behaviour)

    return install


def _ok(**kw):
    return "fine"


def _dead(**kw):
    raise RuntimeError("upstream gone")


def test_run_all_alive_exits_zero(probes, capsys):
    assert ps.run(probes({"a": _ok, "b": _ok})) == 0


def test_run_one_dead_exits_nonzero(probes, capsys):
    """一个源死掉就得非零 —— cron 靠退出码,不靠有人读日志。"""
    assert ps.run(probes({"a": _ok, "b": _dead})) == 1
    out = capsys.readouterr().out
    assert "[FAIL] b" in out
    assert "[OK]   a" in out  # 其余源照常报告,别因为一个死的就瞎了


def test_run_names_the_dead_source(probes, capsys):
    """输出要点名是谁死了:探活日志会被扫,不会被读。"""
    ps.run(probes({"joconde": _dead, "wikipedia": _ok}))
    assert "探不通的源: joconde" in capsys.readouterr().out


def test_self_test_passes_when_probes_reject_bad_input(probes):
    assert ps.self_test(probes({"a": _dead, "b": _dead})) == 0


def test_self_test_catches_a_probe_with_no_judgment(probes, capsys):
    """坏输入还说 OK 的探针 = 没有判断力,必须单独用退出码 2 区分。

    和"源死了"(1)分开,因为处置完全不同:1 去查上游,2 是我们自己的探针坏了、
    在此之前所有'一切正常'都不作数。
    """
    assert ps.self_test(probes({"a": _dead, "b": _ok})) == 2
    assert "没有判断力: b" in capsys.readouterr().out


def test_golden_sample_is_the_mona_lisa():
    """金标样本别被人随手换成冷门件 —— 冷门件下架会伪报成'源死了'。"""
    assert ps.GOLDEN_QID == "Q12418"
    assert ps.BROKEN.keys() == ps.PROBES.keys()  # 每个探针都要有坏样本
