# GoMuseum · Métadonnées finales — Français (Google Play)

**状态：草案，未上传，等待用户审核。**
依据 `keyword-research-fr-FR.md`（实测 2026-09-21）。**本文件不是 en-US 的翻译** —— 法语市场的关键词结构与英语**相反**（见下），Title 的差异化词选择因此不同。
字符数为脚本实测值。

---

## 与英文版的核心差异（先读这段）

实测发现：

- FR `reconnaissance œuvre d'art` → **Smartify 排第 1，4,6★，1M+ 下载** ⇒ **识别词在法语已被强在位者占住**。
- FR `audioguide louvre` → **仅 8 个结果**，头部 MUSEUM BUDDY **2,5★**、Orsay 版 **2,0★** ⇒ **这才是法语市场的空位**。

⇒ **法语 Title 放 `Audioguide` 而不是 `Scan`。** 识别能力在法语市场降级为**页面转化卖点**（进简短描述与截图），不作搜索获客词。
这是有证据的市场差异，不是把英文结论翻译一遍。

---

## Titre（上限 30）

| 版本 | 文案 | 字符数 | 关键词 / 定位差异 |
|---|---|---|---|
| **推荐** | `GoMuseum : Audioguide Louvre` | **28/30** | 精确匹配 `audioguide louvre` —— 法语市场**结果最少、在位者最弱**的高意图查询（8 个结果，头部 2,5★）。法语排版规范：冒号前留空格。 |
| 备选 A | `GoMuseum : Guide du Louvre` | 26/30 | 覆盖更宽的 `guide du Louvre` 词根，自然度最高，但放弃 `audioguide` 这个精确匹配优势。 |
| 备选 B | `GoMuseum : Guide Musées Paris` | 29/30 | **不绑定单馆**，用 `Paris` + `musées` 覆盖四馆整体，牺牲 `Louvre` 专名的强意图流量。⚠️ `guide musée paris` 实测被 Civitatis 4,7★、Odyssey 4,2★ 等城市指南和 Paris Musées 官方 App 占据，**优先级低于前两版**。 |

> ❌ **原备选 B `GoMuseum : Scan Louvre & Art` 已作废**，两处原因：
> ① 法语 `Scan` 落在 PDF 扫描器语义区（见 `keyword-research-fr-FR.md` 专节实测）；
> ② 原注写的"仅在 A/B 测试中作为方向对照版使用"是**不可能执行的建议** —— **Play 的标题不能 A/B**，只有描述类字段能测（见 `experiment-and-measurement-plan.md` §1）。这是我自己文档内部的矛盾。
>
> ⇒ **法语标题没有实验兜底，只能靠判断一次定死。** 三个候选里推荐版（`Audioguide Louvre`）是唯一精确匹配法语最弱防守高意图词的。

⚠️ **别写 `Louvres`**（带 s）：那是瓦勒德瓦兹省的市镇，FR 搜索结果里真有 `Ville de Louvres` 这个 App。

---

## Description courte（上限 80，**Play 索引此字段**）

| 版本 | 文案 | 字符数 |
|---|---|---|
| **推荐** | `Scannez une œuvre au Louvre ou à Orsay : ni titre ni numéro, écoutez.` | **69/80** |
| 备选 A（= 既有稿） | `Photographiez une œuvre au Louvre ou à Orsay pour un guide audio instantané.` | 76/80 |
| 备选 B | `Au Louvre ou à Orsay : pointez, GoMuseum identifie l'œuvre et raconte.` | 70/80 |

**为什么改掉既有稿**：既有稿只说做什么；推荐版说的是*为什么需要* —— `ni titre ni numéro` 直接命中真实痛点（馆内多数作品墙上无馆藏号）。同时 `Scannez` 比 `Photographiez` 短且更接近用户搜索用词，腾出的字符用来讲痛点。
**正字法**：`œuvre` 用连字，`à` 带重音 —— 法语用户对正字法错误敏感，且竞品 TourBlink 的法语本地化版本评分（4,3）高于英文版（3.7），说明本地化质量有回报。

---

## Description complète（上限 4000，**Play 全文索引**）

