// app.js
App({
  onLaunch: function (options) {
    // 小程序启动时的初始化工作
    console.log('小程序启动', options);
  },

  onShow: function (options) {
    // 小程序显示时的操作
    console.log('小程序显示', options);
  },

  onHide: function () {
    // 小程序隐藏时的操作
    console.log('小程序隐藏');
  },

  onError: function (msg) {
    // 小程序发生脚本错误或 API 调用失败时触发
    console.error('小程序错误', msg);
  },

  globalData: {
    // 全局数据
    userInfo: null
  }
});