import { apiPost } from '../../utils/request.js';

const AGENT_SESSION_STORAGE_KEY = 'fire_agent_session_id_v1';

const SCENES = [
  { label: '校园', value: 'campus' },
  { label: '宿舍', value: 'dormitory' },
  { label: '办公', value: 'office' },
  { label: '仓储', value: 'warehouse' },
  { label: '工业', value: 'industrial' },
  { label: '工地', value: 'construction' }
];

function createMessage(role, content, extra = {}) {
  return {
    id: `${Date.now()}_${Math.random().toString(16).slice(2, 8)}`,
    role,
    content,
    citations: extra.citations || [],
    next_actions: extra.next_actions || [],
    used_tools: extra.used_tools || []
  };
}

Page({
  data: {
    inputValue: '',
    loading: false,
    messages: [],
    sessionId: '',
    scrollIntoView: '',
    sceneOptions: SCENES,
    sceneIndex: 0,
    quickPrompts: [
      '最近的高风险隐患主要是什么？',
      '根据现有记录给我一份整改优先级建议',
      '消防通道堆放杂物违反了哪些规定？',
      '帮我总结近 7 天风险趋势'
    ]
  },

  onLoad() {
    const savedSessionId = wx.getStorageSync(AGENT_SESSION_STORAGE_KEY) || '';
    const welcome = createMessage(
      'assistant',
      '我是这个项目里的消防智能助手。你可以直接问法规依据、历史隐患、趋势分析，或者让我给出整改建议。'
    );
    this.setData({
      sessionId: savedSessionId,
      messages: [welcome],
      scrollIntoView: `msg-${welcome.id}`
    });
  },

  onInput(event) {
    this.setData({
      inputValue: event.detail.value
    });
  },

  onSceneChange(event) {
    this.setData({
      sceneIndex: Number(event.detail.value || 0)
    });
  },

  onTapPrompt(event) {
    const prompt = event.currentTarget.dataset.prompt || '';
    this.setData({
      inputValue: prompt
    });
  },

  buildHistoryPayload(messages) {
    return messages
      .filter((item) => item.role === 'user' || item.role === 'assistant')
      .slice(-6)
      .map((item) => ({
        role: item.role,
        content: item.content
      }));
  },

  async onSend() {
    const text = (this.data.inputValue || '').trim();
    if (!text || this.data.loading) {
      return;
    }

    const userMessage = createMessage('user', text);
    const nextMessages = [...this.data.messages, userMessage];

    this.setData({
      messages: nextMessages,
      inputValue: '',
      loading: true,
      scrollIntoView: `msg-${userMessage.id}`
    });

    try {
      const scene = this.data.sceneOptions[this.data.sceneIndex].value;
      const result = await apiPost('/agent/chat', {
        message: text,
        scene,
        session_id: this.data.sessionId || undefined,
        history: this.buildHistoryPayload(nextMessages)
      });
      const nextSessionId = result.session_id || this.data.sessionId || '';
      if (nextSessionId) {
        wx.setStorageSync(AGENT_SESSION_STORAGE_KEY, nextSessionId);
      }

      const assistantMessage = createMessage('assistant', result.reply || '暂时没有返回内容。', {
        citations: result.citations || [],
        next_actions: result.next_actions || [],
        used_tools: result.used_tools || []
      });

      this.setData({
        sessionId: nextSessionId,
        messages: [...nextMessages, assistantMessage],
        loading: false,
        scrollIntoView: `msg-${assistantMessage.id}`
      });
    } catch (error) {
      const assistantMessage = createMessage(
        'assistant',
        '当前请求失败了。你可以稍后再试，或者先检查后端服务和模型密钥是否可用。'
      );

      this.setData({
        messages: [...nextMessages, assistantMessage],
        loading: false,
        scrollIntoView: `msg-${assistantMessage.id}`
      });
    }
  }
});

