import { storageKeys } from './config.js';

const MAX_HISTORY_COUNT = 50;

export function getLocalHistoryRecords() {
  try {
    const records = wx.getStorageSync(storageKeys.historyRecords);
    return Array.isArray(records) ? records : [];
  } catch (error) {
    console.error('读取本地历史失败', error);
    return [];
  }
}

export function saveLocalHistoryRecords(records) {
  const safeRecords = Array.isArray(records) ? records.slice(0, MAX_HISTORY_COUNT) : [];
  wx.setStorageSync(storageKeys.historyRecords, safeRecords);
  return safeRecords;
}

export function buildHistoryRecord(analysisResult, filePath) {
  const safeAnalysis = analysisResult || {};
  const recordId = safeAnalysis.record_id
    ? String(safeAnalysis.record_id)
    : `local_${Date.now()}`;

  return {
    id: recordId,
    recordId,
    imageUrl: filePath || '',
    annotatedUrl: safeAnalysis.annotated_url || '',
    timestamp: new Date().toISOString(),
    source: 'local',
    analysisResult: {
      overall_risk: safeAnalysis.overall_risk || 'warning',
      summary: safeAnalysis.summary || '',
      items: Array.isArray(safeAnalysis.items) ? safeAnalysis.items : [],
      citations: Array.isArray(safeAnalysis.citations) ? safeAnalysis.citations : []
    }
  };
}

export function upsertHistoryRecord(records, newRecord) {
  const list = Array.isArray(records) ? [...records] : [];
  const key = String((newRecord || {}).id || '');
  if (!key) return list;

  const existingIndex = list.findIndex((item) => String((item || {}).id || '') === key);
  if (existingIndex >= 0) {
    list[existingIndex] = newRecord;
  } else {
    list.unshift(newRecord);
  }
  return list.slice(0, MAX_HISTORY_COUNT);
}

export function saveHistoryRecord(newRecord) {
  const current = getLocalHistoryRecords();
  const updated = upsertHistoryRecord(current, newRecord);
  saveLocalHistoryRecords(updated);
  return updated;
}

export function removeHistoryRecordById(recordId) {
  const key = String(recordId || '');
  if (!key) return getLocalHistoryRecords();

  const current = getLocalHistoryRecords();
  const filtered = current.filter((item) => {
    const safeItem = item || {};
    return String(safeItem.id || safeItem.recordId || '') !== key;
  });
  saveLocalHistoryRecords(filtered);
  return filtered;
}

export function clearHistoryRecords() {
  saveLocalHistoryRecords([]);
  return [];
}

export function mergeHistoryRecords(remoteRecords, localRecords) {
  const map = new Map();
  const merged = [];

  const pushItem = (item) => {
    if (!item) return;
    const id = String(item.id || item.recordId || '');
    if (!id || map.has(id)) return;
    map.set(id, true);
    merged.push(item);
  };

  (remoteRecords || []).forEach(pushItem);
  (localRecords || []).forEach(pushItem);

  merged.sort((a, b) => {
    const ta = new Date(a.timestamp || 0).getTime();
    const tb = new Date(b.timestamp || 0).getTime();
    return tb - ta;
  });

  return merged.slice(0, MAX_HISTORY_COUNT);
}
