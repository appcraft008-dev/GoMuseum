"""从 DB 读馆藏并拼回与旧 museum_packs JSON 完全一致的形状（保接口兼容）。"""

import re
from datetime import datetime, timezone
from functools import lru_cache

from sqlalchemy import and_, exists, func, or_
from sqlalchemy.orm import Session

from app.models.content import (
    CategorySection,
    ObjectContentSection,
    ObjectSuggestedQuestion,
    SectionType,
)
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.catalog import RANK_LAST
from app.services.enrichment.category_config import section_label
from app.services.storage import get_object_storage

_PACK_FIELDS = ("slug", "name_zh", "name_en", "city_zh", "city_en", "country")

_LEGACY_SOURCE = "Wikidata/Wikimedia Commons (public data)"


def _has_image_clause():
    """有图过滤:对象至少有一张可展示图(image_key 或 source_url 非空,且非隔离图)。
    供 list_objects 与分类计数复用,让浏览面不显示无图 stub(qid 直达不受影响)。"""
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


# 通用分类法 8 大类(契约§收录策略),全馆共用;奥赛启用前 4 类。
# label 全 6 语(交接 2026-07-03-backend-category-label-i18n):固定小集合,静态表即可;缺译回退 en。
_CATEGORY_LABELS = {
    "painting": {
        "zh": "绘画",
        "zh-hant": "繪畫",
        "en": "Painting",
        "fr": "Peinture",
        "de": "Malerei",
        "es": "Pintura",
        "it": "Dipinti",
        "ko": "회화",
        "ja": "絵画",
        "pl": "Malarstwo",
    },
    "sculpture": {
        "zh": "雕塑",
        "zh-hant": "雕塑",
        "en": "Sculpture",
        "fr": "Sculpture",
        "de": "Skulpturen",
        "es": "Escultura",
        "it": "Sculture",
        "ko": "조각",
        "ja": "彫刻",
        "pl": "Rzeźba",
    },
    "works_on_paper": {
        "zh": "纸上作品",
        "zh-hant": "紙上作品",
        "en": "Works on Paper",
        "fr": "Arts graphiques",
        "de": "Arbeiten auf Papier",
        "es": "Obra sobre papel",
        "it": "Opere su carta",
        "ko": "종이 작품",
        "ja": "紙の作品",
        "pl": "Prace na papierze",
    },
    "photography": {
        "zh": "摄影",
        "zh-hant": "攝影",
        "en": "Photography",
        "fr": "Photographie",
        "de": "Fotografie",
        "es": "Fotografía",
        "it": "Fotografia",
        "ko": "사진",
        "ja": "写真",
        "pl": "Fotografia",
    },
    "decorative_arts": {
        "zh": "装饰艺术",
        "zh-hant": "裝飾藝術",
        "en": "Decorative Arts",
        "fr": "Arts décoratifs",
        "de": "Kunstgewerbe",
        "es": "Artes decorativas",
        "it": "Arti decorative",
        "ko": "장식 미술",
        "ja": "装飾芸術",
        "pl": "Sztuka dekoracyjna",
    },
    "textile": {
        "zh": "纺织",
        "zh-hant": "紡織",
        "en": "Textiles",
        "fr": "Textiles",
        "de": "Textilien",
        "es": "Textiles",
        "it": "Tessuti",
        "ko": "직물",
        "ja": "織物",
        "pl": "Tekstylia",
    },
    "artifact": {
        "zh": "文物器物",
        "zh-hant": "文物器物",
        "en": "Artifacts",
        "fr": "Objets",
        "de": "Artefakte",
        "es": "Artefactos",
        "it": "Reperti",
        "ko": "유물",
        "ja": "工芸品",
        "pl": "Artefakty",
    },
    "manuscript": {
        "zh": "手稿古籍",
        "zh-hant": "手稿古籍",
        "en": "Manuscripts",
        "fr": "Manuscrits",
        "de": "Handschriften",
        "es": "Manuscritos",
        "it": "Manoscritti",
        "ko": "필사본",
        "ja": "写本",
        "pl": "Rękopisy",
    },
    "unknown": {
        "zh": "其他",
        "zh-hant": "其他",
        "en": "Other",
        "fr": "Autre",
        "de": "Sonstiges",
        "es": "Otros",
        "it": "Altro",
        "ko": "기타",
        "ja": "その他",
        "pl": "Inne",
    },
}
_ALL_LABEL = {
    "zh": "全部",
    "zh-hant": "全部",
    "en": "All",
    "fr": "Tout",
    "de": "Alle",
    "es": "Todo",
    "it": "Tutto",
    "ko": "전체",
    "ja": "すべて",
    "pl": "Wszystko",
}


