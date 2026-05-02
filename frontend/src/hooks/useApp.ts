/**
 * Ant Design App Hook
 * 提供 App 组件上下文的统一 Hook，用于获取 message, notification, modal 等方法
 */

import { useContext } from 'react'
import { App } from 'antd'
import type { MessageInstance } from 'antd/es/message/interface'
import type { NotificationInstance } from 'antd/es/notification/interface'
import type { ModalStaticFunctions } from 'antd/es/modal/confirm'

export interface UseAppResult {
  message: MessageInstance
  notification: NotificationInstance
  modal: Omit<ModalStaticFunctions, 'warn'>
}

/**
 * 获取 Ant Design App 上下文
 * @returns App 上下文对象，包含 message, notification, modal 等方法
 */
export const useApp = (): UseAppResult => {
  const app = App.useApp()
  return app
}

/**
 * 使用 message 的便捷 Hook
 * @returns MessageInstance message 实例
 */
export const useMessage = (): MessageInstance => {
  const { message } = useApp()
  return message
}

/**
 * 使用 notification 的便捷 Hook
 * @returns NotificationInstance notification 实例
 */
export const useNotification = (): NotificationInstance => {
  const { notification } = useApp()
  return notification
}

/**
 * 使用 modal 的便捷 Hook
 * @returns Modal 实例
 */
export const useModal = (): Omit<ModalStaticFunctions, 'warn'> => {
  const { modal } = useApp()
  return modal
}

export default useApp
