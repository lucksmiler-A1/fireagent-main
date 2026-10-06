// utils/request.js - 统一的网络请求封装工具

import { BASE_URL, API_PREFIX } from './config.js';

/**
 * 构建完整的API URL
 * @param {string} path API路径（不包含BASE_URL和API_PREFIX）
 * @returns {string} 完整的URL
 */
function buildApiUrl(path) {
  // 确保path以/开头
  const normalizedPath = path.startsWith('/') ? path : '/' + path;
  return BASE_URL + API_PREFIX + normalizedPath;
}

/**
 * 处理请求错误，显示toast提示并抛出错误
 * @param {string} message 错误消息
 * @param {Error} error 原始错误对象
 */
function handleRequestError(message, error = null) {
  wx.showToast({
    title: message,
    icon: 'none',
    duration: 2000
  });
  throw new Error(message);
}

/**
 * GET请求 - 获取数据
 * @param {string} path API路径（相对于API_PREFIX）
 * @param {Object} params 查询参数对象
 * @returns {Promise<Object>} 解析后的JSON响应数据
 *
 * 使用示例：
 * const result = await apiGet('/fire-detection/history');
 * const result = await apiGet('/fire-detection/history', { page: 1, limit: 10 });
 */
function apiGet(path, params = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: buildApiUrl(path),
      method: 'GET',
      data: params,
      header: {
        'Content-Type': 'application/json'
      },
      success: (res) => {
        // 检查HTTP状态码
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            resolve(res.data);
          } catch (error) {
            handleRequestError('响应数据格式错误');
          }
        } else {
          handleRequestError(`请求失败 (${res.statusCode})`);
        }
      },
      fail: (err) => {
        console.error('网络请求失败:', err);
        handleRequestError('网络连接失败，请检查网络设置');
      }
    });
  });
}

/**
 * POST请求 - 提交数据
 * @param {string} path API路径（相对于API_PREFIX）
 * @param {Object} data 请求体数据对象
 * @returns {Promise<Object>} 解析后的JSON响应数据
 *
 * 使用示例：
 * const result = await apiPost('/fire-detection/analyze', { imageUrl: '...' });
 * const result = await apiPost('/user/login', { username: 'admin', password: '123456' });
 */
function apiPost(path, data = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: buildApiUrl(path),
      method: 'POST',
      data: data,
      header: {
        'Content-Type': 'application/json'
      },
      success: (res) => {
        // 检查HTTP状态码
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            resolve(res.data);
          } catch (error) {
            handleRequestError('响应数据格式错误');
          }
        } else {
          handleRequestError(`请求失败 (${res.statusCode})`);
        }
      },
      fail: (err) => {
        console.error('网络请求失败:', err);
        handleRequestError('网络连接失败，请检查网络设置');
      }
    });
  });
}

/**
 * 上传图片文件
 * @param {string} path API路径（相对于API_PREFIX）
 * @param {string} filePath 本地文件路径（通过wx.chooseImage获取的tempFilePath）
 * @param {Object} formData 额外的表单数据对象
 * @returns {Promise<Object>} 解析后的JSON响应数据
 *
 * 使用示例：
 * const result = await apiUploadImage('/fire-detection/upload', tempFilePath);
 * const result = await apiUploadImage('/fire-detection/upload', tempFilePath, { type: 'fire' });
 */
function apiUploadImage(path, filePath, formData = {}) {
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: buildApiUrl(path),
      filePath: filePath,
      name: 'file',  // 固定字段名
      formData: formData,
      timeout: 60000,  // 60秒超时
      success: (res) => {
        // 检查HTTP状态码
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            const data = JSON.parse(res.data);
            resolve(data);
          } catch (error) {
            handleRequestError('响应数据格式错误');
          }
        } else {
          handleRequestError(`上传失败 (${res.statusCode})`);
        }
      },
      fail: (err) => {
        console.error('文件上传失败:', err);
        handleRequestError('文件上传失败，请重试');
      }
    });
  });
}

// 导出统一的API接口
export {
  apiGet,
  apiPost,
  apiUploadImage
};