def _category_label(code: str, lang: str) -> str:
    m = _CATEGORY_LABELS.get(code, {})
    return m.get(lang) or m.get("en") or code


def _resolve_name(i18n, language, legacy=None, final=None):
    """多语显示名规则:i18n[lang] → 该语言的 legacy 列(兼容未 i18n 的 stub)→ final(en 兜底,永不空)。
    避开 Joconde 脏格式(legacy 不含 artist_fr)。"""
    return (i18n or {}).get(language) or (legacy or {}).get(language) or final


def _pick(lang: str, zh, en, fr, fallback=""):
    """按语言选值，带回退链。zh→zh/en；fr→fr/en；其它→en/zh。"""
    if lang == "zh":
        return zh or en or fallback
    if lang == "fr":
        return fr or en or fallback
    return en or zh or fallback


def _sized(storage, key, size):
    """image_key 是基础键(images/{qid}/{sort}),按档位拼文件名。size: thumb|large。"""
    return storage.public_url(f"{key}_{size}.jpg")


def _pack_values(pack, source):
    """从证据包取 source 匹配的全部值(不限 tier:存量 pack 富属性为 material)。"""
    return [
        fct.get("value")
        for fct in (pack or {}).get("facts", [])
        if fct.get("source") == source and fct.get("value")
    ]


