/**
 * 星火智造云打印 — API 请求封装
 * 统一管理对云后端的 HTTP 请求
 */

import axios from 'axios'
import { API_BASE } from '@/utils/constants'

// 创建 axios 实例
const http = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: {
    'Accept': 'application/json',
  },
})

/**
 * 上传文件 & 提交打印任务
 * @param {File} file - PDF 文件
 * @param {Object} cupsOptions - 打印参数
 * @param {boolean} aiSummary - 是否开启 AI 摘要
 * @returns {Promise<Object>} 服务器响应
 */
export async function uploadPrintJob(file, cupsOptions = {}, aiSummary = false) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('cups_options', JSON.stringify(cupsOptions))
  formData.append('ai_summary', String(aiSummary))

  const { data } = await http.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000, // 上传大文件需要更长超时
  })
  return data
}

/**
 * 查询任务状态
 * @param {string} jobId - 任务 ID
 * @returns {Promise<Object>}
 */
export async function getJobStatus(jobId) {
  const { data } = await http.get(`/jobs/${jobId}/status`)
  return data
}

export default http
