// screens-final.jsx — GoMuseum 定稿：暖纸手册 Catalogue 风格 · 全部 6 页
// 首页 = B 上半 + A 下半（横滑卡片）；讲解页 = B 上半 + A 下半（TTS+正文+AI 问答）
// 导航栏 = 中央大识别按钮 GMNavScan

const FIN = GM_THEMES.B;

const FIN_P1 =
  '1888 年秋，梵高在阿尔的「黄房子」里画下了自己的卧室。他刻意压平了透视，用大块纯色铺陈床、椅与墙面——蓝紫的墙、柠檬黄的床架，让整个房间微微向观者倾倒。';
const FIN_P2 =
  '留意床尾的衣钩与右墙的两幅小肖像：那是梵高对友人到访的期待。此版本是他在圣雷米疗养院凭记忆重绘的第二版，用色更沉，也更安静。';

// 菱形分隔 ◆
function FinDiamond({ w = 130, t = FIN }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: w, flexShrink: 0 }}>
      <div style={{ flex: 1, height: 1, background: t.faint }}></div>
      <div
        style={{
          width: 4.5,
          height: 4.5,
          background: t.accent,
          transform: 'rotate(45deg)',
          flexShrink: 0,
        }}
      ></div>
      <div style={{ flex: 1, height: 1, background: t.faint }}></div>
    </div>
  );
}

// 目录编号小节头：01 ── 标题 ──── 备注
function FinSectionHead({ n, label, note, style, t = FIN }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, ...style }}>
      <span
        style={{
          fontFamily: t.serif,
          fontSize: 13,
          color: t.accent,
          fontWeight: 700,
          letterSpacing: 2,
        }}
      >
        {n}
      </span>
      <span style={{ fontSize: 12, letterSpacing: 3, color: t.ink, fontWeight: 600 }}>{label}</span>
      <div style={{ flex: 1, height: 1, background: t.line }}></div>
      {note && <span style={{ fontSize: 11.5, color: t.sub }}>{note}</span>}
    </div>
  );
}

