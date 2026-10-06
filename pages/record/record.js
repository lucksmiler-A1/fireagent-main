import { riskLevels, pages, BASE_URL } from '../../utils/config.js';
import { apiGet } from '../../utils/request.js';
import { getLocalHistoryRecords, removeHistoryRecordById } from '../../utils/history.js';

Page({
  data: {
    record: null
  },

  onLoad(options) {
    const safeOptions = options || {};
    const recordId = safeOptions.id ? decodeURIComponent(safeOptions.id) : '';
    const source = safeOptions.source || 'remote';

    if (!recordId) {
      wx.showToast({ title: '缺少记录ID', icon: 'none' });
      setTimeout(() => wx.navigateBack(), 1200);
      return;
    }

    this.loadRecordDetail(recordId, source);
  },

  loadRecordDetail(recordId, source) {
    apiGet(`/records/${recordId}`)
      .then((result) => {
        this.setData({
          record: this.mapApiRecord(result)
        });
      })
      .catch((error) => {
        console.error('后端详情加载失败，尝试本地回退', error);
        const loaded = this.loadLocalRecord(recordId);
        if (!loaded) {
          wx.showToast({
            title: source === 'local' ? '本地记录不存在' : '记录加载失败',
            icon: 'none'
          });
          setTimeout(() => wx.navigateBack(), 1200);
        }
      });
  },

  loadLocalRecord(recordId) {
    const records = getLocalHistoryRecords();
    const target = records.find((item) => {
      const safeItem = item || {};
      return String(safeItem.id || safeItem.recordId || '') === String(recordId);
    });
    if (!target) return false;

    this.setData({
      record: this.mapLocalRecord(target)
    });
    return true;
  },

  mapApiRecord(result) {
    const safeResult = result || {};
    const recordRiskUI = this.getRiskConfig(safeResult.overall_risk || 'warning');
    return {
      id: safeResult.record_id,
      source: 'remote',
      imageUrl: this.normalizeImageUrl(safeResult.annotated_url || safeResult.image_url),
      rawImageUrl: this.normalizeImageUrl(safeResult.image_url),
      annotatedUrl: this.normalizeImageUrl(safeResult.annotated_url || ''),
      timestamp: safeResult.created_at,
      recordRiskIcon: recordRiskUI.icon,
      recordRiskText: recordRiskUI.text,
      recordRiskColor: recordRiskUI.color,
      analysisResult: {
        overall_risk: safeResult.overall_risk,
        summary: safeResult.summary,
        items: (safeResult.items || []).map((item) => {
          const safeItem = item || {};
          const itemRiskUI = this.getRiskConfig(safeItem.risk || 'warning');
          return {
            title: safeItem.type,
            description: safeItem.desc,
            type: safeItem.risk,
            suggest: safeItem.suggest,
            riskIcon: itemRiskUI.icon,
            riskText: itemRiskUI.text
          };
        })
      }
    };
  },

  mapLocalRecord(item) {
    const safeItem = item || {};
    const analysis = safeItem.analysisResult || {};
    const recordRiskUI = this.getRiskConfig(analysis.overall_risk || 'warning');
    return {
      id: String(safeItem.id || safeItem.recordId || ''),
      source: 'local',
      imageUrl: this.normalizeImageUrl(safeItem.annotatedUrl || safeItem.imageUrl || ''),
      rawImageUrl: this.normalizeImageUrl(safeItem.imageUrl || ''),
      annotatedUrl: this.normalizeImageUrl(safeItem.annotatedUrl || ''),
      timestamp: safeItem.timestamp,
      recordRiskIcon: recordRiskUI.icon,
      recordRiskText: recordRiskUI.text,
      recordRiskColor: recordRiskUI.color,
      analysisResult: {
        overall_risk: analysis.overall_risk || 'warning',
        summary: analysis.summary || '',
        items: (analysis.items || []).map((it) => {
          const safeIt = it || {};
          const itemRiskUI = this.getRiskConfig(safeIt.risk || safeIt.type || 'warning');
          return {
            title: safeIt.type || safeIt.title || '隐患',
            description: safeIt.desc || safeIt.description || '',
            type: safeIt.risk || safeIt.type || 'warning',
            suggest: safeIt.suggest || '',
            riskIcon: itemRiskUI.icon,
            riskText: itemRiskUI.text
          };
        })
      }
    };
  },

  getRiskConfig(riskLevel) {
    const riskMapping = {
      safe: 'safe',
      warning: 'warning',
      danger: 'danger',
      low: 'safe',
      medium: 'warning',
      high: 'danger',
      低: 'safe',
      中: 'warning',
      高: 'danger'
    };

    const mappedRisk = riskMapping[riskLevel] || 'warning';
    return riskLevels[mappedRisk] || riskLevels.warning;
  },

  normalizeImageUrl(url) {
    if (!url) return '';
    if (url.startsWith('wxfile://')) return url;
    if (url.startsWith('http://') || url.startsWith('https://')) return url;
    if (url.startsWith('data:')) return url;
    return BASE_URL + url;
  },

  formatTime(isoString) {
    const date = new Date(isoString);
    const year = date.getFullYear();
    const month = `${date.getMonth() + 1}`.padStart(2, '0');
    const day = `${date.getDate()}`.padStart(2, '0');
    const hour = `${date.getHours()}`.padStart(2, '0');
    const minute = `${date.getMinutes()}`.padStart(2, '0');
    return `${year}-${month}-${day} ${hour}:${minute}`;
  },

  onReAnalyze() {
    const record = this.data.record || {};
    const rawImageUrl = record.rawImageUrl || '';
    if (!rawImageUrl) return;

    if (rawImageUrl.startsWith('wxfile://')) {
      wx.navigateTo({
        url: `${pages.result}?filePath=${encodeURIComponent(rawImageUrl)}`
      });
      return;
    }

    wx.downloadFile({
      url: rawImageUrl,
      success: (res) => {
        if (res.statusCode === 200) {
          wx.navigateTo({
            url: `${pages.result}?filePath=${encodeURIComponent(res.tempFilePath)}`
          });
        } else {
          wx.showToast({ title: '下载失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.showToast({ title: '下载失败', icon: 'none' });
      }
    });
  },

  onShare() {
    wx.showActionSheet({
      itemList: ['分享给好友', '保存到相册', '复制链接'],
      success: (res) => {
        const actions = ['分享给好友', '保存到相册', '复制链接'];
        wx.showToast({
          title: `${actions[res.tapIndex]}功能开发中`,
          icon: 'none'
        });
      }
    });
  },

  onDeleteRecord() {
    const record = this.data.record || {};
    const recordId = record.id;
    if (!recordId) return;

    wx.showModal({
      title: '删除记录',
      content: '仅删除本机缓存的该条历史记录，不影响后端数据库记录。是否继续？',
      confirmColor: '#ee0a24',
      success: (res) => {
        if (!res.confirm) return;
        removeHistoryRecordById(recordId);
        wx.showToast({
          title: '本地记录已删除',
          icon: 'success'
        });
        setTimeout(() => wx.navigateBack(), 500);
      }
    });
  }
});
