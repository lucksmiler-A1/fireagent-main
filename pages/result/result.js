import { pages, riskLevels } from '../../utils/config.js';
import { apiUploadImage } from '../../utils/request.js';
import { buildHistoryRecord, saveHistoryRecord } from '../../utils/history.js';

Page({
  data: {
    filePath: '',
    imageUrl: '',
    showAnnotated: false,
    analysisResult: null,
    isLoading: false,
    isError: false,
    errorMessage: '',
    loadingTips: [
      '厨房油锅起火不能泼水，应先关火并使用锅盖隔绝空气。',
      '电动车电池不要在楼道或室内充电，避免夜间长时间无人看管。',
      '灭火器遵循“提、拔、握、压”，对准火焰根部喷射。',
      '逃生时优先选择安全出口和疏散楼梯，不要乘坐电梯。',
      '浓烟环境要低姿前进，可用湿毛巾捂住口鼻减少吸入。',
      '插线板避免串联使用，大功率设备不要共用一个排插。',
      '消防通道必须保持畅通，严禁堆放杂物和上锁封堵。'
    ],
    currentTipIndex: 0,
    currentTip: '',
    overallRiskUI: null,
    displayItems: []
  },

  onLoad(options) {
    const safeOptions = options || {};
    if (!safeOptions.filePath) {
      wx.showToast({ title: '缺少图片参数', icon: 'none' });
      setTimeout(() => wx.navigateBack(), 1200);
      return;
    }

    const filePath = decodeURIComponent(safeOptions.filePath);
    this.setData({
      filePath,
      imageUrl: filePath
    });
    this.analyzeImage(filePath);
  },

  onUnload() {
    this.stopLoadingTips();
  },

  onHide() {
    if (this.data.isLoading) this.stopLoadingTips();
  },

  startLoadingTips() {
    this.stopLoadingTips();
    const tips = this.data.loadingTips || [];
    if (!tips.length) return;

    const startIndex = Math.floor(Math.random() * tips.length);
    this.setData({
      currentTipIndex: startIndex,
      currentTip: tips[startIndex]
    });

    this.loadingTipTimer = setInterval(() => {
      const nextIndex = (this.data.currentTipIndex + 1) % tips.length;
      this.setData({
        currentTipIndex: nextIndex,
        currentTip: tips[nextIndex]
      });
    }, 3200);
  },

  stopLoadingTips() {
    if (this.loadingTipTimer) {
      clearInterval(this.loadingTipTimer);
      this.loadingTipTimer = null;
    }
  },

  analyzeImage(filePath) {
    const loadingStartedAt = Date.now();
    this.setData({
      isLoading: true,
      isError: false,
      errorMessage: '',
      analysisResult: null,
      overallRiskUI: null,
      displayItems: []
    });
    this.startLoadingTips();

    apiUploadImage('/analysis/upload', filePath, { scene: 'campus' })
      .then((result) => {
        const delay = Math.max(0, 800 - (Date.now() - loadingStartedAt));
        setTimeout(() => {
          this.stopLoadingTips();
          this.setData({
            analysisResult: result,
            isLoading: false,
            isError: false
          });

          this.prepareResultView(result);

          if (result && result.annotated_url) {
            this.setData({
              showAnnotated: true,
              imageUrl: result.annotated_url
            });
          }

          this.saveCurrentResultToHistory(false);
        }, delay);
      })
      .catch((error) => {
        const delay = Math.max(0, 800 - (Date.now() - loadingStartedAt));
        setTimeout(() => {
          this.stopLoadingTips();
          this.setData({
            isLoading: false,
            isError: true,
            errorMessage: this.getFriendlyErrorMessage(error)
          });
        }, delay);
      });
  },

  getFriendlyErrorMessage(error) {
    const errMsg = error && error.message ? String(error.message) : '';
    const message = errMsg.toLowerCase();
    if (!message) return '识别失败，请稍后重试';
    if (message.includes('upload') || message.includes('file')) return '图片上传失败，请重试';
    if (message.includes('network')) return '网络连接失败，请检查网络后重试';
    if (message.includes('timeout')) return '请求超时，请重试';
    return errMsg || '识别失败，请稍后重试';
  },

  saveCurrentResultToHistory(showToast) {
    if (!this.data.analysisResult) return false;
    try {
      const record = buildHistoryRecord(this.data.analysisResult, this.data.filePath);
      saveHistoryRecord(record);
      if (showToast) {
        wx.showToast({
          title: '已保存到历史',
          icon: 'success'
        });
      }
      return true;
    } catch (error) {
      console.error('保存历史记录失败', error);
      if (showToast) {
        wx.showToast({
          title: '保存失败',
          icon: 'none'
        });
      }
      return false;
    }
  },

  prepareResultView(result) {
    const safeResult = result || {};
    const items = Array.isArray(safeResult.items) ? safeResult.items : [];
    const overall = this.getRiskConfig(safeResult.overall_risk);
    const displayItems = items.map((item) => {
      const safeItem = item || {};
      const riskUI = this.getRiskConfig(safeItem.risk);
      return {
        type: safeItem.type || '',
        desc: safeItem.desc || '',
        suggest: safeItem.suggest || '',
        risk: safeItem.risk || 'warning',
        riskIcon: riskUI.icon,
        riskText: riskUI.text,
        riskColor: riskUI.color
      };
    });

    this.setData({
      overallRiskUI: overall,
      displayItems
    });
  },

  toggleAnnotatedImage() {
    const showAnnotated = this.data.showAnnotated;
    const filePath = this.data.filePath;
    const analysisResult = this.data.analysisResult || {};
    if (!analysisResult.annotated_url) return;

    const nextShowAnnotated = !showAnnotated;
    this.setData({
      showAnnotated: nextShowAnnotated,
      imageUrl: nextShowAnnotated ? analysisResult.annotated_url : filePath
    });
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
    const mapped = riskMapping[riskLevel] || 'warning';
    return riskLevels[mapped] || riskLevels.warning;
  },

  onReChoose() {
    wx.navigateBack();
  },

  onRetry() {
    if (this.data.filePath) this.analyzeImage(this.data.filePath);
  },

  onSaveToHistory() {
    if (!this.saveCurrentResultToHistory(true)) {
      wx.showToast({
        title: '暂无可保存结果',
        icon: 'none'
      });
    }
  },

  onViewHistory() {
    wx.navigateTo({
      url: pages.history
    });
  }
});
