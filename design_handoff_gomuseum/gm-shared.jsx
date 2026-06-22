// gm-shared.jsx — GoMuseum 设计探索共用：主题令牌 / 图标 / 原子组件
// 依赖：React (全局)，被 screens-*.jsx 使用。

// ───────────────────────── 主题令牌 ─────────────────────────
const GM_THEMES = {
  // A · 画廊白 Galerie — 大量留白、墨色、古铜点缀
  A: {
    id: 'A',
    serif: "'Noto Serif SC', 'Songti SC', 'STSong', serif",
    sans: "'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif",
    bg: '#FBFAF6',
    surface: '#FFFFFF',
    ink: '#211C14',
    sub: '#7A7466',
    faint: '#ABA494',
    line: '#E8E3D6',
    accent: '#8E6F3E',
    accentDeep: '#6E5526',
    ctaBg: '#211C14',
    ctaInk: '#FBFAF6',
    chipBg: '#F1EDE2',
  },
  // B · 暖纸手册 Catalogue — 米纸底、赤陶点缀、目录编号
  B: {
    id: 'B',
    serif: "'Noto Serif SC', 'Songti SC', 'STSong', serif",
    sans: "'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif",
    bg: '#F3EDDF',
    surface: '#FBF7EC',
    ink: '#2C2316',
    sub: '#8A7A5F',
    faint: '#B0A283',
    line: '#DCD2B8',
    accent: '#A14E28',
    accentDeep: '#7E3A1C',
    ctaBg: '#A14E28',
    ctaInk: '#FBF7EC',
    ctaDash: 'rgba(251,247,236,0.45)',
    ctaDim: 'rgba(251,247,236,0.7)',
    chipBg: '#EAE2CD',
  },
  // BD · 暖纸手册 · 夜版 — 同一版式，深褐纸底 + 提亮赤陶
  BD: {
    id: 'BD',
    dark: true,
    serif: "'Noto Serif SC', 'Songti SC', 'STSong', serif",
    sans: "'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif",
    bg: '#201A12',
    surface: '#2A2218',
    ink: '#EFE6D2',
    sub: '#A89878',
    faint: '#6E614C',
    line: '#3A3022',
    accent: '#D08050',
    accentDeep: '#E09668',
    ctaBg: '#C26A3A',
    ctaInk: '#241A0F',
    ctaDash: 'rgba(36,26,15,0.45)',
    ctaDim: 'rgba(36,26,15,0.7)',
    chipBg: '#332A1D',
  },
  // C · 夜场 Nocturne — 墨色展厅、暖金点缀
  C: {
    id: 'C',
    serif: "'Noto Serif SC', 'Songti SC', 'STSong', serif",
    sans: "'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif",
    bg: '#131419',
    surface: '#1C1E26',
    ink: '#EFEAD9',
    sub: '#97917F',
    faint: '#6A655A',
    line: '#2C2E38',
    accent: '#C7A45E',
    accentDeep: '#D9BC7E',
    ctaBg: '#C7A45E',
    ctaInk: '#181308',
    chipBg: '#23252E',
  },
};

// ───────────────────────── 作品素材 ─────────────────────────
const GM_ART = {
  bedroom: {
    src: 'assets/art/crop-bedroom.png',
    title: '在阿尔的卧室',
    artist: '文森特·梵高',
    year: '1889',
    museum: '奥赛博物馆',
  },
  rhone: {
    src: 'assets/art/crop-rhone.png',
    title: '罗纳河上的星夜',
    artist: '文森特·梵高',
    year: '1888',
    museum: '奥赛博物馆',
  },
  self1889: {
    src: 'assets/art/crop-self1889.png',
    title: '自画像',
    artist: '文森特·梵高',
    year: '1889',
    museum: '奥赛博物馆',
  },
  plain: {
    src: 'assets/art/crop-plain.png',
    title: '奥维尔平原',
    artist: '文森特·梵高',
    year: '1890',
    museum: '奥赛博物馆',
  },
  crows: {
    src: 'assets/art/crop-crows.png',
    title: '麦田群鸦',
    artist: '文森特·梵高',
    year: '1890',
    museum: '梵高博物馆',
  },
  thunder: {
    src: 'assets/art/crop-thunder.png',
    title: '雷雨云下的麦田',
    artist: '文森特·梵高',
    year: '1890',
    museum: '梵高博物馆',
  },
  self1887: {
    src: 'assets/art/crop-self1887.png',
    title: '自画像',
    artist: '文森特·梵高',
    year: '1887',
    museum: '荷兰国家博物馆',
  },
  orsayHall: { src: 'assets/art/orsay-hall.webp', title: '奥赛博物馆' },
  photoBedroom: { src: 'assets/art/77777.jpg', title: '取景照片' },
};

