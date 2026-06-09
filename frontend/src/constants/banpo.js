export const BANPO_HALLS = [
  {
    key: 'basic',
    slug: 'basic-exhibition-hall',
    name: '基本陈列展厅',
    shortName: '陈列',
    icon: '🏺',
    type: '常开放',
    zone: '室内展区',
    floor: 1,
    estimated_duration_minutes: 25,
    display_order: 10,
    description: '以半坡遗址考古发现与研究成果为主线，系统呈现半坡文化的生活形态、生产方式与社会结构。',
    highlights: ['人面鱼纹彩陶盆', '尖底瓶', '彩陶与装饰品', '石器工具'],
  },
  {
    key: 'site',
    slug: 'site-protection-hall',
    name: '遗址保护大厅',
    shortName: '遗址',
    icon: '🏘️',
    type: '常开放',
    zone: '遗址空间',
    floor: 1,
    estimated_duration_minutes: 25,
    display_order: 20,
    description: '强调原址呈现与保护展示，可观察墓葬、地面圆形房屋、烧制作坊、灶具灶台等关键遗存。',
    highlights: ['墓葬', '地面圆形房屋', '烧制作坊', '灶具灶台'],
  },
  {
    key: 'kiln',
    slug: 'kiln-hall',
    name: '陶窑展厅',
    shortName: '陶窑',
    icon: '🔥',
    type: '常开放',
    zone: '工艺展区',
    floor: 1,
    estimated_duration_minutes: 18,
    display_order: 30,
    description: '以“陶器如何被制作出来”为核心叙事，解释制坯、装饰、干燥、入窑烧成等生产流程。',
    highlights: ['陶窑遗址', '火候工艺', '制陶流程'],
  },
  {
    key: 'workshop',
    slug: 'prehistoric-workshop',
    name: '史前工坊',
    shortName: '工坊',
    icon: '🛠️',
    type: '常开放',
    zone: '研学体验',
    floor: 2,
    estimated_duration_minutes: 20,
    display_order: 40,
    description: '把制陶、材料、手作等史前生活知识转化为可参与的互动学习体验。',
    highlights: ['手作体验', '史前工艺', '互动学习'],
  },
  {
    key: 'banpoGirl',
    slug: 'banpo-girl-sculpture',
    name: '半坡姑娘雕塑',
    shortName: '雕塑',
    icon: '🗿',
    type: '常开放',
    zone: '公共空间',
    floor: 1,
    estimated_duration_minutes: 8,
    display_order: 50,
    description: '以“半坡姑娘”为代表形象进行艺术化再现，是观众合影点和半坡人形象记忆入口。',
    highlights: ['人物形象', '文化象征', '观展地标'],
  },
  {
    key: 'education',
    slug: 'education-center',
    name: '教研中心',
    shortName: '教研',
    icon: '📚',
    type: '常开放',
    zone: '研学空间',
    floor: 2,
    estimated_duration_minutes: 18,
    display_order: 60,
    description: '面向青少年和公众教育活动，适合承载研学课程、主题课堂与研究型活动。',
    highlights: ['教育研学', '主题课堂', '公众活动'],
  },
  {
    key: 'peony',
    slug: 'peony-garden',
    name: '牡丹园',
    shortName: '牡丹',
    icon: '🌸',
    type: '常开放',
    zone: '园区空间',
    floor: 3,
    estimated_duration_minutes: 10,
    display_order: 70,
    description: '以牡丹为核心的园林休憩区域，适合在观展间隙停留并体验季节性自然景观。',
    highlights: ['植物景观', '园林休憩', '季节观赏'],
  },
  {
    key: 'temp1',
    slug: 'temporary-hall-1',
    name: '临展厅一',
    shortName: '临展一',
    icon: '🖼️',
    type: '临展',
    zone: '临时展览',
    floor: 3,
    estimated_duration_minutes: 15,
    display_order: 90,
    description: '承载阶段性专题展览，主题和展品随当期策展内容变化。',
    highlights: ['当期专题', '临时展品', '策展主题'],
  },
  {
    key: 'temp2',
    slug: 'temporary-hall-2',
    name: '临展厅二',
    shortName: '临展二',
    icon: '🖼️',
    type: '临展',
    zone: '临时展览',
    floor: 3,
    estimated_duration_minutes: 15,
    display_order: 100,
    description: '与临展厅一共同承担轮换展出，需要按馆方最新展览清单更新内容。',
    highlights: ['轮换展览', '阶段性专题', '馆方更新'],
  },
]

