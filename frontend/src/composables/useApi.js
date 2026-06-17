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
 * @param {string|null} nodeId - 目标节点 ID
 * @param {Function|null} onProgress - 进度回调 (percentage: number)
 * @returns {Promise<Object>} 服务器响应
 */
export async function uploadPrintJob(
  file,
  cupsOptions = {},
  aiSummary = false,
  nodeId = null,
  onProgress = null,
) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('cups_options', JSON.stringify(cupsOptions))
  formData.append('ai_summary', String(aiSummary))
  if (nodeId) {
    formData.append('node_id', nodeId)
  }

  const { data } = await http.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
    onUploadProgress: onProgress
      ? (event) => {
          const pct = event.total ? Math.round((event.loaded / event.total) * 100) : 0
          onProgress(pct)
        }
      : undefined,
  })
  return data
}

/**
 * 查询任务列表
 * @param {string|null} nodeId - 筛选节点 ID
 * @param {number} limit - 每页数量
 * @param {number} offset - 偏移量
 * @returns {Promise<Array>}
 */
export async function listJobs(nodeId = null, limit = 50, offset = 0) {
  const params = { limit, offset }
  if (nodeId) params.node_id = nodeId
  const { data } = await http.get('/jobs', { params })
  return Array.isArray(data) ? data : []
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

/**
 * 提交 Markdown 文本打印
 * @param {string} content - Markdown 文本内容
 * @param {Object} cupsOptions - 打印参数
 * @param {boolean} aiSummary - 是否开启 AI 摘要
 * @param {string|null} nodeId - 目标节点 ID
 * @returns {Promise<Object>} 服务器响应
 */
export async function uploadText(content, cupsOptions = {}, aiSummary = false, nodeId = null) {
  const { data } = await http.post('/text', {
    content,
    cups_options: cupsOptions,
    ai_summary: aiSummary,
    node_id: nodeId || undefined,
  }, {
    timeout: 60000,
  })
  return data
}

/**
 * 预览打印效果 — 将文件按打印参数生成预览 PDF
 * @param {File} file - PDF 文件
 * @param {Object} cupsOptions - 打印参数
 * @returns {Promise<string>} 预览 PDF 的 blob URL
 */
export async function previewFile(file, cupsOptions = {}) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('cups_options', JSON.stringify(cupsOptions))

  const resp = await http.post('/preview', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    responseType: 'blob',
    timeout: 120000,
  })
  const blob = await _ensurePdfBlob(resp.data)
  return URL.createObjectURL(blob)
}

/**
 * 预览打印效果 — 将文本按打印参数生成预览 PDF
 * @param {string} content - Markdown 文本
 * @param {Object} cupsOptions - 打印参数
 * @returns {Promise<string>} 预览 PDF 的 blob URL
 */
export async function previewText(content, cupsOptions = {}) {
  const formData = new FormData()
  formData.append('text_content', content)
  formData.append('cups_options', JSON.stringify(cupsOptions))

  const resp = await http.post('/preview', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    responseType: 'blob',
    timeout: 60000,
  })
  const blob = await _ensurePdfBlob(resp.data)
  return URL.createObjectURL(blob)
}

/**
 * 验证 blob 是否为有效 PDF，如果服务器返回了错误信息则抛出
 * @param {Blob} blob
 * @returns {Promise<Blob>}
 */
async function _ensurePdfBlob(blob) {
  // PDF 文件必须以 %PDF 开头
  const header = await blob.slice(0, 5).text()
  if (header.startsWith('%PDF')) {
    return blob
  }
  // 不是 PDF — 可能是服务器返回的错误信息 (HTML/JSON)
  const errorText = await blob.text()
  // 尝试解析 JSON 错误
  try {
    const err = JSON.parse(errorText)
    throw new Error(err.detail || err.message || '预览生成失败')
  } catch (parseErr) {
    // HTML 错误页面或纯文本
    throw new Error(errorText.slice(0, 200) || '预览生成失败 (服务器错误)')
  }
}

/**
 * 从 DOCX/TXT 提取纯文本（仅提取，不创建打印任务）
 * @param {File} file - DOCX/TXT 文件
 * @returns {Promise<{text: string, filename: string}>}
 */
export async function extractText(file) {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await http.post('/extract', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000,
  })
  return data
}

export default http