# 常见材质 → 本地化干净名(按词首关键词命中;未知原样)。ponytail: 覆盖主流画/雕塑材质,缺再加。
_MEDIUM_NORM = {
    "huile": {"zh": "油画", "en": "Oil on canvas", "fr": "Huile sur toile"},
    "oil": {"zh": "油画", "en": "Oil on canvas", "fr": "Huile sur toile"},
    "bronze": {"zh": "青铜", "en": "Bronze", "fr": "Bronze"},
    "marbre": {"zh": "大理石", "en": "Marble", "fr": "Marbre"},
    "aquarelle": {"zh": "水彩", "en": "Watercolour", "fr": "Aquarelle"},
    "pastel": {"zh": "色粉画", "en": "Pastel", "fr": "Pastel"},
    "gouache": {"zh": "水粉", "en": "Gouache", "fr": "Gouache"},
    "fusain": {"zh": "炭笔", "en": "Charcoal", "fr": "Fusain"},
    "plâtre": {"zh": "石膏", "en": "Plaster", "fr": "Plâtre"},
    "salted": {"zh": "盐纸法", "en": "Salted paper", "fr": "Papier salé"},
    "papier salé": {"zh": "盐纸法", "en": "Salted paper", "fr": "Papier salé"},
    "albumen": {"zh": "蛋白印相", "en": "Albumen print", "fr": "Tirage albuminé"},
    "gelatin": {
        "zh": "明胶银盐",
        "en": "Gelatin silver print",
        "fr": "Tirage argentique",
    },
    "encre": {"zh": "墨水", "en": "Ink", "fr": "Encre"},
    "crayon": {"zh": "铅笔", "en": "Pencil", "fr": "Crayon"},
    "terre cuite": {"zh": "陶土", "en": "Terracotta", "fr": "Terre cuite"},
    # 以下为 2026-09 Joconde 回填带来的法语材质(上游 11273 条实测定的词与词序)。
    # ⚠️ 顺序即语义:先命中先返回。改动前先读 _humanize_medium 的注释。
    # "pierre noire" 必须在 "pierre" 之前 —— 它是素描用的黑石笔,不是石头。
    "pierre noire": {"zh": "黑石笔", "en": "Black chalk", "fr": "Pierre noire"},
    "mine de plomb": {"zh": "石墨铅笔", "en": "Graphite", "fr": "Mine de plomb"},
    "terre crue": {"zh": "生土", "en": "Unfired clay", "fr": "Terre crue"},
    "tempera": {"zh": "蛋彩", "en": "Tempera", "fr": "Tempera"},
    "détremp": {"zh": "胶彩", "en": "Distemper", "fr": "Détrempe"},  # détrempe/détrempé
    "fresque": {"zh": "湿壁画", "en": "Fresco", "fr": "Fresque"},
    "lithographie": {"zh": "石版画", "en": "Lithograph", "fr": "Lithographie"},
    "porcelaine": {"zh": "瓷", "en": "Porcelain", "fr": "Porcelaine"},
    "émail": {"zh": "珐琅", "en": "Enamel", "fr": "Émail"},
    "ivoire": {"zh": "象牙", "en": "Ivory", "fr": "Ivoire"},
    "albâtre": {"zh": "雪花石膏", "en": "Alabaster", "fr": "Albâtre"},
    "calcaire": {"zh": "石灰岩", "en": "Limestone", "fr": "Calcaire"},
    "pierre": {"zh": "石", "en": "Stone", "fr": "Pierre"},
    "argent": {"zh": "银", "en": "Silver", "fr": "Argent"},
    "laiton": {"zh": "黄铜", "en": "Brass", "fr": "Laiton"},
    "zinc": {"zh": "锌", "en": "Zinc", "fr": "Zinc"},
    "verre": {"zh": "玻璃", "en": "Glass", "fr": "Verre"},
    "vélin": {"zh": "犊皮纸", "en": "Vellum", "fr": "Vélin"},
    # cire 在 bronze 之后:"fonte à la cire perdue;bronze"(失蜡铸铜)该归青铜而非蜡
    "cire": {"zh": "蜡", "en": "Wax", "fr": "Cire"},
    "noyer": {"zh": "胡桃木", "en": "Walnut", "fr": "Noyer"},
    "bois": {"zh": "木", "en": "Wood", "fr": "Bois"},
    "toile": {"zh": "布面", "en": "Canvas", "fr": "Toile"},
    # 以下补 **英文**(Wikidata P186,优先级高于 attributes 故更常出现在面板上)
    # 与法语长尾。按 prod 全量 11449 条真值定(2026-09-12)。
    # ⚠️ gelatin/albumen/salted 在上面、排在 silver 之前 —— 否则
    # "gelatin silver print"(明胶银盐照片)会被判成「银」。
    "serpentin": {"zh": "蛇纹石", "en": "Serpentinite", "fr": "Serpentinite"},
    "limestone": {"zh": "石灰岩", "en": "Limestone", "fr": "Calcaire"},
    "sandstone": {"zh": "砂岩", "en": "Sandstone", "fr": "Grès"},
    "black chalk": {"zh": "黑石笔", "en": "Black chalk", "fr": "Pierre noire"},
    "cast iron": {"zh": "铸铁", "en": "Cast iron", "fr": "Fonte"},
    "marble": {"zh": "大理石", "en": "Marble", "fr": "Marbre"},
    "alabaster": {"zh": "雪花石膏", "en": "Alabaster", "fr": "Albâtre"},
    "basalt": {"zh": "玄武岩", "en": "Basalt", "fr": "Basalte"},
    "granite": {"zh": "花岗岩", "en": "Granite", "fr": "Granit"},
    "diorite": {"zh": "闪长岩", "en": "Diorite", "fr": "Diorite"},
    "porphyry": {"zh": "斑岩", "en": "Porphyry", "fr": "Porphyre"},
    "quartzite": {"zh": "石英岩", "en": "Quartzite", "fr": "Quartzite"},
    "flint": {"zh": "燧石", "en": "Flint", "fr": "Silex"},
    "terracotta": {"zh": "陶土", "en": "Terracotta", "fr": "Terre cuite"},
    "plaster": {"zh": "石膏", "en": "Plaster", "fr": "Plâtre"},
    "fresco": {"zh": "湿壁画", "en": "Fresco", "fr": "Fresque"},
    "distemper": {"zh": "胶彩", "en": "Distemper", "fr": "Détrempe"},
    "photogravure": {"zh": "照相凹版", "en": "Photogravure", "fr": "Photogravure"},
    "parchment": {"zh": "羊皮纸", "en": "Parchment", "fr": "Parchemin"},
    "ivory": {"zh": "象牙", "en": "Ivory", "fr": "Ivoire"},
    "ormolu": {"zh": "鎏金铜", "en": "Ormolu", "fr": "Bronze doré"},
    "brass": {"zh": "黄铜", "en": "Brass", "fr": "Laiton"},
    "copper": {"zh": "铜", "en": "Copper", "fr": "Cuivre"},
    "silver": {"zh": "银", "en": "Silver", "fr": "Argent"},
    "gold": {"zh": "金", "en": "Gold", "fr": "Or"},
    "lead": {"zh": "铅", "en": "Lead", "fr": "Plomb"},
    "diamond": {"zh": "钻石", "en": "Diamond", "fr": "Diamant"},
    "velvet": {"zh": "天鹅绒", "en": "Velvet", "fr": "Velours"},
    "clay": {"zh": "黏土", "en": "Clay", "fr": "Argile"},
    "ink": {"zh": "墨水", "en": "Ink", "fr": "Encre"},
    # stone 放在 limestone/sandstone 之后是多余的保险:\b 本就不匹配词内的
    # "…stone",但排在后面,以后有人删掉 \b 也不会立刻把石灰岩变成「石」。
    "stone": {"zh": "石", "en": "Stone", "fr": "Pierre"},
    "wood": {"zh": "木", "en": "Wood", "fr": "Bois"},
    "paper": {"zh": "纸", "en": "Paper", "fr": "Papier"},
    # 法语长尾:木材/石材/金属的具体名称
    "chêne": {"zh": "橡木", "en": "Oak", "fr": "Chêne"},
    "peuplier": {"zh": "杨木", "en": "Poplar", "fr": "Peuplier"},
    "érable": {"zh": "枫木", "en": "Maple", "fr": "Érable"},
    "séquoia": {"zh": "红杉木", "en": "Sequoia", "fr": "Séquoia"},
    "orme": {"zh": "榆木", "en": "Elm", "fr": "Orme"},
    "saule": {"zh": "柳木", "en": "Willow", "fr": "Saule"},
    "grès": {"zh": "砂岩", "en": "Sandstone", "fr": "Grès"},
    "cuivre": {"zh": "铜", "en": "Copper", "fr": "Cuivre"},
    "plomb": {"zh": "铅", "en": "Lead", "fr": "Plomb"},
    "alliage": {"zh": "合金", "en": "Alloy", "fr": "Alliage"},
    "stuc": {"zh": "灰泥", "en": "Stucco", "fr": "Stuc"},
    "enduit": {"zh": "灰泥底", "en": "Plaster ground", "fr": "Enduit"},
    "mortier": {"zh": "灰浆", "en": "Mortar", "fr": "Mortier"},
    "plastiline": {"zh": "塑泥", "en": "Plasticine", "fr": "Plastiline"},
    "sanguine": {"zh": "红粉笔", "en": "Sanguine", "fr": "Sanguine"},
    "lavis": {"zh": "淡彩", "en": "Wash", "fr": "Lavis"},
    "plume": {"zh": "羽毛笔", "en": "Pen", "fr": "Plume"},
    "parchemin": {"zh": "羊皮纸", "en": "Parchment", "fr": "Parchemin"},
    "papier": {"zh": "纸", "en": "Paper", "fr": "Papier"},
}
# 有意不收的词:
# - 技法而非材质(bas-relief/haut-relief/modelage/taille/fond d'or/grisaille/
#   galvanoplastie/ronde bosse):收了会把"浮雕"当材质写上展签。
#   不收,串里靠后的真材质自然会命中。
# - "or"(金):上游 114 条命中里绝大多数是 "fond d'or"(金底),收了会把蛋彩画标成「金」。
#   英文 "gold" 没有这个问题(P186 里就是纯金),所以只收英文那个。
# - "paint":\bpaint 会连 "painting" 一起吃掉,而它只值 1 件。