// ───────────────────────── 首页 ─────────────────────────
function FinalHome({ t = FIN }) {
  return (
    <GMScreen t={t}>
      <div
        style={{
          flex: 1,
          padding: '14px 0 0',
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0,
          overflow: 'hidden',
        }}
      >
        {/* 顶栏：左 城市 · 天气 ｜ 右 通知铃铛 */}
        <div style={{ display: 'flex', alignItems: 'center', padding: '0 20px', marginBottom: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <GMIcon name="pin" size={16} color={t.accent} sw={1.8} />
            <span style={{ fontFamily: t.serif, fontSize: 16, fontWeight: 700, letterSpacing: 1 }}>
              巴黎
            </span>
            <GMIcon name="chevD" size={15} color={t.faint} sw={1.8} />
            <div style={{ width: 1, height: 14, background: t.line, margin: '0 4px' }}></div>
            <GMIcon name="cloudSun" size={18} color={t.accent} sw={1.6} />
            <span style={{ fontFamily: t.serif, fontSize: 15, fontWeight: 700 }}>18°</span>
            <span style={{ fontSize: 11, color: t.sub }}>多云</span>
          </div>
          <span style={{ flex: 1 }}></span>
          <div
            style={{
              position: 'relative',
              width: 34,
              height: 34,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <GMIcon name="mail" size={20} color={t.ink} sw={1.7} />
            <div
              style={{
                position: 'absolute',
                top: 5,
                right: 6,
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: t.accent,
                border: `1.5px solid ${t.bg}`,
              }}
            ></div>
          </div>
        </div>

        {/* 刊头 */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div
            style={{
              fontFamily: t.serif,
              fontSize: 13,
              letterSpacing: 7,
              fontWeight: 700,
              paddingLeft: 7,
            }}
          >
            GOMUSEUM
          </div>
          <div style={{ marginTop: 9 }}>
            <FinDiamond t={t} w={150} />
          </div>
          <div style={{ marginTop: 9, fontSize: 11, letterSpacing: 3, color: t.sub }}>
            随身博物馆导览手册
          </div>
        </div>

        <h1
          style={{
            margin: '22px 0 0',
            fontFamily: t.serif,
            fontWeight: 700,
            textAlign: 'center',
            fontSize: 27,
            lineHeight: 1.55,
          }}
        >
          走近一件作品，
          <br />
          听懂它的故事。
        </h1>

        {/* 门票式主 CTA */}
        <div
          style={{
            margin: '20px 26px 0',
            background: t.ctaBg,
            color: t.ctaInk,
            borderRadius: 4,
            padding: 7,
          }}
        >
          <div
            style={{
              border: `1px dashed ${t.ctaDash}`,
              borderRadius: 2,
              padding: '13px 12px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 12,
            }}
          >
            <GMIcon name="camera" size={24} color={t.ctaInk} />
            <div style={{ fontFamily: t.serif, fontSize: 18, fontWeight: 600, letterSpacing: 2 }}>
              拍照识别讲解
            </div>
            <GMIcon name="arrowR" size={18} color={t.ctaDim} />
          </div>
        </div>
        <div style={{ marginTop: 10, textAlign: 'center', fontSize: 12, color: t.sub }}>
          免费识别还剩 <span style={{ color: t.accent, fontWeight: 600 }}>8</span> 次 · 升级畅听全馆
        </div>

        {/* 01 附近博物馆 — 横滑卡片（A 下半结构 × B 质感） */}
        <FinSectionHead
          t={t}
          n="01"
          label="附近博物馆"
          note="查看全部 →"
          style={{ margin: '24px 26px 0' }}
        />
        <div
          style={{
            marginTop: 14,
            display: 'flex',
            gap: 14,
            overflow: 'hidden',
            flex: 1,
            minHeight: 0,
            paddingLeft: 26,
          }}
        >
          {/* 卡片 1 · 奥赛 */}
          <div
            style={{
              width: 268,
              flexShrink: 0,
              background: t.surface,
              border: `1px solid ${t.line}`,
              alignSelf: 'flex-start',
            }}
          >
            <div style={{ padding: '9px 9px 0' }}>
              <GMImg art={GM_ART.orsayHall} h={132} style={{ border: `1px solid ${t.line}` }} />
            </div>
            <div style={{ padding: '12px 14px 14px' }}>
              <div style={{ display: 'flex', alignItems: 'baseline' }}>
                <span style={{ fontFamily: t.serif, fontSize: 17, fontWeight: 600 }}>
                  奥赛博物馆
                </span>
                <span style={{ flex: 1 }}></span>
                <span style={{ fontSize: 11.5, color: t.accent, fontWeight: 600 }}>开放中</span>
              </div>
              <div style={{ fontSize: 12, color: t.sub, marginTop: 5 }}>
                至 21:45 · 0.8 km · €16
              </div>
              <GMHairline t={t} style={{ margin: '11px 0' }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                <div style={{ display: 'flex', gap: 6 }}>
                  <GMImg
                    art={GM_ART.rhone}
                    w={36}
                    h={36}
                    style={{ border: `2px solid ${t.surface}`, outline: `1px solid ${t.line}` }}
                  />
                  <GMImg
                    art={GM_ART.self1889}
                    w={36}
                    h={36}
                    style={{ border: `2px solid ${t.surface}`, outline: `1px solid ${t.line}` }}
                  />
                  <GMImg
                    art={GM_ART.bedroom}
                    w={36}
                    h={36}
                    style={{ border: `2px solid ${t.surface}`, outline: `1px solid ${t.line}` }}
                  />
                </div>
                <span style={{ fontSize: 11, color: t.sub, lineHeight: 1.5 }}>
                  馆藏 Top 3<br />
                  星夜 · 自画像 · 卧室
                </span>
              </div>
            </div>
          </div>
          {/* 卡片 2 · 橘园（露出一半提示横滑） */}
          <div
            style={{
              width: 268,
              flexShrink: 0,
              background: t.surface,
              border: `1px solid ${t.line}`,
              alignSelf: 'flex-start',
            }}
          >
            <div style={{ padding: '9px 9px 0' }}>
              <GMImg art={GM_ART.plain} h={132} style={{ border: `1px solid ${t.line}` }} />
            </div>
            <div style={{ padding: '12px 14px 14px' }}>
              <div style={{ fontFamily: t.serif, fontSize: 17, fontWeight: 600 }}>橘园美术馆</div>
              <div style={{ fontSize: 12, color: t.sub, marginTop: 5 }}>
                至 18:00 · 1.6 km · €12
              </div>
            </div>
          </div>
        </div>
        {/* 横滑指示点 */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: 6, padding: '10px 0 12px' }}>
          <div style={{ width: 16, height: 4, borderRadius: 2, background: t.accent }}></div>
          <div style={{ width: 4, height: 4, borderRadius: 2, background: t.faint }}></div>
          <div style={{ width: 4, height: 4, borderRadius: 2, background: t.faint }}></div>
        </div>
      </div>
      <GMNavScan t={t} active="首页" />
    </GMScreen>
  );
}

// ───────────────────────── 登录页 ─────────────────────────
function FinalLogin({ t = FIN }) {
  return (
    <GMScreen t={t}>
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          padding: '0 28px 24px',
          overflowY: 'auto',
          minHeight: 0,
        }}
      >
        {/* 品牌区 — 上方留白约 12% 屏高 */}
        <div
          style={{
            paddingTop: 52,
            paddingBottom: 38,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
          }}
        >
          <div
            style={{
              fontFamily: t.serif,
              fontSize: 27,
              fontWeight: 900,
              letterSpacing: 9,
              paddingLeft: 9,
            }}
          >
            GOMUSEUM
          </div>
          <div style={{ margin: '11px 0' }}>
            <FinDiamond t={t} w={50} />
          </div>
          <div style={{ fontSize: 13, letterSpacing: 4, color: t.sub }}>随身博物馆导览手册</div>
        </div>

        {/* 输入框 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
          {['邮箱', '密码'].map((ph) => (
            <div
              key={ph}
              style={{
                height: 58,
                background: t.surface,
                border: `1px solid ${t.line}`,
                display: 'flex',
                alignItems: 'center',
                padding: '0 18px',
              }}
            >
              <span style={{ fontSize: 15.5, color: t.faint }}>{ph}</span>
            </div>
          ))}
        </div>

        {/* 登录按钮 — 门票式（与全站 CTA 一致） */}
        <div style={{ marginTop: 18, background: t.ctaBg, padding: 7 }}>
          <div
            style={{
              border: `1px dashed ${t.ctaDash}`,
              height: 52,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 12,
            }}
          >
            <GMIcon name="ticket" size={19} color={t.ctaInk} />
            <span
              style={{
                fontFamily: t.serif,
                fontSize: 19,
                fontWeight: 700,
                letterSpacing: 7,
                color: t.ctaInk,
              }}
            >
              登　录
            </span>
          </div>
        </div>

        {/* 注册链接 */}
        <div
          style={{
            textAlign: 'center',
            marginTop: 18,
            fontSize: 14.5,
            color: t.accent,
            fontWeight: 500,
          }}
        >
          还没有账号？注册
        </div>

        {/* 第三方登录分隔 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 22 }}>
          <div style={{ flex: 1, height: 1, background: t.line }}></div>
          <span style={{ fontSize: 12.5, color: t.sub, whiteSpace: 'nowrap' }}>
            或使用以下方式登录
          </span>
          <div style={{ flex: 1, height: 1, background: t.line }}></div>
        </div>

        {/* Google / Apple */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 11, marginTop: 18 }}>
          {['使用 Google 登录', '使用 Apple 登录'].map((label) => (
            <div
              key={label}
              style={{
                height: 58,
                background: t.surface,
                border: `1px solid ${t.line}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <span style={{ fontFamily: t.serif, fontSize: 15.5, color: t.ink }}>{label}</span>
            </div>
          ))}
        </div>

        {/* "或" 简单分隔 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 18 }}>
          <div style={{ flex: 1, height: 1, background: t.line }}></div>
          <span style={{ fontSize: 13, color: t.sub }}>或</span>
          <div style={{ flex: 1, height: 1, background: t.line }}></div>
        </div>

        {/* 游客登录 */}
        <div
          style={{
            marginTop: 18,
            height: 58,
            background: t.chipBg,
            border: `1px solid ${t.line}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <span style={{ fontFamily: t.serif, fontSize: 16.5, fontWeight: 700, color: t.ink }}>
            游客登录
          </span>
        </div>
      </div>
    </GMScreen>
  );
}

function FinalCollection({ t = FIN, loaded = false }) {
  // categories 来自 GET /museums/{slug} → categories:[{code,label,count}]
  const categories = [
    { code: 'all', label: '全部', count: 347 },
    { code: 'painting', label: '绘画', count: 186 },
    { code: 'sculpture', label: '雕塑', count: 64 },
    { code: 'photo', label: '摄影', count: 38 },
    { code: 'decorative', label: '装饰艺术', count: 59 },
  ];

  // items 来自 GET /museums/{slug}/objects?category=all&sort=popularity&limit=50&offset=0
  // → { items:[{id,thumbnail,title,author}], total, limit, offset }
  // 缩略图缺失 → 占位图；字段缺失 → 空字符串
  const items = [
    { art: GM_ART.bedroom, title: '在阿尔勒的卧室', author: '文森特·梵高' },
    { art: GM_ART.self1889, title: '自画像', author: '文森特·梵高' },
    { art: GM_ART.rhone, title: '罗纳河上的星夜', author: '文森特·梵高' },
    { art: GM_ART.crows, title: '麦田群鸦', author: '文森特·梵高' },
    { art: GM_ART.thunder, title: '雷雨云下的麦田', author: '文森特·梵高' },
    { art: GM_ART.plain, title: '奥维尔平原', author: '文森特·梵高' },
    { art: GM_ART.self1887, title: '自画像（1887）', author: '文森特·梵高' },
    { art: null, title: null, author: null }, // ← 缺字段容错示例
  ];

  const CardImg = ({ art }) => {
    if (art?.src) {
      return (
        <img
          src={art.src}
          alt=""
          style={{
            width: '100%',
            height: 116,
            objectFit: 'cover',
            display: 'block',
            border: `1px solid ${t.line}`,
          }}
        />
      );
    }
    return (
      <div
        style={{
          width: '100%',
          height: 116,
          background: t.chipBg,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          border: `1px solid ${t.line}`,
        }}
      >
        <GMIcon name="photo" size={28} color={t.faint} />
      </div>
    );
  };

  return (
    <GMScreen t={t}>
      {/* 顶栏 */}
      <div
        style={{
          padding: '12px 18px 10px',
          display: 'flex',
          alignItems: 'center',
          flexShrink: 0,
        }}
      >
        <GMIcon name="back" size={20} color={t.ink} />
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 2,
          }}
        >
          <span style={{ fontFamily: t.serif, fontSize: 16, fontWeight: 700, letterSpacing: 0.5 }}>
            奥赛博物馆
          </span>
          <span style={{ fontSize: 10, color: t.sub, letterSpacing: 1 }}>347 件收录藏品</span>
        </div>
        <GMIcon name="search" size={20} color={t.ink} />
      </div>

      {/* 分类 Tab — 横向可滑，数据来自 API */}
      <div
        style={{
          display: 'flex',
          overflow: 'hidden',
          flexShrink: 0,
          borderTop: `1px solid ${t.line}`,
          borderBottom: `1.5px solid ${t.line}`,
        }}
      >
        {categories.map((c, i) => {
          const on = i === 0;
          return (
            <div
              key={c.code}
              style={{
                padding: '8px 15px 6px',
                flexShrink: 0,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                borderBottom: on ? `2.5px solid ${t.accent}` : '2.5px solid transparent',
                marginBottom: -1.5,
                gap: 2,
              }}
            >
              <span
                style={{
                  fontFamily: t.serif,
                  fontSize: 13,
                  fontWeight: on ? 700 : 400,
                  color: on ? t.accentDeep : t.sub,
                }}
              >
                {c.label}
              </span>
              <span style={{ fontSize: 9.5, color: t.faint }}>{c.count}</span>
            </div>
          );
        })}
      </div>

      {/* 2 列网格 + 无限滚动 */}
      <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '12px 14px 0' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          {items.map((item, i) => (
            <div key={i} style={{ background: t.surface, border: `1px solid ${t.line}` }}>
              <div style={{ padding: '6px 6px 0' }}>
                <CardImg art={item.art} />
              </div>
              <div style={{ padding: '7px 9px 10px' }}>
                <div
                  style={{
                    fontFamily: t.serif,
                    fontSize: 12.5,
                    fontWeight: 600,
                    lineHeight: 1.4,
                    color: t.ink,
                    overflow: 'hidden',
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                  }}
                >
                  {item.title || '未命名'}
                </div>
                <div style={{ fontSize: 10.5, color: t.sub, marginTop: 3 }}>
                  {item.author || '\u00a0'}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* 底部状态 — 加载中 / 已全部加载 */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            padding: '22px 0 18px',
            gap: 8,
          }}
        >
          {loaded ? (
            <>
              <FinDiamond t={t} w={90} />
              <span style={{ fontSize: 11.5, color: t.faint, letterSpacing: 1 }}>
                已全部加载 · 共 347 件
              </span>
            </>
          ) : (
            <>
              <div
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: '50%',
                  border: `2.5px solid ${t.line}`,
                  borderTopColor: t.accent,
                }}
              ></div>
              <span style={{ fontSize: 11.5, color: t.faint }}>正在加载 · 已显示 8 / 347</span>
            </>
          )}
        </div>
      </div>

      <GMNavScan t={t} active="探索" />
    </GMScreen>
  );
}

function FinalGuide({ t = FIN }) {
  // 数据契约 images[]: { art, credit }；缺省时用占位图，不崩
  const artwork = {
    title: '在阿尔勒的卧室',
    titleOrig: 'La Chambre à Arles',
    images: [
      { art: GM_ART.bedroom, credit: 'Wikimedia Commons · 公有领域' },
      { art: GM_ART.self1889, credit: 'Wikimedia Commons · 公有领域' },
    ],
  };
  const hero = artwork.images?.[0] ?? null;
  const tabs = ['介绍', '作者', '背景', '故事'];

  return (
    <GMScreen t={t}>
      {/* 顶栏 */}
      <div
        style={{ padding: '12px 18px 8px', display: 'flex', alignItems: 'center', flexShrink: 0 }}
      >
        <GMIcon name="back" size={20} color={t.ink} />
        <span
          style={{ flex: 1, textAlign: 'center', fontSize: 11, letterSpacing: 3, color: t.sub }}
        >
          语音导览 · 第 3 件
        </span>
        <GMIcon name="star" size={20} color={t.accent} />
      </div>

      {/* 可滚动主体（hero 在内，随手势折叠） */}
      <div style={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
        {/* ── Hero 大图：全出血，约屏幕高 1/3，无装裱边框 ── */}
        <div style={{ position: 'relative', height: 286, overflow: 'hidden', flexShrink: 0 }}>
          {hero ? (
            <img
              src={hero.art.src}
              alt={artwork.title}
              style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
            />
          ) : (
            <div
              style={{
                width: '100%',
                height: '100%',
                background: t.chipBg,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <GMIcon name="photo" size={40} color={t.faint} />
            </div>
          )}
          {/* 底部渐变遮罩 + 标题叠加 */}
          <div
            style={{
              position: 'absolute',
              inset: 0,
              background: 'linear-gradient(to bottom, rgba(0,0,0,0) 36%, rgba(0,0,0,0.68) 100%)',
            }}
          ></div>
          <div
            style={{ position: 'absolute', bottom: 0, left: 0, right: 0, padding: '0 20px 14px' }}
          >
            <h1
              style={{
                margin: 0,
                fontFamily: t.serif,
                fontSize: 22,
                fontWeight: 700,
                color: '#F6F1E4',
                letterSpacing: 0.5,
                lineHeight: 1.3,
                textShadow: '0 1px 6px rgba(0,0,0,0.35)',
              }}
            >
              {artwork.title}
            </h1>
            <div
              style={{
                fontSize: 12,
                color: 'rgba(246,241,228,0.72)',
                marginTop: 3,
                fontStyle: 'italic',
              }}
            >
              {artwork.titleOrig}
            </div>
          </div>
          {/* 版权署名（hero 态淡显） */}
          {hero?.credit && (
            <div
              style={{
                position: 'absolute',
                bottom: 6,
                right: 10,
                fontSize: 9,
                color: 'rgba(246,241,228,0.38)',
                letterSpacing: 0.2,
              }}
            >
              {hero.credit}
            </div>
          )}
          {/* 多图指示点 */}
          {artwork.images.length > 1 && (
            <div
              style={{
                position: 'absolute',
                top: 12,
                right: 14,
                display: 'flex',
                gap: 5,
                alignItems: 'center',
              }}
            >
              {artwork.images.map((_, i) => (
                <div
                  key={i}
                  style={{
                    width: i === 0 ? 16 : 6,
                    height: 5,
                    borderRadius: 3,
                    background: i === 0 ? 'rgba(246,241,228,0.9)' : 'rgba(246,241,228,0.32)',
                  }}
                ></div>
              ))}
            </div>
          )}
        </div>

        {/* 内容区 */}
        <div style={{ padding: '0 20px' }}>
          {/* 流式墙签（始终可见） */}
          <div style={{ padding: '10px 0', borderBottom: `1px solid ${t.line}` }}>
            <div style={{ fontSize: 12.5, color: t.sub, lineHeight: 1.6 }}>
              文森特·梵高 · 1889 · 布面油画 · 72 × 90 cm
            </div>
          </div>

          {/* ▸ 作品信息（默认收起） */}
          <div style={{ borderBottom: `1px solid ${t.line}` }}>
            <div style={{ display: 'flex', alignItems: 'center', padding: '9px 0', gap: 9 }}>
              <span style={{ fontSize: 11, color: t.accent, fontWeight: 900, lineHeight: 1 }}>
                ▸
              </span>
              <span
                style={{
                  fontFamily: t.serif,
                  fontSize: 13.5,
                  fontWeight: 700,
                  letterSpacing: 0.5,
                  color: t.ink,
                }}
              >
                作品信息
              </span>
              <div style={{ flex: 1, height: 1, background: t.line }}></div>
              <span style={{ fontSize: 10.5, color: t.faint }}>编号 · 来源 · 展览 · 文献</span>
            </div>
          </div>

          {/* Tab 栏 */}
          <div style={{ display: 'flex', marginTop: 2, borderBottom: `1.5px solid ${t.line}` }}>
            {tabs.map((tab, i) => {
              const on = i === 0;
              return (
                <div
                  key={tab}
                  style={{
                    flex: 1,
                    textAlign: 'center',
                    padding: '10px 0',
                    fontSize: 12.5,
                    fontFamily: t.serif,
                    fontWeight: on ? 700 : 400,
                    color: on ? t.accentDeep : t.sub,
                    borderBottom: on ? `2.5px solid ${t.accent}` : '2.5px solid transparent',
                    letterSpacing: 0.5,
                    marginBottom: -1.5,
                  }}
                >
                  {tab}
                </div>
              );
            })}
          </div>

          {/* TTS 播放器 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 13 }}>
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: '50%',
                background: t.ctaBg,
                flexShrink: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <GMIcon name="pause" size={17} color={t.ctaInk} sw={2} />
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ position: 'relative', height: 2, background: t.line, borderRadius: 2 }}>
                <div
                  style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    bottom: 0,
                    width: '34%',
                    background: t.accent,
                  }}
                ></div>
                <div
                  style={{
                    position: 'absolute',
                    left: '34%',
                    top: -3.5,
                    width: 9,
                    height: 9,
                    borderRadius: '50%',
                    background: t.accentDeep,
                  }}
                ></div>
              </div>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  marginTop: 6,
                  fontSize: 11,
                  color: t.sub,
                }}
              >
                <span>1:24</span>
                <span>4:08</span>
              </div>
            </div>
            <div
              style={{
                padding: '4px 9px',
                border: `1px solid ${t.line}`,
                fontSize: 11,
                color: t.sub,
                background: t.surface,
                flexShrink: 0,
              }}
            >
              1.0×
            </div>
          </div>

          <GMHairline t={t} style={{ marginTop: 11 }} />

          {/* 讲解正文 */}
          <p
            style={{
              margin: '12px 0 0',
              fontSize: 13.5,
              lineHeight: 1.9,
              color: t.ink,
              textAlign: 'justify',
            }}
          >
            {FIN_P1}
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 12 }}>
            <span
              style={{ fontFamily: t.serif, fontSize: 13, fontWeight: 700, color: t.accentDeep }}
            >
              看点
            </span>
            <div style={{ flex: 1, height: 1, background: t.line }}></div>
          </div>
          <p
            style={{
              margin: '9px 0 20px',
              fontSize: 13.5,
              lineHeight: 1.9,
              color: t.ink,
              textAlign: 'justify',
            }}
          >
            {FIN_P2}
          </p>
        </div>
      </div>

      {/* AI 问答 — 固定底栏 */}
      <div
        style={{
          flexShrink: 0,
          padding: '0 20px 13px',
          borderTop: `1px solid ${t.line}`,
          background: t.bg,
        }}
      >
        <div
          style={{ display: 'flex', gap: 8, paddingTop: 9, marginBottom: 8, overflow: 'hidden' }}
        >
          {['为什么透视是歪的？', '他住了多久？'].map((q) => (
            <div
              key={q}
              style={{
                padding: '6px 12px',
                background: t.chipBg,
                fontSize: 11.5,
                color: t.ink,
                flexShrink: 0,
              }}
            >
              {q}
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <div
            style={{
              flex: 1,
              height: 42,
              border: `1px solid ${t.line}`,
              background: t.surface,
              display: 'flex',
              alignItems: 'center',
              padding: '0 16px',
              fontSize: 13,
              color: t.faint,
            }}
          >
            问问这幅画……
          </div>
          <div
            style={{
              width: 42,
              height: 42,
              borderRadius: '50%',
              background: t.ctaBg,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <GMIcon name="mic" size={18} color={t.ctaInk} />
          </div>
        </div>
      </div>
    </GMScreen>
  );
}

// ───────────────────────── 讲解页 · AI 聊天面板展开态 ─────────────────────────
function FinalGuideChat({ t = FIN }) {
  const PANEL_H = 695; // ~78% of 892

  // 对话内容
  const A1 =
    '梵高刻意打破了文艺复兴以来的线性透视法则。他将地板与家具的延伸线都微微向观者倾斜，制造出房间"向你倾倒"的感觉——这既是他压抑情绪的投射，也是他有意追求的纯粹色彩表达。';
  const chips2 = ['还画了几个版本？', '为什么用这些颜色？', '梵高住在那里多久？'];

  const Bubble = ({ who, text, streaming, source }) => {
    const isUser = who === 'user';
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: isUser ? 'flex-end' : 'flex-start',
          marginBottom: streaming ? 10 : 4,
        }}
      >
        <div
          style={{
            maxWidth: '84%',
            padding: '10px 14px',
            background: isUser ? t.ctaBg : t.surface,
            border: isUser ? 'none' : `1px solid ${t.line}`,
            color: isUser ? t.ctaInk : t.ink,
            fontSize: 13.5,
            lineHeight: 1.8,
          }}
        >
          {streaming ? (
            <span style={{ letterSpacing: 4, color: t.faint, fontSize: 17 }}>···</span>
          ) : (
            text
          )}
        </div>
        {/* 助手消息底部：朗读 + 来源 */}
        {!isUser && !streaming && (
          <div
            style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 6, paddingLeft: 2 }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 5,
                padding: '4px 10px',
                border: `1px solid ${t.line}`,
                background: t.surface,
              }}
            >
              <GMIcon name="volume" size={13} color={t.accent} sw={1.6} />
              <span style={{ fontSize: 11, color: t.accent, letterSpacing: 0.5 }}>朗读</span>
            </div>
            {source && <span style={{ fontSize: 10.5, color: t.faint }}>来源：{source}</span>}
          </div>
        )}
      </div>
    );
  };

  return (
    <div
      style={{
        height: '100%',
        position: 'relative',
        background: '#0A0806',
        fontFamily: t.sans,
        overflow: 'hidden',
      }}
    >
      {/* 背景：讲解页 hero（弱化） */}
      <div
        style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '100%', opacity: 0.22 }}
      >
        <img
          src={GM_ART.bedroom.src}
          alt=""
          style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
        />
      </div>
      {/* 遮罩 */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: t.dark ? 'rgba(0,0,0,0.72)' : 'rgba(20,14,8,0.58)',
        }}
      ></div>

      {/* 聊天底部面板 */}
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          height: PANEL_H,
          background: t.bg,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* 拖动把手 */}
        <div style={{ display: 'flex', justifyContent: 'center', padding: '10px 0 6px' }}>
          <div style={{ width: 36, height: 4, borderRadius: 2, background: t.line }}></div>
        </div>

        {/* 顶部锚点：作品缩略图 + 标题 + 收回按钮 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '0 18px 10px' }}>
          <div
            style={{
              background: t.surface,
              border: `1px solid ${t.line}`,
              padding: 4,
              flexShrink: 0,
            }}
          >
            <img
              src={GM_ART.bedroom.src}
              alt=""
              style={{
                width: 42,
                height: 42,
                objectFit: 'cover',
                display: 'block',
                border: `1px solid ${t.line}`,
              }}
            />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontFamily: t.serif,
                fontSize: 14,
                fontWeight: 700,
                color: t.ink,
                lineHeight: 1.3,
              }}
            >
              在阿尔勒的卧室
            </div>
            <div style={{ fontSize: 11, color: t.sub, marginTop: 2 }}>文森特·梵高 · 1889</div>
          </div>
          <div
            style={{
              width: 34,
              height: 34,
              background: t.chipBg,
              border: `1px solid ${t.line}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <GMIcon name="chevD" size={18} color={t.sub} sw={2} />
          </div>
        </div>
        <GMHairline t={t} />

        {/* 聊天消息区（可滚动） */}
        <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '14px 16px 4px' }}>
          {/* 第一轮：用户问题 */}
          <Bubble who="user" text="为什么透视是歪的？" />

          {/* 第一轮：助手回答（完整） */}
          <Bubble who="ai" text={A1} source="奥赛博物馆官方资料 · GoMuseum AI" />

          {/* 后续推荐问题 chips */}
          <div style={{ marginTop: 10, marginBottom: 14 }}>
            <div style={{ fontSize: 10.5, color: t.faint, letterSpacing: 1, marginBottom: 7 }}>
              继续问
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
              {chips2.map((q) => (
                <div
                  key={q}
                  style={{
                    padding: '6px 12px',
                    background: t.chipBg,
                    border: `1px solid ${t.line}`,
                    fontSize: 12,
                    color: t.ink,
                  }}
                >
                  {q}
                </div>
              ))}
            </div>
          </div>

          {/* 第二轮：用户问题 */}
          <Bubble who="user" text="还画了几个版本？" />

          {/* 第二轮：助手流式生成中 */}
          <Bubble who="ai" streaming={true} />
        </div>

        {/* 底部输入条 */}
        <div
          style={{
            flexShrink: 0,
            padding: '10px 14px 16px',
            borderTop: `1px solid ${t.line}`,
            background: t.bg,
            display: 'flex',
            gap: 9,
            alignItems: 'center',
          }}
        >
          <div
            style={{
              flex: 1,
              height: 44,
              border: `1px solid ${t.line}`,
              background: t.surface,
              display: 'flex',
              alignItems: 'center',
              padding: '0 14px',
              fontSize: 13.5,
              color: t.faint,
            }}
          >
            继续提问……
          </div>
          <div
            style={{
              width: 44,
              height: 44,
              border: `1px solid ${t.line}`,
              background: t.surface,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <GMIcon name="mic" size={19} color={t.sub} />
          </div>
          <div
            style={{
              width: 44,
              height: 44,
              background: t.ctaBg,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <GMIcon name="send" size={17} color={t.ctaInk} sw={2} />
          </div>
        </div>
      </div>
    </div>
  );
}

function FinalGuideInfo({ t = FIN }) {
  const infoRows = [
    { label: '馆藏编号', value: 'RF 1959 2' },
    { label: '现藏地', value: '奥赛博物馆，巴黎，法国' },
    {
      label: '来源流转',
      value: '西奥·梵高遗赠 → 约翰娜·梵高-邦格尔 → 1921 卢森堡美术馆 → 1947 奥赛博物馆',
    },
    { label: '展览史', value: '1905 巴黎春季沙龙；1937 巴黎世博会' },
    { label: '签名题字', value: '右下角签名 "Vincent"' },
    { label: '参考文献', value: 'De la Faille 1970, F 484 / JH 1608' },
  ];
  const tabs = ['介绍', '作者', '背景', '故事'];
  return (
    <GMScreen t={t}>
      {/* 顶栏：Hero 折叠后标题提升至此 */}
      <div
        style={{
          padding: '12px 18px 8px',
          display: 'flex',
          alignItems: 'center',
          flexShrink: 0,
          borderBottom: `1px solid ${t.line}`,
        }}
      >
        <GMIcon name="back" size={20} color={t.ink} />
        <span
          style={{
            flex: 1,
            textAlign: 'center',
            fontFamily: t.serif,
            fontSize: 14.5,
            fontWeight: 700,
            color: t.ink,
            letterSpacing: 0.5,
          }}
        >
          在阿尔勒的卧室
        </span>
        <GMIcon name="star" size={20} color={t.accent} />
      </div>

      <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '0 20px' }}>
        {/* 流式墙签（始终可见） */}
        <div style={{ padding: '9px 0 10px', borderBottom: `1px solid ${t.line}` }}>
          <div style={{ fontSize: 12.5, color: t.sub, lineHeight: 1.6 }}>
            文森特·梵高 · 1889 · 布面油画 · 72 × 90 cm
          </div>
        </div>

        {/* ▾ 作品信息（展开态） */}
        <div style={{ borderBottom: `1px solid ${t.line}` }}>
          <div style={{ display: 'flex', alignItems: 'center', padding: '9px 0', gap: 9 }}>
            <span style={{ fontSize: 11, color: t.accent, fontWeight: 900, lineHeight: 1 }}>▾</span>
            <span
              style={{
                fontFamily: t.serif,
                fontSize: 13.5,
                fontWeight: 700,
                letterSpacing: 0.5,
                color: t.ink,
              }}
            >
              作品信息
            </span>
            <div style={{ flex: 1, height: 1, background: t.line }}></div>
          </div>
          {/* 展开内容 — 硬事实表 */}
          <div
            style={{
              background: t.surface,
              border: `1px solid ${t.line}`,
              marginBottom: 12,
              padding: '2px 0',
            }}
          >
            {infoRows.map((r, i) => (
              <div
                key={r.label}
                style={{
                  display: 'flex',
                  gap: 12,
                  padding: '9px 14px',
                  borderBottom: i < infoRows.length - 1 ? `1px solid ${t.line}` : 'none',
                }}
              >
                <span
                  style={{
                    fontSize: 10.5,
                    letterSpacing: 1.5,
                    color: t.faint,
                    textTransform: 'uppercase',
                    flexShrink: 0,
                    width: 52,
                    paddingTop: 1,
                  }}
                >
                  {r.label}
                </span>
                <span style={{ fontSize: 12.5, color: t.ink, lineHeight: 1.6 }}>{r.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Tab 栏 */}
        <div style={{ display: 'flex', borderBottom: `1.5px solid ${t.line}`, marginTop: 2 }}>
          {tabs.map((tab, i) => {
            const on = i === 0;
            return (
              <div
                key={tab}
                style={{
                  flex: 1,
                  textAlign: 'center',
                  padding: '10px 0',
                  fontSize: 12.5,
                  fontFamily: t.serif,
                  fontWeight: on ? 700 : 400,
                  color: on ? t.accentDeep : t.sub,
                  borderBottom: on ? `2.5px solid ${t.accent}` : '2.5px solid transparent',
                  letterSpacing: 0.5,
                  marginBottom: -1.5,
                }}
              >
                {tab}
              </div>
            );
          })}
        </div>

        {/* 讲解首段 */}
        <p
          style={{
            margin: '13px 0 20px',
            fontSize: 13.5,
            lineHeight: 1.9,
            color: t.ink,
            textAlign: 'justify',
          }}
        >
          {FIN_P1}
        </p>
      </div>

      {/* AI 问答 */}
      <div
        style={{
          flexShrink: 0,
          padding: '0 20px 13px',
          borderTop: `1px solid ${t.line}`,
          background: t.bg,
        }}
      >
        <div style={{ display: 'flex', gap: 8, paddingTop: 9, marginBottom: 8 }}>
          {['为什么透视是歪的？', '他住了多久？'].map((q) => (
            <div
              key={q}
              style={{
                padding: '6px 12px',
                background: t.chipBg,
                fontSize: 11.5,
                color: t.ink,
                flexShrink: 0,
              }}
            >
              {q}
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <div
            style={{
              flex: 1,
              height: 42,
              border: `1px solid ${t.line}`,
              background: t.surface,
              display: 'flex',
              alignItems: 'center',
              padding: '0 16px',
              fontSize: 13,
              color: t.faint,
            }}
          >
            问问这幅画……
          </div>
          <div
            style={{
              width: 42,
              height: 42,
              borderRadius: '50%',
              background: t.ctaBg,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <GMIcon name="mic" size={18} color={t.ctaInk} />
          </div>
        </div>
      </div>
    </GMScreen>
  );
}

// ───────────────────────── 取景拍照页（识别入口） ─────────────────────────
function FinalCapture({ t = FIN }) {
  const gallery = [GM_ART.bedroom, GM_ART.rhone, GM_ART.self1889, GM_ART.crows];
  return (
    <div
      style={{
        height: '100%',
        background: '#0F0C09',
        display: 'flex',
        flexDirection: 'column',
        fontFamily: t.sans,
        overflow: 'hidden',
      }}
    >
      {/* 取景器 */}
      <div style={{ position: 'relative', flex: 1, minHeight: 0 }}>
        <img
          src={GM_ART.photoBedroom.src}
          alt="取景"
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
          }}
        />
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background:
              'linear-gradient(180deg, rgba(15,12,9,0.5) 0%, rgba(15,12,9,0.05) 22% 70%, rgba(15,12,9,0.65) 100%)',
          }}
        ></div>

        {/* 顶栏 */}
        <div
          style={{
            position: 'absolute',
            top: 14,
            left: 16,
            right: 16,
            display: 'flex',
            alignItems: 'center',
          }}
        >
          <div
            style={{
              width: 38,
              height: 38,
              borderRadius: '50%',
              background: 'rgba(15,12,9,0.5)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <GMIcon name="close" size={19} color="#F6F1E4" />
          </div>
          <span style={{ flex: 1 }}></span>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 7,
              padding: '7px 14px',
              borderRadius: 999,
              background: 'rgba(15,12,9,0.5)',
            }}
          >
            <span
              style={{
                fontFamily: t.serif,
                fontSize: 13,
                fontWeight: 600,
                color: '#F6F1E4',
                letterSpacing: 1,
              }}
            >
              识别画作
            </span>
          </div>
          <span style={{ flex: 1 }}></span>
          <div
            style={{
              width: 38,
              height: 38,
              borderRadius: '50%',
              background: 'rgba(15,12,9,0.5)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <GMIcon name="flash" size={19} color="#F6F1E4" />
          </div>
        </div>

        {/* 取景四角 */}
        {[
          { top: 70, left: 38, bt: 1, bl: 1 },
          { top: 70, right: 38, bt: 1, br: 1 },
          { bottom: 90, left: 38, bb: 1, bl: 1 },
          { bottom: 90, right: 38, bb: 1, br: 1 },
        ].map((p, i) => (
          <div
            key={i}
            style={{
              position: 'absolute',
              width: 34,
              height: 34,
              top: p.top,
              left: p.left,
              right: p.right,
              bottom: p.bottom,
              borderTop: p.bt ? '2.5px solid rgba(246,241,228,0.92)' : 'none',
              borderBottom: p.bb ? '2.5px solid rgba(246,241,228,0.92)' : 'none',
              borderLeft: p.bl ? '2.5px solid rgba(246,241,228,0.92)' : 'none',
              borderRight: p.br ? '2.5px solid rgba(246,241,228,0.92)' : 'none',
            }}
          ></div>
        ))}

        {/* 提示 */}
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: 0,
            right: 0,
            textAlign: 'center',
            transform: 'translateY(60px)',
          }}
        >
          <span
            style={{
              fontSize: 12.5,
              color: '#F6F1E4',
              background: 'rgba(15,12,9,0.45)',
              padding: '6px 14px',
              borderRadius: 999,
              letterSpacing: 1,
            }}
          >
            将画作完整置于取景框内
          </span>
        </div>
      </div>

      {/* 控制条 — 暖纸 */}
      <div style={{ background: t.bg, padding: '0 0 14px', flexShrink: 0 }}>
        {/* 图库横排 */}
        <div style={{ padding: '14px 22px 0', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 11.5, letterSpacing: 1, color: t.sub }}>最近图库</span>
          <div style={{ flex: 1, height: 1, background: t.line }}></div>
          <span style={{ fontSize: 11.5, color: t.accent, fontWeight: 600 }}>全部相册 →</span>
        </div>
        <div style={{ display: 'flex', gap: 10, padding: '12px 22px 0', overflow: 'hidden' }}>
          {gallery.map((g, i) => (
            <GMImg
              key={i}
              art={g}
              w={52}
              h={52}
              style={{ border: `1px solid ${t.line}`, flexShrink: 0 }}
            />
          ))}
        </div>

        {/* 快门行：图库 · 快门 · 切换 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 40px 0',
          }}
        >
          {/* 从图库选择 */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5 }}>
            <div
              style={{
                width: 46,
                height: 46,
                borderRadius: 8,
                border: `1.5px solid ${t.line}`,
                background: t.surface,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <GMIcon name="photo" size={22} color={t.ink} />
            </div>
            <span style={{ fontSize: 10.5, color: t.sub, letterSpacing: 0.5 }}>图库</span>
          </div>
          {/* 快门 */}
          <div
            style={{
              width: 74,
              height: 74,
              borderRadius: '50%',
              background: t.ctaBg,
              border: `4px solid ${t.bg}`,
              boxShadow: `0 0 0 2px ${t.ctaBg}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <GMIcon name="camera" size={30} color={t.ctaInk} sw={1.7} />
          </div>
          {/* 占位（保持快门居中） */}
          <div
            style={{
              width: 46,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 5,
            }}
          >
            <div
              style={{
                width: 46,
                height: 46,
                borderRadius: 8,
                border: `1.5px solid ${t.line}`,
                background: t.surface,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <GMIcon name="search" size={20} color={t.ink} />
            </div>
            <span style={{ fontSize: 10.5, color: t.sub, letterSpacing: 0.5 }}>搜索</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ───────────────────────── 拍照识别 · 候选确认 ─────────────────────────
function FinalScan({ t = FIN }) {
  const cands = [
    { art: GM_ART.self1889, name: '自画像', meta: '梵高 · 1889 · 奥赛博物馆', conf: '4%' },
    { art: GM_ART.rhone, name: '罗纳河上的星夜', meta: '梵高 · 1888 · 奥赛博物馆', conf: '1%' },
  ];
  return (
    <div
      style={{
        height: '100%',
        background: '#171310',
        display: 'flex',
        flexDirection: 'column',
        fontFamily: t.sans,
        overflow: 'hidden',
      }}
    >
      {/* 取景器 */}
      <div style={{ position: 'relative', flex: 1, minHeight: 0 }}>
        <img
          src={GM_ART.photoBedroom.src}
          alt="取景"
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
          }}
        />
        <div style={{ position: 'absolute', inset: 0, background: 'rgba(23,19,16,0.18)' }}></div>
        <div
          style={{
            position: 'absolute',
            top: 12,
            left: 16,
            right: 16,
            display: 'flex',
            justifyContent: 'space-between',
          }}
        >
          {['close', 'flash'].map((n) => (
            <div
              key={n}
              style={{
                width: 38,
                height: 38,
                borderRadius: '50%',
                background: 'rgba(23,19,16,0.5)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <GMIcon name={n} size={19} color="#F6F1E4" />
            </div>
          ))}
        </div>
        {[
          { top: 56, left: 40, bt: 1, bl: 1 },
          { top: 56, right: 40, bt: 1, br: 1 },
          { bottom: 60, left: 40, bb: 1, bl: 1 },
          { bottom: 60, right: 40, bb: 1, br: 1 },
        ].map((p, i) => (
          <div
            key={i}
            style={{
              position: 'absolute',
              width: 30,
              height: 30,
              top: p.top,
              left: p.left,
              right: p.right,
              bottom: p.bottom,
              borderTop: p.bt ? '2.5px solid #F6F1E4' : 'none',
              borderBottom: p.bb ? '2.5px solid #F6F1E4' : 'none',
              borderLeft: p.bl ? '2.5px solid #F6F1E4' : 'none',
              borderRight: p.br ? '2.5px solid #F6F1E4' : 'none',
            }}
          ></div>
        ))}
      </div>

      {/* 结果面板 — 暖纸 */}
      <div
        style={{
          background: t.bg,
          borderRadius: '18px 18px 0 0',
          padding: '10px 22px 18px',
          flexShrink: 0,
          color: t.ink,
        }}
      >
        <div
          style={{ width: 36, height: 4, borderRadius: 2, background: t.line, margin: '0 auto' }}
        ></div>
        <div style={{ display: 'flex', alignItems: 'baseline', marginTop: 13 }}>
          <span style={{ fontFamily: t.serif, fontSize: 16.5, fontWeight: 700 }}>
            识别完成，请确认展品
          </span>
          <span style={{ flex: 1 }}></span>
          <span style={{ fontSize: 11.5, color: t.sub }}>用时 0.8 s</span>
        </div>

        {/* 首选候选 — 装裱卡 */}
        <div
          style={{
            marginTop: 13,
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            padding: 11,
            background: t.surface,
            border: `1.5px solid ${t.accent}`,
          }}
        >
          <GMImg art={GM_ART.bedroom} w={60} h={60} style={{ border: `1px solid ${t.line}` }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontFamily: t.serif, fontSize: 16.5, fontWeight: 600 }}>在阿尔的卧室</div>
            <div style={{ fontSize: 12, color: t.sub, marginTop: 4 }}>梵高 · 1889 · 奥赛博物馆</div>
          </div>
          <div style={{ textAlign: 'center', flexShrink: 0 }}>
            <div
              style={{ fontFamily: t.serif, fontSize: 18, fontWeight: 700, color: t.accentDeep }}
            >
              94%
            </div>
            <div style={{ fontSize: 10, color: t.sub, marginTop: 2 }}>置信度</div>
          </div>
        </div>

        {cands.map((c) => (
          <div
            key={c.name}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 14,
              padding: '9px 12px',
              borderBottom: `1px solid ${t.line}`,
            }}
          >
            <GMImg art={c.art} w={40} h={40} style={{ border: `1px solid ${t.line}` }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontFamily: t.serif, fontSize: 14.5 }}>{c.name}</div>
              <div style={{ fontSize: 11.5, color: t.sub, marginTop: 3 }}>{c.meta}</div>
            </div>
            <span style={{ fontSize: 12.5, color: t.faint }}>{c.conf}</span>
          </div>
        ))}

        {/* 确认按钮 — 门票式 */}
        <div
          style={{
            marginTop: 14,
            background: t.ctaBg,
            color: t.ctaInk,
            borderRadius: 4,
            padding: 6,
          }}
        >
          <div
            style={{
              border: `1px dashed ${t.ctaDash}`,
              borderRadius: 2,
              height: 44,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 10,
            }}
          >
            <GMIcon name="headphones" size={18} color={t.ctaInk} />
            <span
              style={{ fontFamily: t.serif, fontSize: 15, fontWeight: 600, letterSpacing: 1.5 }}
            >
              确认，开始讲解
            </span>
          </div>
        </div>
        <div style={{ marginTop: 11, textAlign: 'center', fontSize: 12.5, color: t.accent }}>
          都不是？搜索作品名或展签编号 →
        </div>
      </div>
    </div>
  );
}

// ───────────────────────── 探索 ─────────────────────────
function FinalExplore({ t = FIN }) {
  return (
    <GMScreen t={t}>
      <div
        style={{
          flex: 1,
          minHeight: 0,
          padding: '16px 26px 0',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* 刊头式标题 */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div
            style={{
              fontFamily: t.serif,
              fontSize: 21,
              fontWeight: 700,
              letterSpacing: 4,
              paddingLeft: 4,
            }}
          >
            探 索
          </div>
          <div style={{ marginTop: 8 }}>
            <FinDiamond t={t} w={110} />
          </div>
        </div>

        {/* 搜索框 */}
        <div
          style={{
            marginTop: 14,
            height: 46,
            border: `1px solid ${t.line}`,
            background: t.surface,
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '0 16px',
          }}
        >
          <GMIcon name="search" size={18} color={t.faint} />
          <span style={{ fontSize: 13.5, color: t.faint }}>搜索城市、博物馆或艺术品</span>
        </div>

        {/* 城市 */}
        <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
          {['巴黎', '阿姆斯特丹', '伦敦', '维也纳'].map((c, i) => (
            <div
              key={c}
              style={{
                padding: '7px 15px',
                fontSize: 12.5,
                background: i === 0 ? t.ctaBg : 'transparent',
                color: i === 0 ? t.ctaInk : t.sub,
                border: `1px solid ${i === 0 ? t.ctaBg : t.line}`,
              }}
            >
              {c}
            </div>
          ))}
        </div>

        <FinSectionHead t={t} n="01" label="巴黎" note="12 家博物馆" style={{ marginTop: 22 }} />

        {/* 奥赛装裱卡 */}
        <div style={{ marginTop: 13, background: t.surface, border: `1px solid ${t.line}` }}>
          <div style={{ padding: '9px 9px 0' }}>
            <GMImg art={GM_ART.orsayHall} h={124} style={{ border: `1px solid ${t.line}` }} />
          </div>
          <div style={{ padding: '12px 14px 14px' }}>
            <div style={{ display: 'flex', alignItems: 'baseline' }}>
              <span style={{ fontFamily: t.serif, fontSize: 17, fontWeight: 600 }}>奥赛博物馆</span>
              <span style={{ flex: 1 }}></span>
              <span style={{ fontSize: 11.5, color: t.accent, fontWeight: 600 }}>
                开放中 · 至 21:45
              </span>
            </div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 14,
                marginTop: 8,
                fontSize: 12,
                color: t.sub,
              }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <GMIcon name="ticket" size={14} color={t.faint} /> €16 · 周一闭馆
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <GMIcon name="pin" size={14} color={t.faint} /> 0.8 km
              </span>
            </div>
            <GMHairline t={t} style={{ margin: '11px 0' }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
              <div style={{ display: 'flex', gap: 6 }}>
                <GMImg
                  art={GM_ART.rhone}
                  w={34}
                  h={34}
                  style={{ border: `2px solid ${t.surface}`, outline: `1px solid ${t.line}` }}
                />
                <GMImg
                  art={GM_ART.self1889}
                  w={34}
                  h={34}
                  style={{ border: `2px solid ${t.surface}`, outline: `1px solid ${t.line}` }}
                />
                <GMImg
                  art={GM_ART.bedroom}
                  w={34}
                  h={34}
                  style={{ border: `2px solid ${t.surface}`, outline: `1px solid ${t.line}` }}
                />
              </div>
              <span style={{ fontSize: 11, color: t.sub }}>含 86 件已收录讲解</span>
              <span style={{ flex: 1 }}></span>
              <GMIcon name="chevR" size={17} color={t.faint} />
            </div>
          </div>
        </div>

        {/* 其余条目 */}
        {[
          { n: '02', name: '卢浮宫', meta: '9:00–18:00 · €22 · 1.9 km' },
          { n: '03', name: '橘园美术馆', meta: '9:00–18:00 · €12 · 1.6 km' },
          { n: '04', name: '罗丹美术馆', meta: '10:00–18:30 · €14 · 2.2 km' },
        ].map((m) => (
          <div
            key={m.name}
            style={{
              display: 'flex',
              alignItems: 'center',
              height: 58,
              borderBottom: `1px solid ${t.line}`,
              gap: 14,
            }}
          >
            <span
              style={{
                fontFamily: t.serif,
                fontSize: 13,
                color: t.faint,
                fontWeight: 700,
                letterSpacing: 2,
              }}
            >
              {m.n}
            </span>
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: t.serif, fontSize: 15, fontWeight: 600 }}>{m.name}</div>
              <div style={{ fontSize: 11.5, color: t.sub, marginTop: 3 }}>{m.meta}</div>
            </div>
            <GMIcon name="chevR" size={17} color={t.faint} />
          </div>
        ))}
      </div>
      <GMNavScan t={t} active="探索" />
    </GMScreen>
  );
}

// ───────────────────────── 足迹 ─────────────────────────
function FinalFootprints({ t = FIN }) {
  const groups = [
    {
      n: '01',
      museum: '奥赛博物馆 · 巴黎',
      when: '今天',
      items: [
        { art: GM_ART.bedroom, name: '在阿尔的卧室', meta: '14:32 · 已听完 · 4 min', star: true },
        { art: GM_ART.rhone, name: '罗纳河上的星夜', meta: '14:05 · 听到 2:10', star: true },
        { art: GM_ART.self1889, name: '自画像', meta: '13:48 · 已听完 · 3 min', star: false },
      ],
    },
    {
      n: '02',
      museum: '梵高博物馆 · 阿姆斯特丹',
      when: '5月28日',
      items: [
        { art: GM_ART.crows, name: '麦田群鸦', meta: '已听完 · 5 min', star: true },
        { art: GM_ART.thunder, name: '雷雨云下的麦田', meta: '已听完 · 4 min', star: false },
      ],
    },
    {
      n: '03',
      museum: '荷兰国家博物馆 · 阿姆斯特丹',
      when: '5月27日',
      items: [{ art: GM_ART.self1887, name: '自画像', meta: '已听完 · 4 min', star: false }],
    },
  ];
  return (
    <GMScreen t={t}>
      <div
        style={{
          flex: 1,
          minHeight: 0,
          padding: '16px 26px 0',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div
            style={{
              fontFamily: t.serif,
              fontSize: 21,
              fontWeight: 700,
              letterSpacing: 4,
              paddingLeft: 4,
            }}
          >
            足 迹
          </div>
          <div style={{ marginTop: 8 }}>
            <FinDiamond t={t} w={110} />
          </div>
          <div style={{ marginTop: 8, fontSize: 11.5, letterSpacing: 1, color: t.sub }}>
            6 件作品 · 3 座博物馆 · 2 座城市
          </div>
        </div>

        {groups.map((g) => (
          <div key={g.museum}>
            <FinSectionHead
              t={t}
              n={g.n}
              label={g.museum}
              note={g.when}
              style={{ marginTop: 20 }}
            />
            {g.items.map((it) => (
              <div
                key={it.name + it.meta}
                style={{ display: 'flex', alignItems: 'center', gap: 13, padding: '9px 0' }}
              >
                <GMImg
                  art={it.art}
                  w={46}
                  h={46}
                  style={{ border: `2px solid ${t.surface}`, outline: `1px solid ${t.line}` }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontFamily: t.serif, fontSize: 14.5, fontWeight: 600 }}>
                    {it.name}
                  </div>
                  <div style={{ fontSize: 11.5, color: t.sub, marginTop: 3 }}>{it.meta}</div>
                </div>
                <GMIcon name="star" size={18} color={it.star ? t.accent : t.line} fill={it.star} />
              </div>
            ))}
          </div>
        ))}
      </div>
      <GMNavScan t={t} active="足迹" />
    </GMScreen>
  );
}

// ───────────────────────── 城市选择 · 下拉搜索（展开态） ─────────────────────────
function FinalCityPicker({ t = FIN }) {
  const cities = [
    { name: '巴黎', en: 'Paris', meta: '12 家博物馆 · 当前定位', cur: true },
    { name: '阿姆斯特丹', en: 'Amsterdam', meta: '8 家博物馆' },
    { name: '伦敦', en: 'London', meta: '15 家博物馆' },
    { name: '维也纳', en: 'Vienna', meta: '9 家博物馆' },
    { name: '佛罗伦萨', en: 'Florence', meta: '7 家博物馆' },
  ];
  return (
    <GMScreen t={t}>
      <div
        style={{
          position: 'relative',
          flex: 1,
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* 底层：首页（弱化） */}
        <div
          style={{
            flex: 1,
            minHeight: 0,
            opacity: 0.25,
            pointerEvents: 'none',
            overflow: 'hidden',
          }}
        >
          <FinalHome t={t} />
        </div>
        {/* 遮罩 */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: t.dark ? 'rgba(0,0,0,0.5)' : 'rgba(44,35,22,0.32)',
          }}
        ></div>

        {/* 下拉面板 — 贴左，自适应宽度 */}
        <div
          style={{
            position: 'absolute',
            top: 12,
            left: 16,
            width: 232,
            background: t.surface,
            border: `1px solid ${t.line}`,
            borderRadius: 6,
            boxShadow: t.dark ? '0 16px 40px rgba(0,0,0,0.6)' : '0 16px 40px rgba(44,35,22,0.22)',
            overflow: 'hidden',
          }}
        >
          {/* 搜索框 */}
          <div style={{ padding: 12 }}>
            <div
              style={{
                height: 40,
                border: `1px solid ${t.line}`,
                background: t.bg,
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '0 12px',
              }}
            >
              <GMIcon name="search" size={16} color={t.faint} />
              <span style={{ fontSize: 13, color: t.ink, flex: 1 }}>
                巴黎<span style={{ color: t.accent }}>|</span>
              </span>
              <GMIcon name="close" size={14} color={t.faint} />
            </div>
            {/* 自动定位 */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 7,
                marginTop: 11,
                color: t.accent,
              }}
            >
              <GMIcon name="pin" size={15} color={t.accent} sw={1.8} />
              <span style={{ fontSize: 12.5, fontWeight: 600 }}>使用我的当前位置</span>
            </div>
          </div>
          <GMHairline t={t} />
          {/* 城市列表 */}
          <div style={{ maxHeight: 360, overflow: 'hidden' }}>
            {cities.map((c) => (
              <div
                key={c.name}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '10px 14px',
                  background: c.cur ? t.chipBg : 'transparent',
                  borderBottom: `1px solid ${t.line}`,
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 7 }}>
                    <span style={{ fontFamily: t.serif, fontSize: 15, fontWeight: 600 }}>
                      {c.name}
                    </span>
                    <span style={{ fontSize: 10.5, color: t.faint, letterSpacing: 0.5 }}>
                      {c.en}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: t.sub, marginTop: 2 }}>{c.meta}</div>
                </div>
                {c.cur && <GMIcon name="check" size={16} color={t.accent} sw={2} />}
              </div>
            ))}
          </div>
        </div>
      </div>
      <GMNavScan t={t} active="首页" />
    </GMScreen>
  );
}

// ───────────────────────── 设置 ─────────────────────────
function FinalSettings({ t = FIN }) {
  const Toggle = ({ on }) => (
    <div
      style={{
        width: 40,
        height: 23,
        borderRadius: 999,
        padding: 2.5,
        boxSizing: 'border-box',
        background: on ? t.accent : t.line,
        display: 'flex',
        justifyContent: on ? 'flex-end' : 'flex-start',
      }}
    >
      <div style={{ width: 18, height: 18, borderRadius: '50%', background: t.surface }}></div>
    </div>
  );
  // 外观选择 — 分段控件：浅色 / 深色 / 跟随系统
  const ModeSeg = () => {
    const cur = t.dark ? '深色' : '浅色';
    return (
      <div style={{ display: 'flex', border: `1px solid ${t.line}`, background: t.surface }}>
        {['浅色', '深色', '跟随系统'].map((m) => {
          const on = m === cur;
          return (
            <div
              key={m}
              style={{
                padding: '5px 11px',
                fontSize: 11.5,
                letterSpacing: 1,
                background: on ? t.ctaBg : 'transparent',
                color: on ? t.ctaInk : t.sub,
                fontWeight: on ? 600 : 400,
              }}
            >
              {m}
            </div>
          );
        })}
      </div>
    );
  };
  const Row = ({ icon, label, value, toggle, on, control }) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 13, height: 48 }}>
      <GMIcon name={icon} size={19} color={t.sub} />
      <span style={{ fontSize: 14, flex: 1 }}>{label}</span>
      {value && <span style={{ fontSize: 12.5, color: t.sub }}>{value}</span>}
      {control ? (
        control
      ) : toggle ? (
        <Toggle on={on} />
      ) : (
        <GMIcon name="chevR" size={16} color={t.faint} />
      )}
    </div>
  );
  return (
    <GMScreen t={t}>
      <div
        style={{
          flex: 1,
          minHeight: 0,
          padding: '16px 26px 0',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div
            style={{
              fontFamily: t.serif,
              fontSize: 21,
              fontWeight: 700,
              letterSpacing: 4,
              paddingLeft: 4,
            }}
          >
            设 置
          </div>
          <div style={{ marginTop: 8 }}>
            <FinDiamond t={t} w={110} />
          </div>
        </div>

        {/* 额度卡 — 门票式 */}
        <div
          style={{
            marginTop: 16,
            background: t.surface,
            border: `1px solid ${t.line}`,
            padding: 6,
          }}
        >
          <div
            style={{
              border: `1px dashed ${t.faint}`,
              padding: '12px 14px',
              display: 'flex',
              alignItems: 'center',
              gap: 14,
            }}
          >
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 11.5, letterSpacing: 1, color: t.sub }}>免费识别额度</div>
              <div style={{ fontFamily: t.serif, fontSize: 18, fontWeight: 700, marginTop: 4 }}>
                剩余 8{' '}
                <span style={{ fontSize: 13, color: t.faint, fontWeight: 400 }}>/ 10 次</span>
              </div>
              <div style={{ position: 'relative', height: 3, background: t.chipBg, marginTop: 9 }}>
                <div
                  style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    bottom: 0,
                    width: '80%',
                    background: t.accent,
                  }}
                ></div>
              </div>
            </div>
            <div
              style={{
                padding: '9px 18px',
                background: t.ctaBg,
                color: t.ctaInk,
                fontSize: 13,
                fontFamily: t.serif,
                fontWeight: 600,
                letterSpacing: 2,
                flexShrink: 0,
              }}
            >
              升级
            </div>
          </div>
        </div>

        <FinSectionHead t={t} n="01" label="通用" style={{ marginTop: 20 }} />
        <div style={{ marginTop: 4 }}>
          <Row icon="globe" label="讲解语言" value="简体中文" />
          <Row icon="moon" label="外观" control={<ModeSeg />} />
          <Row icon="download" label="离线馆包" value="已下载 2 个馆" />
          <Row icon="photo" label="自动保存照片" toggle on={false} />
          <Row icon="volume" label="TTS 音色" value="沉稳 · 女声" />
        </div>

        <FinSectionHead t={t} n="02" label="账户" style={{ marginTop: 12 }} />
        <div style={{ marginTop: 4 }}>
          <Row icon="user" label="登录 / 绑定账号" value="未登录" />
        </div>

        <FinSectionHead t={t} n="03" label="支持与法律" style={{ marginTop: 12 }} />
        <div style={{ marginTop: 4 }}>
          <Row icon="heart" label="鼓励我们" />
          <Row icon="shield" label="隐私政策" />
        </div>

        <div style={{ flex: 1 }}></div>
        <div
          style={{
            textAlign: 'center',
            fontSize: 11,
            color: t.faint,
            paddingBottom: 10,
            fontStyle: 'italic',
          }}
        >
          GoMuseum 0.9.2 · MVP
        </div>
      </div>
      <GMNavScan t={t} active="设置" />
    </GMScreen>
  );
}

Object.assign(window, {
  FinalLogin,
  FinalHome,
  FinalCityPicker,
  FinalCapture,
  FinalScan,
  FinalGuide,
  FinalGuideInfo,
  FinalGuideChat,
  FinalCollection,
  FinalExplore,
  FinalFootprints,
  FinalSettings,
});