export const BANPO_HALLS_BY_SLUG = Object.fromEntries(BANPO_HALLS.map((hall) => [hall.slug, hall]))
export const BANPO_HALLS_BY_KEY = Object.fromEntries(BANPO_HALLS.map((hall) => [hall.key, hall]))
export const CANONICAL_HALL_SLUGS = new Set(BANPO_HALLS.map((hall) => hall.slug))

export function normalizeHallSlug(value) {
  if (!value) return ''
  return CANONICAL_HALL_SLUGS.has(value) ? value : ''
}

export function isCanonicalHallSlug(value) {
  return CANONICAL_HALL_SLUGS.has(value)
}

export function getHallBySlug(value) {
  return BANPO_HALLS_BY_SLUG[normalizeHallSlug(value)] || null
}

export function getHallDisplayName(value) {
  return getHallBySlug(value)?.name || value || '未选择展厅'
}

export function createHallPayload(hall) {
  return {
    slug: hall.slug,
    name: hall.name,
    description: hall.description,
    floor: hall.floor,
    estimated_duration_minutes: hall.estimated_duration_minutes,
    display_order: hall.display_order,
    is_active: true,
  }
}

export function normalizeHallRecord(record) {
  if (!record) return null
  const rawSlug = record.slug || record.hall || record.hall_slug
  const slug = normalizeHallSlug(rawSlug)
  const contract = BANPO_HALLS_BY_SLUG[slug]
  return {
    ...record,
    slug,
    contract,
    isLegacy: Boolean(rawSlug && rawSlug !== slug),
  }
}

export function mergeHallsWithContract(records = []) {
  const bySlug = new Map()
  for (const item of records) {
    const normalized = normalizeHallRecord(item)
    if (normalized?.slug && !bySlug.has(normalized.slug)) {
      bySlug.set(normalized.slug, normalized)
    }
  }

  return BANPO_HALLS.map((hall) => {
    const backend = bySlug.get(hall.slug)
    return {
      ...hall,
      ...backend,
      slug: hall.slug,
      name: hall.name,
      shortName: hall.shortName,
      icon: hall.icon,
      type: hall.type,
      zone: hall.zone,
      description: hall.description,
      highlights: hall.highlights,
      floor: hall.floor,
      estimated_duration_minutes: backend?.estimated_duration_minutes ?? hall.estimated_duration_minutes,
      display_order: hall.display_order,
      is_active: backend?.is_active ?? true,
      exhibit_count: backend?.exhibit_count ?? 0,
      hasBackend: Boolean(backend),
      contract: hall,
    }
  }).sort((a, b) => a.display_order - b.display_order)
}

export function getLegacyHallRows(records = []) {
  return records
    .filter((item) => {
      const rawSlug = item?.slug || item?.hall || item?.hall_slug
      return rawSlug && !CANONICAL_HALL_SLUGS.has(rawSlug)
    })
    .map((item) => {
      return {
        ...item,
        targetSlug: '',
        targetName: '契约外展厅',
      }
    })
}

export const BANPO_PERSONAS = [
  {
    code: 'A',
    personaId: 'A',
    focusId: 'research',
    name: '考古研究员',
    focusTitle: '证据怎样成史',
    routeTitle: '考古研究路线',
    reportTitle: '半坡考古研究报告',
    color: 'warning',
    prompt: '像研究者一样，看证据、推理和不确定性。',
  },
  {
    code: 'B',
    personaId: 'B',
    focusId: 'study',
    name: '研学记录员',
    focusTitle: '带着任务研学',
    routeTitle: '研学记录路线',
    reportTitle: '半坡研学记录报告',
    color: 'success',
    prompt: '边看边记，把展厅整理成可复盘的笔记。',
  },
  {
    code: 'C',
    personaId: 'C',
    focusId: 'history',
    name: '历史追问者',
    focusTitle: '历史问题追问',
    routeTitle: '历史追问路线',
    reportTitle: '半坡历史追问报告',
    color: 'primary',
    prompt: '把半坡放进更大的史前中国和今天来理解。',
  },
  {
    code: 'D',
    personaId: 'D',
    focusId: 'object-study',
    name: '器物研究员',
    focusTitle: '器物细节观察',
    routeTitle: '器物观察路线',
    reportTitle: '半坡器物观察报告',
    color: 'info',
    prompt: '从材料、器形、纹饰和工艺读懂文物。',
  },
]

export const BANPO_PERSONA_BY_CODE = Object.fromEntries(BANPO_PERSONAS.map((item) => [item.code, item]))

export const BANPO_ASSUMPTIONS = [
  { code: 'A', label: '更像平等互助的共同体' },
  { code: 'B', label: '艰难但有烟火气的生活' },
  { code: 'C', label: '已经出现分工和规则' },
  { code: 'D', label: '先不下判断，跟证据走' },
]

