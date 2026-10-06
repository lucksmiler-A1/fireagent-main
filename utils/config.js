export const BASE_URL = 'http://127.0.0.1:8010';
export const API_PREFIX = '/api/v1';

export const storageKeys = {
  historyRecords: 'fire_safety_history_records'
};

export const riskLevels = {
  safe: {
    text: '安全',
    color: '#07c160',
    icon: '✅'
  },
  warning: {
    text: '轻微隐患',
    color: '#ff976a',
    icon: '⚠️'
  },
  danger: {
    text: '严重隐患',
    color: '#ee0a24',
    icon: '🚨'
  }
};

export const pages = {
  upload: '/pages/upload/upload',
  result: '/pages/result/result',
  history: '/pages/history/history',
  record: '/pages/record/record',
  agent: '/pages/agent/agent'
};