def _humanize_medium(raw, lang):
    """原始材质串(法语 Joconde / 英语 Wikidata P186)→ 本地化干净名;未命中原样。
    词首边界匹配,防 'toile' 误中 'oil'。"""
    if not raw:
        return None
    low = raw.lower()
    for kw, m in _MEDIUM_NORM.items():
        if re.search(rf"\b{kw}", low):
            return m.get(lang) or m.get("en")
    return raw


# 米制单位:全称 mètre(s)/metre(s) 与缩写 "en m 2.08"。\b 保证不吃 "en mm"。
# ⚠️ 只认全称会漏掉绝大多数:上游 104.6 万行里缩写写法 132393 行、全称仅 277 行
# —— 认得出的不到 0.2%。此前 dimensions 几乎全空没人看见,2026-09 回填一铺开
# 就会让卢浮宫素描部门(惯用 "H. en m 0,126")整片显示成 "0.1 × 0.2 cm"。
_METRIC_RE = re.compile(r"\ben\s+m(?:\b|ètres?\b|etres?\b)", re.IGNORECASE)


def _humanize_dimensions(raw):
    """Joconde 尺寸串(如 'en mètres : L. 0,55 ; H. 0,46' / 'H. 208, l. 264.5')→ '宽 × 高 cm'。
    ponytail: 取前两个数 + 米→厘米;格式怪异则原样返回。"""
    if not raw:
        return None
    nums = re.findall(r"\d+(?:[.,]\d+)?", raw)
    if len(nums) < 2:
        return raw
    vals = [float(n.replace(",", ".")) for n in nums[:2]]
    if _METRIC_RE.search(raw):  # 米 → 厘米
        vals = [v * 100 for v in vals]

    def _fmt(x):
        return f"{x:.1f}".rstrip("0").rstrip(".")

    return f"{_fmt(vals[0])} × {_fmt(vals[1])} cm"


