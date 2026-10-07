"""各馆「必看」作品清单 —— 预生成与馆藏列表的排序头部。

替代 popularity 当排序主键:popularity = Wikidata 跨语言条目数,prod 77% 为 0
(Joconde 源的件写死 0),同分大面积平局 → 前 N 件由 id 决定,等于随机。

来源(2026-09-30 摸底,qid 逐件在 prod 核过馆/作者/年代):
- louvre:官方参观线路 12 件
- orsay:官网无逐件清单,取主流导览共识
- petit_palais:官网 chefs-d'œuvre 页 11 件里能唯一对上的 7 件
  (乌戈林像库里 4 个同名版本分不清,其余库里没有 —— 不猜)
- orangerie:睡莲库里有的 7 块(缺《Matin aux saules》)+ 保罗·纪尧姆像;
  另 3 件是无图件(9-05 定不做)

改清单只需部署后端,不用发 App 包。顺序即排序。
"""

from sqlalchemy import and_, case, exists, or_

from app.models.museum_object import MuseumObject, ObjectImage

MUST_SEE: dict[str, list[str]] = {
    "louvre": [
        "Q12418",  # 蒙娜丽莎
        "Q151952",  # 米洛的维纳斯
        "Q216402",  # 萨莫特拉斯的胜利女神
        "Q1114881",  # 波提切利壁画
        "Q656434",  # 美丽的费隆妮叶夫人
        "Q563727",  # 圣母子与圣安妮
        "Q185255",  # 迦拿的婚礼
        "Q212616",  # 梅杜萨之筏
        "Q29530",  # 自由引导人民
        "Q83862",  # 垂死的奴隶
        "Q3203231",  # 叛逆的奴隶
        "Q517408",  # 普赛克与爱神
    ],
    "orsay": [
        "Q737062",  # 奥林匹亚
        "Q152509",  # 草地上的午餐
        "Q683274",  # 煎饼磨坊的舞会
        "Q17495196",  # 梵高自画像 1887
        "Q3630735",  # 梵高自画像 1889
        "Q1213917",  # 奥维尔教堂
        "Q1464531",  # 罗纳河上的星夜
        "Q18543956",  # 阿尔勒的卧室
        "Q105444311",  # 十四岁的小舞者
        "Q1368055",  # 拾穗
        "Q2571560",  # 晚祷
        "Q687182",  # 惠斯勒的母亲
        "Q334138",  # 世界的起源
        "Q540488",  # 奥尔南的葬礼
        "Q1167178",  # 画家的工作室
        "Q3231771",  # 阿让特伊的罂粟花田
        "Q2270028",  # 圣拉扎尔火车站
        "Q17436678",  # 鲁昂大教堂
        "Q1766454",  # 刨地板的工人
        "Q1165042",  # 玩牌的人
        "Q930535",  # 沙滩上的大溪地女人
        "Q1239950",  # 苦艾酒
        "Q1212861",  # 维纳斯的诞生(卡巴内尔)
    ],
    "petit_palais": [
        "Q326503",  # 睡眠者(库尔贝)
        "Q53846832",  # 巴黎中央市场(莱尔米特)
        "Q104445860",  # 萨拉·伯恩哈特像(克莱兰)
        "Q50818703",  # 拉瓦库尔塞纳河上的日落(莫奈)
        "Q106462064",  # 菲恩达讷西青年铜像
        "Q104479426",  # 圣马丁(圣像)
        "Q99472451",  # 猴子音乐会座钟
    ],
    "orangerie": [
        "Q28797622",  # 睡莲·落日
        "Q28797619",  # 睡莲·绿色倒影
        "Q28797618",  # 睡莲·柳树下的晴朗清晨
        "Q3828905",  # 睡莲·云
        "Q28797620",  # 睡莲·清晨
        "Q28797625",  # 睡莲·树影
        "Q28797624",  # 睡莲·两棵柳树
        "Q3937645",  # 保罗·纪尧姆像(莫迪利亚尼)
    ],
}

ALL_MUST_SEE: frozenset[str] = frozenset(q for qs in MUST_SEE.values() for q in qs)


def must_see_order(slug: str | None) -> list:
    """ORDER BY 头部键,用法 `order_by(*must_see_order(slug), 其余键...)`。

    必看件按清单顺序 0..n-1,其余 n;没清单的馆 → 空列表(排序照旧)。"""
    qs = MUST_SEE.get(slug or "", [])
    if not qs:
        return []
    return [
        case({q: i for i, q in enumerate(qs)}, value=MuseumObject.qid, else_=len(qs))
    ]


def has_image_clause():
    """有图过滤:对象至少有一张可展示图(image_key 或 source_url 非空,且非隔离图)。

    与 must_see_order 同属"馆 TOP-N 是谁"这一个问题:App 藏品列表(浏览面)
    只给有图件排名,生成/报告用的 top_objects 曾经不过滤,导致两边候选池不同、
    排出来的第 N 位不是同一件(2026-10-07 橘园 TOP50 实例)。统一到这一个函数,
    谁用 top_objects / must_see_order 就自动跟 App 列表口径一致。
    qid 直达与搜索不受影响,只影响"前 N 件是谁"这个排名问题。
    """
    return exists().where(
        and_(
            ObjectImage.object_id == MuseumObject.id,
            or_(
                ObjectImage.image_key.isnot(None),
                ObjectImage.source_url.isnot(None),
            ),
            ObjectImage.role != "view_quarantine",
        )
    )
