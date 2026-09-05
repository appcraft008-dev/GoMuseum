"""_state.json 的条目记账。

单独成模块而不是留在 run_batch.py 里:后者顶部 import 了 voxcpm/librosa/
mlx_whisper 那一套重依赖,CI 只装 pytest+opencc,import 不进去就没法测
—— 跟 backend 侧 audio_verdict.py 的分法同理。
"""


def make_record(tries, seed, md5):
    """把一条任务的多次尝试折成 _state.json 条目。

    顶层分数**必须**取最后一次尝试(tries[-1]),因为磁盘上那个文件就是最后一次
    写出来的:成功即 break,所以成功时最后一次就是合格那次;失败时最后一次就是
    被移进 _rejected/ 的那个。

    ⚠️ 旧版把 sharp/consist 取自"锐度最优的一次",lenratio/atempo 却是循环
    残留的最后一次值 —— 三方错位,且**只在失败条目上错**(成功条目 break 后
    三者本来同源)。后果不是脏数据而是误诊:ja/background 的 state 记
    consist=0.06(第一次尝试),拿 _rejected/ 里的文件重算实为 0.79,差点据此
    断定"内容彻底跑偏、无解"。tries 原样保留每一次的分数 —— 坍缩成单个数字后,
    没人能倒推它错在哪,包括写它的人。
    """
    return {**tries[-1], "seed": seed, "tries": tries, "md5": md5}