@lru_cache(maxsize=1)
def _museum_ranks() -> dict[str, int]:
    """slug → 探索页名次。真相源是 museums.yaml 的 `rank`。

    不进 DB 是有意的:它是纯呈现决策,改一次要配一次迁移 + 一次 prod 写操作,
    而 yaml 改完随 CD 就生效。进程内只解析一次(馆配置不会热变)。
    """
    from app.services.enrichment.catalog import MuseumCatalog
    from app.services.enrichment.factory import CATALOG_PATH

    return {
        slug: cfg.rank for slug, cfg in MuseumCatalog.from_file(CATALOG_PATH).items()
    }


def list_museums(db: Session) -> list[dict]:
    rows = (
        db.query(Museum, func.count(MuseumObject.id).label("cnt"))
        .outerjoin(MuseumObject, MuseumObject.museum_id == Museum.id)
        .group_by(Museum.id)
        # 按 slug 只是兜底次序——真正的排序在下面按 rank 做。别把它当最终顺序:
        # 首条会被探索页拿去上大卡,而字母序意味着哪天上个 `british_museum`
        # 就会无声顶掉卢浮宫的首位。
        .order_by(Museum.slug)
        .all()
    )
    storage = get_object_storage()
    out = []
    for m, cnt in rows:
        row = {f: getattr(m, f) for f in _PACK_FIELDS}
        row["artwork_count"] = cnt
        # 探索页缩略图(spec 2026-07-20 museum-cover-intro-quality,加法):同一行零成本可读
        row["cover_image"] = (
            _sized(storage, m.cover_image_key, "thumb") if m.cover_image_key else None
        )
        out.append(row)
    # DB 里可能有 yaml 没配的馆(手工建的/刚删了配置),给它末位,再按 slug 稳定排。
    ranks = _museum_ranks()
    out.sort(key=lambda r: (ranks.get(r["slug"], RANK_LAST), r["slug"]))
    return out