// ───────────────────────── 图标 ─────────────────────────
const GM_ICON_PATHS = {
  home: ['M3.5 11.5 12 4.5l8.5 7', 'M5.8 9.8V20h12.4V9.8'],
  compass: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z', 'M14.8 9.2l-1.7 4-4 1.6 1.7-4z'],
  pin: [
    'M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11Z',
    'M12 12.3a2.3 2.3 0 1 0 0-4.6 2.3 2.3 0 0 0 0 4.6Z',
  ],
  sliders: [
    'M4 7h16 M4 17h16 M4 12h16',
    'M14.5 7a1.8 1.8 0 1 0 0 .01 M8.5 12a1.8 1.8 0 1 0 0 .01 M16 17a1.8 1.8 0 1 0 0 .01',
  ],
  camera: [
    'M3.5 8.2a1.7 1.7 0 0 1 1.7-1.7h2.1L9 4h6l1.7 2.5h2.1a1.7 1.7 0 0 1 1.7 1.7v9.6a1.7 1.7 0 0 1-1.7 1.7H5.2a1.7 1.7 0 0 1-1.7-1.7Z',
    'M12 16.6a3.6 3.6 0 1 0 0-7.2 3.6 3.6 0 0 0 0 7.2Z',
  ],
  search: ['M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Z', 'M16.2 16.2 21 21'],
  play: ['M9.2 7.2v9.6l8-4.8z'],
  pause: ['M8.5 6.5v11 M15.5 6.5v11'],
  mic: [
    'M12 14.5a2.8 2.8 0 0 0 2.8-2.8V6.8a2.8 2.8 0 1 0-5.6 0v4.9A2.8 2.8 0 0 0 12 14.5Z',
    'M6.5 11.7a5.5 5.5 0 0 0 11 0 M12 17.2V20.5 M9.2 20.5h5.6',
  ],
  star: ['m12 4.6 2.2 4.6 5 .7-3.6 3.6.8 5-4.4-2.4-4.4 2.4.8-5L4.8 9.9l5-.7z'],
  chevR: ['m9.5 6 6 6-6 6'],
  back: ['M15 5l-7 7 7 7'],
  clock: ['M12 20.5a8.5 8.5 0 1 0 0-17 8.5 8.5 0 0 0 0 17Z', 'M12 7.5V12l3.2 1.9'],
  headphones: [
    'M4.5 17v-4.5a7.5 7.5 0 0 1 15 0V17',
    'M4.5 14.5h2.3v5.5H5.6a1.1 1.1 0 0 1-1.1-1.1Z',
    'M19.5 14.5h-2.3v5.5h1.2a1.1 1.1 0 0 0 1.1-1.1Z',
  ],
  close: ['M6 6l12 12 M18 6 6 18'],
  flash: ['M13 3 5.5 13.5h5L9.5 21 17 10.5h-5z'],
  check: ['m5 12.8 4.3 4.3L19 7.5'],
  arrowR: ['M4.5 12h14 M13 6.5l5.5 5.5-5.5 5.5'],
  globe: [
    'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z',
    'M3.5 12h17 M12 3.5c-5.6 5.4-5.6 11.6 0 17 5.6-5.4 5.6-11.6 0-17Z',
  ],
  download: [
    'M12 4v10 M7.5 10.5 12 15l4.5-4.5',
    'M4.5 16.5V19a1.5 1.5 0 0 0 1.5 1.5h12A1.5 1.5 0 0 0 19.5 19v-2.5',
  ],
  bell: ['M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 2H4.5Z', 'M10 20.5a2.2 2.2 0 0 0 4 0'],
  shield: ['M12 3.5 5 6v5.5c0 4.6 3 7.6 7 9 4-1.4 7-4.4 7-9V6Z'],
  moon: ['M19.5 14.5A7.8 7.8 0 0 1 9.5 4.5a8 8 0 1 0 10 10Z'],
  doc: ['M7 3.5h7L18.5 8v12.5h-11Z', 'M14 3.5V8h4.5 M9.5 12.5h5 M9.5 16h5'],
  user: [
    'M12 11.5a3.8 3.8 0 1 0 0-7.6 3.8 3.8 0 0 0 0 7.6Z',
    'M5 20.2c.8-3.5 3.6-5.4 7-5.4s6.2 1.9 7 5.4',
  ],
  photo: ['M4 5.5h16v13H4Z', 'm5.5 16 4.5-5 4 4.2 2-2.1 2.5 2.9 M15.3 9.3a1 1 0 1 0 0 .01'],
  heart: [
    'M12 19.5C7 15.7 4.5 12.9 4.5 9.9 4.5 7.7 6.2 6 8.4 6c1.4 0 2.8.7 3.6 1.9C12.8 6.7 14.2 6 15.6 6c2.2 0 3.9 1.7 3.9 3.9 0 3-2.5 5.8-7.5 9.6Z',
  ],
  mail: ['M3.5 6.5h17v11h-17Z', 'm4.5 7.5 7.5 6 7.5-6'],
  ticket: ['M4 7.5h16V11a1.6 1.6 0 0 0 0 3.2v3.3H4v-3.3A1.6 1.6 0 0 0 4 11Z', 'M14.5 7.5v10'],
  volume: ['M5 9.5v5h3l4.5 3.8V5.7L8 9.5Z', 'M16 9a4.3 4.3 0 0 1 0 6 M18.3 7a7.4 7.4 0 0 1 0 10'],
  lock: ['M7 11h10v8.5H7Z', 'M9 11V8a3 3 0 0 1 6 0v3'],
  send: ['M12 20V4', 'M5 11l7-7 7 7'],
  qr: [
    'M4.5 4.5h5v5h-5Z M14.5 4.5h5v5h-5Z M4.5 14.5h5v5h-5Z',
    'M14.5 14.5h2v2h-2Z M17.5 17.5h2v2h-2Z',
  ],
  sun: [
    'M12 16.5a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9Z',
    'M12 2.5v2.5 M12 19v2.5 M4.6 4.6l1.8 1.8 M17.6 17.6l1.8 1.8 M2.5 12h2.5 M19 12h2.5 M4.6 19.4l1.8-1.8 M17.6 6.4l1.8-1.8',
  ],
  cloudSun: [
    'M7.5 8.2a3 3 0 1 1 .8 2.1',
    'M9 19.5h7.5a3.5 3.5 0 0 0 .3-7A5 5 0 0 0 7.4 11 3.8 3.8 0 0 0 9 19.5Z',
    'M16.2 3v1.8 M21 7.8h-1.8 M19.4 4.4l-1.3 1.3',
  ],
  chevD: ['M7 10l5 5 5-5'],
};

