"""_state.json 的条目记账。

单独成模块而不是留在 run_batch.py 里:后者顶部 import 了 voxcpm/librosa/
mlx_whisper 那一套重依赖,CI 只装 pytest+opencc,import 不进去就没法测
—— 跟 backend 侧 audio_verdict.py 的分法同理。
"""


def pick(tries):
    """多次尝试里留哪一次 → 下标。

    合格优先;合格的里面节奏达标(paced)优先;同档取最早的一次。
    全不合格 → 最后一次(被移进 _rejected/ 的那个,行为与择优之前一致)。
    paced 是软偏好,不进 ok:它决定"留哪条",不决定"算不算合格"。
    """
    ok = [i for i, t in enumerate(tries) if t["ok"]]
    if not ok:
        return len(tries) - 1
    return ([i for i in ok if tries[i].get("paced", True)] or ok)[0]


def make_record(tries, seed, md5, *, kept=-1, pipeline=None):
    """把一条任务的多次尝试折成 _state.json 条目。

    顶层分数**必须**取磁盘上那个文件对应的那次尝试(`kept`,由 pick 给出)。

    ⚠️ 旧版把 sharp/consist 取自"锐度最优的一次",lenratio/atempo 却是循环
    残留的最后一次值 —— 三方错位,且**只在失败条目上错**。后果不是脏数据而是
    误诊:ja/background 的 state 记 consist=0.06(第一次尝试),拿 _rejected/
    里的文件重算实为 0.79。tries 原样保留每一次的分数 —— 坍缩成单个数字后,
    没人能倒推它错在哪,包括写它的人。

    pipeline = 起跑时仓库 commit(start_run.sh 注入)。灌入端缺它就拒绝 ——
    2026-10-19 起有批次用了生成机上的旧副本,535 条响度乱掉的音频照样上了线。
    """
    return {**tries[kept], "seed": seed, "tries": tries, "md5": md5,
            "pipeline": pipeline}