def get_museum_pack(
    db: Session, slug: str, language: str = "zh", *, artworks: bool = True
) -> dict | None:
    """完整馆包。artworks=False 时省掉藏品数组(仍返回该键为空列表,形状不变)——
    列表页走分页 /objects,不需要全量:卢浮宫 17283 件全塞一个响应 = **5MB / 5.7s**,
    而前端 MuseumDetail 根本不解析 artworks,下载完就扔。缺省 True 保老 App 不变。"""
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return None
    # artworks=False:整段藏品加载全跳过(查询/图/作者/URL 拼装都省),这才是 5.7s 的来源
    objs = (
        (
            db.query(MuseumObject)
            .filter_by(museum_id=m.id)
            .order_by(MuseumObject.popularity.desc())
            .all()
        )
        if artworks
        else []
    )
    obj_ids = [o.id for o in objs]
    # Batch-load all primary images in one query
    images_by_obj: dict[int, ObjectImage] = {}
    if obj_ids:
        for img in (
            db.query(ObjectImage)
            .filter(ObjectImage.object_id.in_(obj_ids), ObjectImage.role == "primary")
            .all()
        ):
            images_by_obj[img.object_id] = img

    # 作者名批量预加载:本地化名的真相源是 Artist.name_i18n(names 写这里,不写
    # MuseumObject.artist_* 列)。此前馆包只读裸列 → 卢浮宫 10041 件作者名在中文
    # 视图全显拉丁文。与详情接口的 _resolve_name 同源(那里早就做对了)。
    artists_by_qid = {}
    aqids = {aq for o in objs if (aq := (o.attributes or {}).get("artist_qid"))}
    if aqids:
        from app.models.artist import Artist

        artists_by_qid = {
            a.qid: a for a in db.query(Artist).filter(Artist.qid.in_(list(aqids)))
        }

    def _artist_name(o, language):
        art = artists_by_qid.get((o.attributes or {}).get("artist_qid"))
        return _resolve_name(
            art.name_i18n if art else None,
            language,
            {
                "zh": (art.name_zh if art else None) or o.artist_zh,
                "en": (art.name_en if art else None) or o.artist_en,
            },
            (art.name_en if art else None) or o.artist_en or o.artist_zh,
        )

    storage = get_object_storage()

    def _resolve_image(obj_id, fallback_src):
        img = images_by_obj.get(obj_id)
        if img and img.image_key:
            return _sized(storage, img.image_key, "thumb")
        return (img.source_url if img else None) or fallback_src

    artworks = [
        {
            "qid": o.qid,
            # title_zh 永不为 null：富化数据常缺中文标题，回退 title_en→qid，
            # 否则前端 `title_zh as String` 强转会崩（馆藏列表整页加载失败）。
            "title_zh": (o.attributes or {}).get("title_i18n", {}).get("zh")
            or o.title_zh
            or o.title_en
            or o.qid,
            # title_en 同样 title_i18n 优先(与上面 title_zh 对称):names(尤其
            # Batch 路径)只回填 attributes.title_i18n、不写列,法语源大馆的 title_en
            # 列多为空——卢浮宫实测 9505/17283 件列空、其中 9497 件 i18n 里其实有
            # 英文名,只读列会让英文用户看到一半藏品标题空白。
            "title_en": (o.attributes or {}).get("title_i18n", {}).get("en")
            or o.title_en,
            # 作者名同样 i18n 优先(真相源 Artist.name_i18n),与 title_* 对称
            "artist_zh": _artist_name(o, "zh"),
            "artist_en": _artist_name(o, "en"),
            "year": o.year,
            "period_zh": o.period_zh,
            "period_en": o.period_en,
            "image": _resolve_image(o.id, None),
            "popularity": o.popularity,
        }
        for o in objs
    ]
    cat_rows = (
        db.query(MuseumObject.category, func.count())
        .filter_by(museum_id=m.id)
        .filter(_has_image_clause())  # 分类计数只算有图件(浏览面)
        .group_by(MuseumObject.category)
        .all()
    )
    total = sum(c for _, c in cat_rows)
    categories = [
        {"code": "all", "label": _ALL_LABEL.get(language, "全部"), "count": total}
    ] + [
        {"code": code, "label": _category_label(code, language), "count": cnt}
        for code, cnt in sorted(cat_rows, key=lambda x: -x[1])
    ]

    # 双数字(加法字段):catalog_count=有图件数, archive_count=总件数。
    # 优先读 museum.stats(Task 7 回写),缺失键现场 count 兜底(保证语义即时正确)。
    stats = m.stats or {}
    archive_count = stats.get("archive_count")
    if archive_count is None:
        archive_count = (
            db.query(func.count(MuseumObject.id)).filter_by(museum_id=m.id).scalar()
        )
    catalog_count = stats.get("catalog_count")
    if catalog_count is None:
        catalog_count = (
            db.query(func.count(MuseumObject.id))
            .filter_by(museum_id=m.id)
            .filter(_has_image_clause())
            .scalar()
        )

    pack = {f: getattr(m, f) for f in _PACK_FIELDS}
    pack.update(
        {
            "qid": m.qid,
            "source": _LEGACY_SOURCE,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            # 独立 COUNT:artworks=False 时列表为空,但件数是门面字段(App 显"17283 件"),
            # 不能从列表长度推(测试 test_pack_skip_artworks_keeps_shape 抓到过)
            "artwork_count": (
                len(artworks)
                if artworks
                else db.query(MuseumObject).filter_by(museum_id=m.id).count()
            ),
            "catalog_count": catalog_count,
            "archive_count": archive_count,
            "categories": categories,
            "artworks": artworks,
            # 博物馆介绍(spec 2026-07-18):按语言解析,缺→en→任一→null;前端 as String? 容错
            "description": (
                (m.description_i18n or {}).get(language)
                or (m.description_i18n or {}).get("en")
                or next(iter((m.description_i18n or {}).values()), None)
            ),
            # 封面(得体性筛选后固化);large 档(hero 大图)
            "cover_image": (
                _sized(storage, m.cover_image_key, "large")
                if m.cover_image_key
                else None
            ),
        }
    )
    return pack