```
Au Louvre, la plupart des œuvres ne portent aucun numéro au mur et le cartel est en français. GoMuseum vous dit ce que vous regardez : pointez, c'est tout.

Les réflexes habituels ne fonctionnent pas ici : impossible de taper un numéro sur un audioguide loué, impossible de chercher un titre que vous ne connaissez pas. GoMuseum supprime cette étape — pointez votre appareil photo vers le tableau, la sculpture ou l'objet devant vous, et l'application identifie l'œuvre et raconte son histoire. Elle couvre le Louvre, le Musée d'Orsay, le Musée de l'Orangerie et le Petit Palais — quatre musées parisiens, une seule application.

SCANNEZ & ÉCOUTEZ
• Pointez votre appareil photo — GoMuseum reconnaît l'œuvre et l'identifie en quelques secondes
• Guides écrits approfondis pour des milliers d'œuvres dans les quatre collections — fondés sur des sources vérifiées, jamais inventés
• Audio narré, pour écouter tout en regardant
• Une œuvre pas encore rédigée ? Scannez-la quand même : GoMuseum la documente et rédige son guide sur place
• Questions fréquentes rédigées et vérifiées à l'avance pour de nombreuses œuvres — ce n'est pas un chatbot en direct

EXPLOREZ LIBREMENT
• Recherchez une collection par titre d'œuvre ou nom d'artiste
• Aucun compte requis — commencez en tant qu'invité
• Vos 5 premières reconnaissances et votre premier guide audio sont gratuits
• Guides écrits disponibles en 10 langues : français, anglais, allemand, espagnol, italien, polonais, japonais, coréen, chinois simplifié et chinois traditionnel

NI LOCATION, NI FILE D'ATTENTE
Plus besoin de passer au comptoir des audioguides ni de laisser une caution. GoMuseum reste dans votre poche et vous suit dans la salle, ou devant le tableau, qui attire votre regard — au lieu d'un parcours choisi par quelqu'un d'autre.

PASS VILLE PARIS
Un seul pass débloque scans et audio illimités au Louvre, à Orsay, à l'Orangerie et au Petit Palais pour toute la durée de votre visite. Un paiement unique, pas un abonnement.

CONFIDENTIALITÉ
Vos photos ne servent qu'à identifier l'œuvre devant vous. Nous ne stockons ni ne téléversons jamais vos images originales.

GoMuseum est un guide indépendant. L'application n'est ni affiliée, ni approuvée, ni liée au Musée du Louvre, au Musée d'Orsay, au Musée de l'Orangerie ou au Petit Palais.

Remarque : GoMuseum nécessite une connexion internet pour reconnaître les œuvres et diffuser les guides audio.
```

**字符数：2414/4000（60%）**（既有稿实测 1413/4000，35%）

### 较既有稿的实质变化

与英文版同源的修正（10 语归位、痛点段、**按需生成那句**、非实时对话、一次性付费、独立声明扩写、联网提示）全部同步落实。
⚠️ 其中"覆盖量失实"一项**已撤销**：懒生成约 20 秒补齐，`des milliers d'œuvres` 成立，详见 `current-listing-audit.md` A1。**法语特有的处置**：

| # | 处置 | 依据 |
|---|---|---|
| F1 | Title 用 `Audioguide` 而非 `Scan` | FR 识别词被 Smartify 占（4,6★），`audioguide louvre` 才是空位 |
| F2 | 正字法完整：`œuvre` 连字、`cartel`（法语馆内标准用词，不是 `étiquette`）、`à` 重音 | 竞品本地化质量与评分正相关（TourBlink FR 4,3 vs EN 3.7） |
| F3 | `tableau` 与 `œuvre` 两词并用 | 法语用户两词都搜（实测 `Estimation Tableau & Peinture` 在位） |
| F4 | `Petit Palais` 用短名 | 全名 `Petit Palais, musée des beaux-arts de la ville de Paris`；⚠️ **绝不可写 `musée du Petit Palais`** —— 那是阿维尼翁的馆 |
| F5 | 独立声明措辞用 `ni affiliée, ni approuvée, ni liée` | Petit Palais 属 Paris Musées 体系，FR 市场官方 App 矩阵真实存在，此处需要比英文更明确 |

---

## Couverture des mots-clés

| Mot-clé | Titre | Desc. courte | Desc. complète | 覆盖 |
|---|---|---|---|---|
| Louvre | ✓ | ✓ | ✓（多次） | 全覆盖 |
| **audioguide / audioguides** | ✓ | | ✓ | Titre + Complète |
| Orsay | | ✓ | ✓ | Courte + Complète |
| **scan / scannez** | **✗**（刻意） | ✓ | ✓（多次） | Courte + Complète |
| œuvre(s) | | ✓ | ✓（多次） | 全覆盖 |
| guide(s) | （含于 audioguide） | | ✓（多次） | Complète |
| musée(s) | | | ✓（多次） | Complète |
| reconnaissance / reconnaît | | | ✓ | Complète |
| tableau / sculpture | | | ✓ | Complète |
| Orangerie / Petit Palais | | | ✓ | Complète |

## Avant / Après

| Champ | Brouillon existant | Recommandation | 变化 |
|---|---|---|---|
| Titre | `GoMuseum`（8/30） | `GoMuseum : Audioguide Louvre`（28/30） | 零关键词 → 精确匹配法语市场最弱防守的高意图词 |
| Desc. courte | 76/80 | 69/80 | 从"做什么"改为"为什么需要"，且更短 |
| Desc. complète | 1413/4000（35%） | 2414/4000（60%） | 同英文版修正 + 5 项法语特有处置 |
