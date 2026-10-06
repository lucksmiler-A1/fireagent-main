import { pages, riskLevels, BASE_URL } from '../../utils/config.js';
import { apiGet } from '../../utils/request.js';
import { clearHistoryRecords, getLocalHistoryRecords, mergeHistoryRecords } from '../../utils/history.js';

Page({
  data: {
    records: []
  },

  onShow() {
    this.loadHistoryRecords();
  },

  onPullDownRefresh() {
    this.loadHistoryRecords(function () {
      wx.stopPullDownRefresh();
    });
  },

  loadHistoryRecords(done) {
    const finish = typeof done === 'function' ? done : function () {};
    const localRecords = this.mapLocalRecords(getLocalHistoryRecords());
    this.setData({ records: localRecords });

    apiGet('/records', { limit: 50, offset: 0 })
      .then((result) => {
        const remoteRaw = result && Array.isArray(result.records) ? result.records : [];
        const remoteRecords = this.mapRemoteRecords(remoteRaw);
        const merged = mergeHistoryRecords(remoteRecords, localRecords);
        this.setData({ records: merged });
        finish();
      })
      .catch((error) => {
        console.error('加载历史记录失败', error);
        if (!localRecords.length) {
          wx.showToast({
            title: '历史记录加载失败',
            icon: 'none'
          });
        }
        finish();
      });
  },

  mapLocalRecords(records) {
    return (records || [])
      .map((item) => {
        const safeItem = item || {};
        const analysis = safeItem.analysisResult || {};
        const riskUI = this.getRiskConfig(analysis.overall_risk || 'warning');
        return {
          id: String(safeItem.id || safeItem.recordId || ''),
          imageUrl: this.normalizeImageUrl(safeItem.imageUrl || safeItem.annotatedUrl || ''),
          timestamp: safeItem.timestamp,
          source: 'local',
          analysisResult: {
            overall_risk: analysis.overall_risk || 'warning',
            summary: analysis.summary || '',
            items: analysis.items || []
          },
          riskIcon: riskUI.icon,
          riskText: riskUI.text,
          riskColor: riskUI.color
        };
      })
      .filter((item) => item.id);
  },

  mapRemoteRecords(records) {
    return (records || [])
      .map((item) => {
        const safeItem = item || {};
        const riskUI = this.getRiskConfig(safeItem.overall_risk || 'warning');
        return {
          id: String(safeItem.record_id || ''),
          imageUrl: this.normalizeImageUrl(safeItem.thumbnail_url || ''),
          timestamp: safeItem.created_at,
          source: 'remote',
          analysisResult: {
            overall_risk: safeItem.overall_risk || 'warning',
            summary: safeItem.summary || '',
            items: []
          },
          riskIcon: riskUI.icon,
          riskText: riskUI.text,
          riskColor: riskUI.color
        };
      })
      .filter((item) => item.id);
  },

  onRecordTap(event) {
    const recordId = event.currentTarget.dataset.recordId;
    const source = event.currentTarget.dataset.source || 'remote';
    if (!recordId) return;

    wx.navigateTo({
      url: `${pages.record}?id=${encodeURIComponent(recordId)}&source=${source}`
    });
  },

  formatTime(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diff = now - date;

    if (diff < 60 * 1000) return '刚刚';
    if (diff < 60 * 60 * 1000) return `${Math.floor(diff / (60 * 1000))}分钟前`;
    if (diff < 24 * 60 * 60 * 1000) return `${Math.floor(diff / (60 * 60 * 1000))}小时前`;
    if (diff < 7 * 24 * 60 * 60 * 1000) return `${Math.floor(diff / (24 * 60 * 60 * 1000))}天前`;

    const year = date.getFullYear();
    const month = `${date.getMonth() + 1}`.padStart(2, '0');
    const day = `${date.getDate()}`.padStart(2, '0');
    return `${year}-${month}-${day}`;
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

  onClearHistory() {
    const localRecords = getLocalHistoryRecords();
    if (!localRecords.length) {
      wx.showToast({
        title: '本地历史已为空',
        icon: 'none'
      });
      return;
    }

    wx.showModal({
      title: '清空本地历史',
      content: '仅清空本机保存的历史记录，不影响后端数据库记录。是否继续？',
      confirmColor: '#ee0a24',
      success: (res) => {
        if (!res.confirm) return;
        clearHistoryRecords();
        this.loadHistoryRecords();
        wx.showToast({
          title: '本地历史已清空',
          icon: 'success'
        });
      }
    });
  }
});