export const BANPO_RHYTHMS = [
  { value: 'notebook', label: '研学记录模式' },
  { value: 'quick', label: '30 分钟抓重点' },
  { value: 'dialogue', label: '1 小时边看边问' },
  { value: 'research', label: '研究深化模式' },
]

function routeStep(slug, title, focus, minutes, reason) {
  const hall = getHallBySlug(slug)
  return {
    order: 0,
    hall_slug: slug,
    hall_name: hall?.name || slug,
    title,
    focus,
    reason,
    minutes,
    estimated_minutes: minutes,
    tags: hall?.highlights?.slice(0, 3) || [],
  }
}

const MINI_PROGRAM_FALLBACK_STEPS = [
  routeStep(
    'basic-exhibition-hall',
    '基本陈列展厅',
    '半坡人、石器工具、彩陶与装饰品。',
    18,
    '先建立半坡文化的基本印象，了解出土遗物、生活方式和考古发现脉络。',
  ),
  routeStep(
    'site-protection-hall',
    '遗址保护大厅',
    '房屋遗迹、墓葬区、制陶区和聚落边界。',
    18,
    '再把器物放回真实遗址空间，观察房屋、墓葬、作坊和公共空间。',
  ),
  routeStep(
    'kiln-hall',
    '陶窑展厅',
    '陶窑结构、烧成痕迹和制陶工艺。',
    14,
    '补上制陶流程，理解陶器从材料、成型到烧制的过程。',
  ),
  routeStep(
    'prehistoric-workshop',
    '史前工坊',
    '手作步骤、材料处理和工艺难点。',
    14,
    '用互动体验把抽象技术转化为可感知的操作过程。',
  ),
  routeStep(
    'banpo-girl-sculpture',
    '半坡姑娘雕塑',
    '人物形象、文化象征和观展记忆点。',
    8,
    '通过公共形象理解半坡遗址如何被今天的人记住和表达。',
  ),
  routeStep(
    'temporary-hall-1',
    '临展厅一',
    '当期主题、展签说明和馆方更新。',
    8,
    '临展内容随馆方主题更新，适合用现场展签确认当期信息。',
  ),
  routeStep(
    'temporary-hall-2',
    '临展厅二',
    '轮换展览、阶段性主题和现场说明。',
    8,
    '继续查看临时展陈，补充当期策展主题中的另一组材料。',
  ),
  routeStep(
    'education-center',
    '教研中心',
    '研学问题、讨论线索和活动信息。',
    8,
    '把前面的观察整理成问题、笔记或复盘提纲。',
  ),
  routeStep(
    'peony-garden',
    '牡丹园',
    '园林休憩、季节景观和参观节奏。',
    6,
    '作为参观间隙的停留点，放慢节奏并整理刚才的观察。',
  ),
].map((step, index) => ({ ...step, order: index + 1 }))

function miniProgramFallbackRoute(persona) {
  return {
    persona,
    title: '小程序本地兜底路线',
    summary: '与小程序 route 页固定 9 站 fallback 完全一致；身份只影响后端 AI plan payload，不改变本地兜底顺序。',
    total_minutes: 102,
    steps: MINI_PROGRAM_FALLBACK_STEPS,
  }
}

export const BANPO_ROUTE_STRATEGIES = {
  A: miniProgramFallbackRoute(BANPO_PERSONA_BY_CODE.A),
  B: miniProgramFallbackRoute(BANPO_PERSONA_BY_CODE.B),
  C: miniProgramFallbackRoute(BANPO_PERSONA_BY_CODE.C),
  D: miniProgramFallbackRoute(BANPO_PERSONA_BY_CODE.D),
}

export const TTS_VOICE_CONTRACT = {
  voice: '冰糖',
  label: '冰糖（美少女声线）',
  description: '清甜明亮，语速自然偏快，停顿短，适合博物馆公共空间的轻声讲解。',
  sample: '这里是半坡遗址。先看眼前这件器物，再判断它能说明什么。',
}

export const BANPO_EXHIBIT_CATEGORIES = [
  { value: 'painted_pottery', label: '彩陶与纹饰' },
  { value: 'pottery', label: '陶器' },
  { value: 'stone_tool', label: '石器工具' },
  { value: 'bone_tool', label: '骨器' },
  { value: 'settlement', label: '聚落遗址' },
  { value: 'burial', label: '墓葬与体质人类学' },
  { value: 'production', label: '生产与工艺' },
  { value: 'symbol', label: '符号与精神文化' },
  { value: 'education', label: '研学体验' },
  { value: 'temporary', label: '临展内容' },
]

export function getCategoryLabel(value) {
  return BANPO_EXHIBIT_CATEGORIES.find((item) => item.value === value)?.label || value || '未分类'
}
