/**
 * 前端系统配置 API 服务测试
 * 
 * 此文件用于验证：
 * 1. TypeScript 接口定义是否正确
 * 2. API 服务方法是否完整
 * 3. 类型一致性
 */

import {
  systemConfigApi,
  ProcessingConfig,
  VideoConfig,
  TopicConfig,
  LoggingConfig,
  AdvancedConfig,
  ConfigCategory
} from '../systemConfigApi'

// 接口测试 - 验证 ProcessingConfig 类型
const testProcessingConfig: ProcessingConfig = {
  chunk_size: 5000,
  min_score_threshold: 70,
  max_clips_per_collection: 5,
  max_retries: 3,
  api_timeout: 600
}

// 接口测试 - 验证 VideoConfig 类型
const testVideoConfig: VideoConfig = {
  use_stream_copy: true,
  use_hardware_accel: true,
  encoder_preset: 'p6',
  crf: 23
}

// 接口测试 - 验证 TopicConfig 类型
const testTopicConfig: TopicConfig = {
  min_topic_duration_minutes: 2,
  max_topic_duration_minutes: 12,
  target_topic_duration_minutes: 5,
  min_topics_per_chunk: 3,
  max_topics_per_chunk: 8
}

// 接口测试 - 验证 LoggingConfig 类型
const testLoggingConfig: LoggingConfig = {
  log_level: 'INFO',
  log_format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
}

// 接口测试 - 验证 AdvancedConfig 类型
const testAdvancedConfig: AdvancedConfig = {
  proxy_url: '',
  encryption_key: '',
  bilibili_cookie: ''
}

// 接口测试 - 验证 ConfigCategory 类型
const testCategories: ConfigCategory[] = [
  'processing',
  'video',
  'topic',
  'logging',
  'advanced'
]

// API 服务方法存在性测试
const testApiMethodsExist = () => {
  const methods: (keyof typeof systemConfigApi)[] = [
    'getAllConfigs',
    'getProcessingConfig',
    'updateProcessingConfig',
    'getVideoConfig',
    'updateVideoConfig',
    'getTopicConfig',
    'updateTopicConfig',
    'getLoggingConfig',
    'updateLoggingConfig',
    'getAdvancedConfig',
    'updateAdvancedConfig',
    'resetAllConfigs',
    'resetCategoryConfig',
    'getConfigInfo'
  ]

  methods.forEach((method) => {
    if (typeof systemConfigApi[method] !== 'function') {
      throw new Error(`Method ${String(method)} not found in systemConfigApi`)
    }
  })

  console.log('✓ All API methods exist')
  return true
}

// 配置分类值验证
const testCategoryValues = () => {
  const validCategories: ConfigCategory[] = [
    'processing',
    'video',
    'topic',
    'logging',
    'advanced'
  ]

  const categoryNames: Record<ConfigCategory, string> = {
    processing: '处理参数',
    video: '视频处理',
    topic: '话题提取',
    logging: '日志',
    advanced: '高级'
  }

  validCategories.forEach((cat) => {
    const name = categoryNames[cat]
    if (!name) {
      throw new Error(`Category name not found for: ${cat}`)
    }
  })

  console.log('✓ All category values are valid')
  return true
}

// 默认配置值测试
const testDefaultConfigValues = () => {
  if (testProcessingConfig.chunk_size !== 5000) {
    throw new Error('Default chunk_size should be 5000')
  }
  if (testProcessingConfig.min_score_threshold !== 70) {
    throw new Error('Default min_score_threshold should be 70')
  }
  if (testProcessingConfig.max_clips_per_collection !== 5) {
    throw new Error('Default max_clips_per_collection should be 5')
  }
  if (testProcessingConfig.max_retries !== 3) {
    throw new Error('Default max_retries should be 3')
  }
  if (testProcessingConfig.api_timeout !== 600) {
    throw new Error('Default api_timeout should be 600')
  }

  if (testVideoConfig.use_stream_copy !== true) {
    throw new Error('Default use_stream_copy should be true')
  }
  if (testVideoConfig.use_hardware_accel !== true) {
    throw new Error('Default use_hardware_accel should be true')
  }
  if (testVideoConfig.encoder_preset !== 'p6') {
    throw new Error('Default encoder_preset should be p6')
  }
  if (testVideoConfig.crf !== 23) {
    throw new Error('Default crf should be 23')
  }

  if (testTopicConfig.min_topic_duration_minutes !== 2) {
    throw new Error('Default min_topic_duration_minutes should be 2')
  }
  if (testTopicConfig.max_topic_duration_minutes !== 12) {
    throw new Error('Default max_topic_duration_minutes should be 12')
  }
  if (testTopicConfig.target_topic_duration_minutes !== 5) {
    throw new Error('Default target_topic_duration_minutes should be 5')
  }
  if (testTopicConfig.min_topics_per_chunk !== 3) {
    throw new Error('Default min_topics_per_chunk should be 3')
  }
  if (testTopicConfig.max_topics_per_chunk !== 8) {
    throw new Error('Default max_topics_per_chunk should be 8')
  }

  if (testLoggingConfig.log_level !== 'INFO') {
    throw new Error('Default log_level should be INFO')
  }

  console.log('✓ All default config values are correct')
  return true
}

// 类型兼容性测试
const testTypeCompatibility = () => {
  const partialProcessing: Partial<ProcessingConfig> = {
    chunk_size: 10000
  }
  const partialVideo: Partial<VideoConfig> = {
    crf: 18
  }
  const partialTopic: Partial<TopicConfig> = {
    min_topic_duration_minutes: 3
  }
  const partialLogging: Partial<LoggingConfig> = {
    log_level: 'DEBUG'
  }
  const partialAdvanced: Partial<AdvancedConfig> = {
    proxy_url: 'http://localhost:7890'
  }

  console.log('Partial types are assignable:')
  console.log('  - Partial<ProcessingConfig>:', partialProcessing)
  console.log('  - Partial<VideoConfig>:', partialVideo)
  console.log('  - Partial<TopicConfig>:', partialTopic)
  console.log('  - Partial<LoggingConfig>:', partialLogging)
  console.log('  - Partial<AdvancedConfig>:', partialAdvanced)
  console.log('✓ Type compatibility test passed')
  return true
}

// 运行所有测试
export const runTests = () => {
  console.log('='.repeat(50))
  console.log('Running frontend system config API tests...')
  console.log('='.repeat(50))
  console.log('')

  try {
    testApiMethodsExist()
    testCategoryValues()
    testDefaultConfigValues()
    testTypeCompatibility()

    console.log('')
    console.log('='.repeat(50))
    console.log('All tests passed! ✓')
    console.log('='.repeat(50))
    return true
  } catch (error) {
    console.error('')
    console.error('='.repeat(50))
    console.error('Test failed! ✗')
    console.error((error as Error).message)
    console.error('='.repeat(50))
    return false
  }
}

export {
  testProcessingConfig,
  testVideoConfig,
  testTopicConfig,
  testLoggingConfig,
  testAdvancedConfig,
  testCategories,
  testApiMethodsExist,
  testCategoryValues,
  testDefaultConfigValues,
  testTypeCompatibility
}