function GMIcon({ name, size = 22, color = 'currentColor', sw = 1.6, fill = false, style }) {
  const paths = GM_ICON_PATHS[name] || [];
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={style}>
      {paths.map((d, i) => (
        <path
          key={i}
          d={d}
          fill={fill ? color : 'none'}
          stroke={color}
          strokeWidth={fill ? 0.8 : sw}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ))}
    </svg>
  );
}

// ───────────────────────── 原子组件 ─────────────────────────
function GMImg({ art, h, w, style, radius = 0 }) {
  return (
    <div
      style={{
        width: w || '100%',
        height: h,
        flexShrink: 0,
        overflow: 'hidden',
        borderRadius: radius,
        background: '#D8D2C2',
        ...style,
      }}
    >
      <img
        src={art.src}
        alt={art.title}
        style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
      />
    </div>
  );
}

function GMEyebrow({ t, children, style }) {
  return (
    <div
      style={{
        fontFamily: t.sans,
        fontSize: 11,
        letterSpacing: 2.2,
        color: t.sub,
        textTransform: 'uppercase',
        ...style,
      }}
    >
      {children}
    </div>
  );
}

function GMHairline({ t, style }) {
  return <div style={{ height: 1, background: t.line, ...style }}></div>;
}

// 底部导航 — 四个 Tab
function GMNav({ t, active = '首页' }) {
  const items = [
    { label: '首页', icon: 'home' },
    { label: '探索', icon: 'compass' },
    { label: '足迹', icon: 'pin' },
    { label: '设置', icon: 'sliders' },
  ];
  return (
    <div
      style={{
        height: 64,
        borderTop: `1px solid ${t.line}`,
        background: t.bg,
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        flexShrink: 0,
      }}
    >
      {items.map((it) => {
        const on = it.label === active;
        const c = on ? (t.id === 'C' ? t.accent : t.ink) : t.faint;
        return (
          <div
            key={it.label}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 4,
            }}
          >
            <GMIcon name={it.icon} size={21} color={c} sw={on ? 1.9 : 1.6} />
            <span
              style={{
                fontFamily: t.sans,
                fontSize: 10.5,
                letterSpacing: 1,
                color: c,
                fontWeight: on ? 600 : 400,
              }}
            >
              {it.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// 底部导航 v2 — 中央大识别按钮（定稿版）
function GMNavScan({ t, active = '首页' }) {
  const left = [
    { label: '首页', icon: 'home' },
    { label: '探索', icon: 'compass' },
  ];
  const right = [
    { label: '足迹', icon: 'pin' },
    { label: '设置', icon: 'sliders' },
  ];
  const Tab = (it) => {
    const on = it.label === active;
    const c = on ? t.accentDeep : t.faint;
    return (
      <div
        key={it.label}
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 4,
        }}
      >
        <GMIcon name={it.icon} size={21} color={c} sw={on ? 1.9 : 1.6} />
        <span
          style={{
            fontFamily: t.sans,
            fontSize: 10.5,
            letterSpacing: 1,
            color: c,
            fontWeight: on ? 600 : 400,
          }}
        >
          {it.label}
        </span>
      </div>
    );
  };
  return (
    <div
      style={{
        height: 68,
        borderTop: `1px solid ${t.line}`,
        background: t.bg,
        display: 'grid',
        gridTemplateColumns: '1fr 1fr 92px 1fr 1fr',
        flexShrink: 0,
        position: 'relative',
      }}
    >
      {left.map(Tab)}
      {/* 中央识别按钮 */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'flex-end',
          paddingBottom: 6,
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: -26,
            width: 60,
            height: 60,
            borderRadius: '50%',
            background: t.ctaBg,
            border: `4px solid ${t.bg}`,
            boxShadow: t.dark ? '0 6px 16px rgba(0,0,0,0.45)' : '0 6px 16px rgba(44,35,22,0.28)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <GMIcon name="camera" size={26} color={t.ctaInk} sw={1.7} />
        </div>
        <span
          style={{
            fontFamily: t.sans,
            fontSize: 10.5,
            letterSpacing: 1.5,
            color: active === '识别' ? t.accentDeep : t.sub,
            fontWeight: 600,
          }}
        >
          识别
        </span>
      </div>
      {right.map(Tab)}
    </div>
  );
}

// 屏幕外壳：填满设备内容区
function GMScreen({ t, children, style }) {
  return (
    <div
      data-screen-label={style && style.label}
      style={{
        height: '100%',
        background: t.bg,
        color: t.ink,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        fontFamily: t.sans,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

Object.assign(window, {
  GM_THEMES,
  GM_ART,
  GMIcon,
  GMImg,
  GMEyebrow,
  GMHairline,
  GMNav,
  GMNavScan,
  GMScreen,
});
