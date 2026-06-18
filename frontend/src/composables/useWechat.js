/**
 * 星火智造云打印 — 微信 JS-SDK 封装
 *
 * 在微信客户端内:
 *   1. 初始化 wx.config → wx.ready
 *   2. wx.chooseImage: 从微信相册 / 聊天图片中选择
 *   3. wx.chooseMessageFile: 从微信聊天中选择文件 (新版 JSSDK 1.6.0+)
 *   4. 返回 File 对象供上传组件使用
 *
 * 非微信环境: 静默跳过, 不显示微信按钮
 */

import { ref, readonly } from 'vue'
import http from './useApi'

// ── 检测是否在微信客户端内 ──
export function isWechat() {
  return /MicroMessenger/i.test(navigator.userAgent)
}

const state = ref({
  ready: false,
  disabled: !isWechat(),
  error: '',
})

let _initPromise = null

/**
 * 初始化微信 JS-SDK
 */
export async function initWechat() {
  if (!isWechat()) {
    state.value.disabled = true
    return
  }

  if (_initPromise) return _initPromise
  _initPromise = _doInit()
  return _initPromise
}

async function _doInit() {
  try {
    // 1. 云端获取签名
    const url = location.href.split('#')[0]
    const { data } = await http.get('/wechat/signature', {
      params: { url: encodeURIComponent(url) },
    })

    if (data.disabled) {
      state.value.disabled = true
      state.value.error = data.message || '微信功能未启用'
      return
    }

    // 2. wx.config
    await new Promise((resolve) => {
      window.wx.config({
        debug: false,
        appId: data.appId,
        timestamp: data.timestamp,
        nonceStr: data.nonceStr,
        signature: data.signature,
        jsApiList: [
          'chooseImage',
          'getLocalImgData',
          'chooseMessageFile',
        ],
      })

      window.wx.ready(() => {
        state.value.ready = true
        resolve()
      })

      window.wx.error((err) => {
        state.value.error = `微信初始化失败: ${err.errMsg || err}`
        resolve()
      })
    })
  } catch (err) {
    state.value.error = `微信签名获取失败: ${err.message || err}`
  }
}

/**
 * 从微信相册/聊天图片中选择图片 → 转为 File 对象
 *
 * 调用 wx.chooseImage → getLocalImgData → base64 → Blob → File
 */
export function chooseWechatImage() {
  if (!state.value.ready) {
    throw new Error('微信 JSSDK 未就绪, 请稍后重试')
  }

  return new Promise((resolve, reject) => {
    window.wx.chooseImage({
      count: 1,
      sizeType: ['original', 'compressed'],
      sourceType: ['album'],    // 微信相册 (含聊天图片)
      success(res) {
        const localIds = res.localIds || []
        if (localIds.length === 0) {
          reject(new Error('未选择图片'))
          return
        }

        const filePromises = localIds.map((localId) =>
          _localImgToFile(localId)
        )

        Promise.all(filePromises)
          .then((files) => {
            const validFiles = files.filter((f) => !!f)
            if (validFiles.length === 0) {
              reject(new Error('图片读取失败'))
            } else {
              resolve(validFiles)
            }
          })
          .catch(reject)
      },
      fail(err) {
        if (err.errMsg && err.errMsg.includes('cancel')) {
          reject(new Error('cancel'))
        } else {
          reject(new Error(`选择图片失败: ${err.errMsg || err}`))
        }
      },
    })
  })
}

/**
 * wx.getLocalImgData → base64 → Blob → File
 */
function _localImgToFile(localId) {
  return new Promise((resolve) => {
    window.wx.getLocalImgData({
      localId,
      success(res) {
        let data = res.localData || ''
        if (!data.startsWith('data:')) {
          data = 'data:image/jpeg;base64,' + data
        }

        const [meta, b64] = data.split(',')
        if (!b64) {
          resolve(null)
          return
        }

        try {
          const mimeMatch = meta.match(/data:(.*?);/)
          const mime = mimeMatch ? mimeMatch[1] : 'image/jpeg'
          const ext = mime.split('/')[1] || 'jpg'
          const bytes = _b64ToBytes(b64)
          const file = new File([bytes], `wechat_${Date.now()}.${ext}`, { type: mime })
          resolve(file)
        } catch {
          resolve(null)
        }
      },
      fail() {
        resolve(null)
      },
    })
  })
}

function _b64ToBytes(b64) {
  const raw = atob(b64)
  const bytes = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) {
    bytes[i] = raw.charCodeAt(i)
  }
  return bytes
}

export const wechatState = readonly(state)