def get_object_content(db: Session, slug: str, qid: str, language: str) -> dict | None:
    obj = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if not obj:
        return None
    # Validate that the object belongs to the museum identified by slug
    museum = db.query(Museum).filter_by(id=obj.museum_id).one_or_none()
    if not museum or museum.slug != slug:
        return None
    mapping = (
        db.query(CategorySection, SectionType)
        .join(SectionType, CategorySection.section_code == SectionType.code)
        .filter(CategorySection.category == obj.category)
        .order_by(CategorySection.sort_order)
        .all()
    )
    bodies = {
        c.section_code: c
        for c in db.query(ObjectContentSection)
        .filter_by(object_id=obj.id, language=language)
        .all()
    }
    storage = get_object_storage()
    tabs = []
    for cs, st in mapping:
        if cs.section_code == "artist":  # artist 段是常驻卡片,不进 tabs
            continue
        row = bodies.get(cs.section_code)
        body = row.body if (row and row.status == "published") else None
        if not (body and body.strip()):
            continue  # 动态:空/未发布模块不进 tabs(料薄优雅降级)
        tabs.append(
            {
                "section_code": cs.section_code,
                "label": section_label(cs.section_code, language),
                "icon": st.icon,
                "body": body,
                # ⚠️ 只给标志位,**绝不下发直链**:内容接口无鉴权,发直链等于
                # 把付费墙拆了(音频 key 做成不可推测也白搭——我们自己发出去)。
                # 前端据此决定显不显示播放按钮,真要听走已加闸的 /audio。
                "has_audio": bool(row and row.audio_key),
            }
        )
    suggested = [
        {"question": q.question, "answer": q.answer, "sort": q.sort}
        for q in db.query(ObjectSuggestedQuestion)
        .filter_by(object_id=obj.id, language=language, status="published")
        .order_by(ObjectSuggestedQuestion.sort)
        .all()
    ]
    attrs = obj.attributes or {}
    images = [
        {
            "url": (
                _sized(storage, i.image_key, "large") if i.image_key else i.source_url
            ),
            "credit": i.credit,
        }
        for i in db.query(ObjectImage)
        .filter(
            ObjectImage.object_id == obj.id,
            ObjectImage.role != "view_quarantine",  # 隔离图不进图集
        )
        .order_by(ObjectImage.sort)
        .all()
        if i.image_key or i.source_url
    ]
    from app.models.artist import Artist

    aqid = attrs.get("artist_qid")
    art = db.query(Artist).filter_by(qid=aqid).first() if aqid else None
    # 作者名唯一解析(问题1a):简介行与作者卡共用 name_i18n,不再用原始 artist_zh/en 列
    resolved_artist = _resolve_name(
        art.name_i18n if art else None,
        language,
        {
            "zh": (art.name_zh if art else None) or obj.artist_zh,
            "en": (art.name_en if art else None) or obj.artist_en,
        },
        (art.name_en if art else None) or obj.artist_en or obj.artist_zh,
    )
    facts = {
        "artist": resolved_artist,
        "date": obj.year,
        # medium 优先证据包干净源(Wikidata P186,多值合并),回退 Joconde medium_fr
        "medium": _humanize_medium(
            ", ".join(_pack_values(obj.evidence_pack, "wikidata:P186"))
            or attrs.get("medium_fr"),
            language,
        ),
        "dimensions": _humanize_dimensions(attrs.get("dimensions")),
        "inventory": obj.inventory_number,
        "location": _pick(language, museum.name_zh, museum.name_en, museum.name_en),
        # provenance/exhibitions/bibliography 移出面板(进证据包材料级,阶段2 用),保形不删键
        "provenance": None,
        "artist_life": None,  # ponytail: 未存作者生平，接 Wikidata 作者源后再补
        "exhibitions": [],
        "bibliography": [],
    }
    guide_row = (
        db.query(ObjectContentSection)
        .filter_by(
            object_id=obj.id,
            language=language,
            section_code="guide",
            status="published",
        )
        .one_or_none()
    )
    default_guide = (
        {
            "body": guide_row.body,
            "has_audio": bool(guide_row.audio_key),
        }
        if guide_row and guide_row.body
        else None
    )
    artist_card = {
        "name": resolved_artist,  # 与简介行同源(问题1a)
        "birth": art.birth if art else None,
        "death": art.death if art else None,
        # 国籍/代表作按 language 本地化(i18n 权威→en 列兜底,不返 null;交接③)
        "nationality": (
            ((art.nationality_i18n or {}).get(language) or art.nationality)
            if art
            else None
        ),
        "notable_works": (
            ((art.notable_works_i18n or {}).get(language) or art.notable_works)
            if art
            else None
        )
        or [],
        "bio": (art.bio or {}).get(language) if art else None,
    }
    guide_body = guide_row.body if guide_row else None
    eff_status = obj.content_status
    if not (guide_body and guide_body.strip()) and not tabs:
        eff_status = "empty"
    from app.services.enrichment.lazy import lock_active

    # 加法字段(2026-07-10):真实段落进度(诚实分数,非假百分比)。
    # expected=guide+该类目深度段(不含 artist 卡);published=已发布的 guide+深度段。
    _expected_deep = sum(1 for cs, _st in mapping if cs.section_code != "artist")
    generation = {
        "published": (1 if default_guide else 0) + len(tabs),
        "expected": 1 + _expected_deep,
    }

    return {
        "qid": qid,
        "category": obj.category,
        "language": language,
        "status": eff_status,
        # 加法字段(2026-07-04):前端三态精确信号——true=懒生成/懒翻译进行中
        "generating": lock_active(obj),
        # 加法字段(2026-07-10):懒生成进度分数(前端显 published/expected 段)
        "generation": generation,
        "title": _resolve_name(
            attrs.get("title_i18n"),
            language,
            {"zh": obj.title_zh, "en": obj.title_en, "fr": attrs.get("title_fr")},
            obj.title_en or obj.title_zh or obj.qid,
        ),
        "images": images,
        "facts": facts,
        "artist": artist_card,
        "tabs": tabs,
        "default_guide": default_guide,
        "suggested_questions": suggested,
    }


