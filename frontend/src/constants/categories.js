/**
 * Shared constants for exhibit categories and halls
 */

// Exhibit categories with display labels
export const EXHIBIT_CATEGORIES = [
  { value: 'bronze', label: '青铜器' },
  { value: 'ceramic', label: '陶瓷' },
  { value: 'painting', label: '书画' },
  { value: 'jade', label: '玉器' },
  { value: 'gold_silver', label: '金银器' },
  { value: 'sculpture', label: '雕塑' }
]

// Category options for select/filter components (includes "All" option)
export const CATEGORY_OPTIONS = [
  { value: null, label: '全部' },
  ...EXHIBIT_CATEGORIES
]

// Hall options with display labels
export const HALL_OPTIONS = [
  { value: null, label: '全部' },
  { value: '1F', label: '一楼展厅' },
  { value: '2F', label: '二楼展厅' },
  { value: '3F', label: '三楼展厅' }
]

// Category values only (for checkbox groups)
export const CATEGORY_VALUES = EXHIBIT_CATEGORIES.map(c => c.value)
