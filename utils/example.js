// utils/example.js - API使用示例
// 这个文件仅用于演示如何使用utils/request.js中的API函数
// 实际项目中请在页面或服务文件中使用这些API

const { apiGet, apiPost, apiUploadImage } = require('./request.js');

/**
 * 示例：获取消防隐患历史记录
 */
async function getHistoryRecords() {
  try {
    // GET请求示例 - 获取历史记录
    const result = await apiGet('/fire-detection/history');
    console.log('历史记录:', result);
    return result;
  } catch (error) {
    console.error('获取历史记录失败:', error.message);
  }
}

/**
 * 示例：获取分页的历史记录
 */
async function getHistoryRecordsWithPagination(page = 1, limit = 10) {
  try {
    // GET请求示例 - 带查询参数
    const result = await apiGet('/fire-detection/history', {
      page: page,
      limit: limit,
      sort: 'desc'
    });
    console.log('分页历史记录:', result);
    return result;
  } catch (error) {
    console.error('获取分页历史记录失败:', error.message);
  }
}

/**
 * 示例：提交图片进行AI分析
 */
async function analyzeImage(imageUrl) {
  try {
    // POST请求示例 - 提交分析请求
    const result = await apiPost('/fire-detection/analyze', {
      imageUrl: imageUrl,
      type: 'fire_hazard',
      priority: 'high'
    });
    console.log('分析结果:', result);
    return result;
  } catch (error) {
    console.error('分析图片失败:', error.message);
  }
}

/**
 * 示例：上传图片文件
 */
async function uploadImageFile(tempFilePath) {
  try {
    // 上传文件示例
    const result = await apiUploadImage('/fire-detection/upload', tempFilePath, {
      type: 'hazard_image',
      description: '消防隐患照片'
    });
    console.log('上传结果:', result);
    return result;
  } catch (error) {
    console.error('上传图片失败:', error.message);
  }
}

/**
 * 示例：在页面中使用API
 * 在result.js页面中替换模拟分析的部分
 */
async function realAnalyzeImage(imageUrl) {
  try {
    // 首先上传图片
    const uploadResult = await apiUploadImage('/fire-detection/upload', imageUrl);

    if (uploadResult.success) {
      // 上传成功后，获取图片URL并进行分析
      const imageId = uploadResult.data.imageId;

      // 发送分析请求
      const analysisResult = await apiPost('/fire-detection/analyze', {
        imageId: imageId,
        analysisType: 'comprehensive'
      });

      console.log('真实分析结果:', analysisResult);
      return analysisResult;
    }
  } catch (error) {
    console.error('真实分析失败:', error.message);
    // 如果网络请求失败，回退到离线模拟模式
    throw error;
  }
}

// 导出示例函数（仅用于测试）
module.exports = {
  getHistoryRecords,
  getHistoryRecordsWithPagination,
  analyzeImage,
  uploadImageFile,
  realAnalyzeImage
};