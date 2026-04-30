/**
 * 时间工具函数
 * 提供时间格式化和转换的统一实现
 */

/**
 * 将秒数转换为时间字符串
 * @param seconds - 秒数
 * @param includeHours - 是否包含小时部分（超过1小时自动包含）
 * @returns 格式化的时间字符串，例如 "01:23" 或 "1:23:45"
 */
export function formatSecondsToTime(seconds: number | string, includeHours = false): string {
  // 处理字符串输入
  const numSeconds = typeof seconds === 'string' ? parseFloat(seconds) : seconds

  // 处理无效输入
  if (!numSeconds || numSeconds < 0 || isNaN(numSeconds)) {
    return '00:00'
  }

  const totalSeconds = Math.floor(numSeconds)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const secs = totalSeconds % 60

  // 如果超过1小时或明确要求包含小时，则显示小时
  if (hours > 0 || includeHours) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
  }

  return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

/**
 * 将时间字符串转换为秒数
 * @param time - 时间字符串，格式为 "HH:MM:SS" 或 "MM:SS"
 * @returns 秒数
 * @throws 如果时间格式无效
 */
export function parseTimeToSeconds(time: string): number {
  if (!time || typeof time !== 'string') {
    throw new Error('Invalid time format')
  }

  const parts = time.split(':').map((part) => {
    const num = parseInt(part, 10)
    if (isNaN(num)) {
      throw new Error(`Invalid time part: ${part}`)
    }
    return num
  })

  if (parts.length === 3) {
    // 格式: HH:MM:SS
    return parts[0] * 3600 + parts[1] * 60 + parts[2]
  } else if (parts.length === 2) {
    // 格式: MM:SS
    return parts[0] * 60 + parts[1]
  } else if (parts.length === 1) {
    // 格式: SS
    return parts[0]
  } else {
    throw new Error('Invalid time format. Expected HH:MM:SS, MM:SS, or SS')
  }
}

/**
 * 格式化时间范围
 * @param startTime - 开始时间（秒数）
 * @param endTime - 结束时间（秒数）
 * @returns 格式化的时间范围字符串，例如 "00:00 - 01:23"
 */
export function formatTimeRange(startTime: number | string, endTime: number | string): string {
  return `${formatSecondsToTime(startTime)} - ${formatSecondsToTime(endTime)}`
}

/**
 * 计算时间差（秒）
 * @param startTime - 开始时间（秒数）
 * @param endTime - 结束时间（秒数）
 * @returns 时间差（秒）
 */
export function calculateDuration(startTime: number | string, endTime: number | string): number {
  const start = typeof startTime === 'string' ? parseTimeToSeconds(startTime) : startTime
  const end = typeof endTime === 'string' ? parseTimeToSeconds(endTime) : endTime
  return Math.max(0, end - start)
}

/**
 * 格式化持续时间
 * @param seconds - 持续时间（秒）
 * @returns 格式化的持续时间字符串，例如 "1分23秒" 或 "1小时2分3秒"
 */
export function formatDuration(seconds: number | string): string {
  const numSeconds = typeof seconds === 'string' ? parseFloat(seconds) : seconds

  if (!numSeconds || numSeconds < 0 || isNaN(numSeconds)) {
    return '0秒'
  }

  const totalSeconds = Math.floor(numSeconds)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const secs = totalSeconds % 60

  const parts: string[] = []

  if (hours > 0) {
    parts.push(`${hours}小时`)
  }

  if (minutes > 0) {
    parts.push(`${minutes}分`)
  }

  if (secs > 0 || parts.length === 0) {
    parts.push(`${secs}秒`)
  }

  return parts.join('')
}

/**
 * 获取当前时间戳
 * @returns ISO 8601 格式的时间戳字符串
 */
export function getCurrentTimestamp(): string {
  return new Date().toISOString()
}

/**
 * 格式化日期时间
 * @param dateString - ISO 8601 格式的日期字符串
 * @param format - 格式类型，'full' | 'short' | 'time'
 * @returns 格式化的日期时间字符串
 */
export function formatDateTime(dateString: string, format: 'full' | 'short' | 'time' = 'full'): string {
  const date = new Date(dateString)

  if (isNaN(date.getTime())) {
    return dateString
  }

  const options: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }

  if (format === 'short') {
    options.second = undefined
  } else if (format === 'time') {
    options.year = undefined
    options.month = undefined
    options.day = undefined
  }

  return new Intl.DateTimeFormat('zh-CN', options).format(date)
}

/**
 * 检查时间是否在指定范围内
 * @param targetTime - 目标时间（秒数）
 * @param startTime - 开始时间（秒数）
 * @param endTime - 结束时间（秒数）
 * @returns 是否在范围内
 */
export function isTimeInRange(
  targetTime: number | string,
  startTime: number | string,
  endTime: number | string
): boolean {
  const target = typeof targetTime === 'string' ? parseTimeToSeconds(targetTime) : targetTime
  const start = typeof startTime === 'string' ? parseTimeToSeconds(startTime) : startTime
  const end = typeof endTime === 'string' ? parseTimeToSeconds(endTime) : endTime

  return target >= start && target <= end
}