def list_objects(
    db: Session,
    slug: str,
    *,
    language: str = "zh",
    category: str | None = None,
    sort: str = "popularity",
    limit: int = 50,
    offset: int = 0,
) -> dict | None:
    """分页藏品列表（供 A2/A3 列表页）。未知馆→None。纯元数据 + content_status。"""
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return None
    q = db.query(MuseumObject).filter_by(museum_id=m.id).filter(_has_image_clause())
    if category and category != "all":
        q = q.filter(MuseumObject.category == category)
    total = q.count()
    q = q.order_by(MuseumObject.popularity.desc())
    objs = q.limit(limit).offset(offset).all()

    obj_ids = [o.id for o in objs]
    images_by_obj: dict = {}
    if obj_ids:
        for img in (
            db.query(ObjectImage)
            .filter(ObjectImage.object_id.in_(obj_ids), ObjectImage.role == "primary")
            .all()
        ):
            images_by_obj[img.object_id] = img
    storage = get_object_storage()

    from app.models.artist import Artist

    artist_qids = {
        (o.attributes or {}).get("artist_qid")
        for o in objs
        if (o.attributes or {}).get("artist_qid")
    }
    artists_by_qid = (
        {a.qid: a for a in db.query(Artist).filter(Artist.qid.in_(artist_qids)).all()}
        if artist_qids
        else {}
    )

    def _thumb(obj_id):
        img = images_by_obj.get(obj_id)
        if img and img.image_key:
            return _sized(storage, img.image_key, "thumb")
        return img.source_url if img else None

    def _title(o):
        a = o.attributes or {}
        return _resolve_name(
            a.get("title_i18n"),
            language,
            {"zh": o.title_zh, "en": o.title_en, "fr": a.get("title_fr")},
            o.title_en or o.title_zh or o.qid,
        )

    def _artist(o):
        art = artists_by_qid.get((o.attributes or {}).get("artist_qid"))
        return (
            _resolve_name(
                art.name_i18n if art else None,
                language,
                {"zh": o.artist_zh, "en": o.artist_en},
                o.artist_en or o.artist_zh,
            )
            or ""
        )

    # content_status 按请求语言解读:对象 ready 但该语言无已发布内容 → empty(待完善),
    # 防"列表看着有、点进去空"(懒翻译入口;契约§content_status)
    lang_ready_ids = (
        {
            oid
            for (oid,) in db.query(ObjectContentSection.object_id)
            .filter(
                ObjectContentSection.object_id.in_(obj_ids),
                ObjectContentSection.language == language,
                ObjectContentSection.status == "published",
                ObjectContentSection.body.isnot(None),
            )
            .distinct()
        }
        if obj_ids
        else set()
    )

    def _status(o):
        if o.content_status == "ready" and o.id not in lang_ready_ids:
            return "empty"
        return o.content_status

    items = [
        {
            "qid": o.qid,
            "title": _title(o),
            "artist": _artist(o),
            "year": o.year,
            "thumbnail": _thumb(o.id),
            "content_status": _status(o),
        }
        for o in objs
    ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}
