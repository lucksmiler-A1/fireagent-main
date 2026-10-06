// pages/upload/upload.js
import { pages } from '../../utils/config.js';

Page({
  data: {
    selectedImage: null,      // 选中的图片信息 {filePath, tempFilePath}
    showPreview: false,       // 是否显示预览
    isAnalyzing: false        // 是否正在分析中
  },

  /**
   * 页面加载完成
   */
  onLoad: function (options) {
    console.log('upload页面加载');
  },

  /**
   * 页面显示时
   */
  onShow: function () {
    console.log('upload页面显示');
  },

  /**
   * 检查并请求权限
   * @param {string} scope - 权限类型 ('scope.camera' 或 'scope.writePhotosAlbum')
   * @returns {Promise<boolean>} 是否有权限
   */
  checkPermission: function (scope) {
    return new Promise((resolve) => {
      wx.getSetting({
        success: (res) => {
          if (res.authSetting[scope] === undefined) {
            // 首次请求权限
            wx.authorize({
              scope: scope,
              success: () => resolve(true),
              fail: () => {
                // 用户拒绝授权，引导用户手动开启
                this.showPermissionGuide(scope);
                resolve(false);
              }
            });
          } else if (res.authSetting[scope] === true) {
            // 已授权
            resolve(true);
          } else {
            // 已拒绝，引导用户手动开启
            this.showPermissionGuide(scope);
            resolve(false);
          }
        },
        fail: () => resolve(false)
      });
    });
  },

  /**
   * 显示权限引导提示
   * @param {string} scope - 权限类型
   */
  showPermissionGuide: function (scope) {
    let title = '权限被拒绝';
    let content = '';

    if (scope === 'scope.camera') {
      title = '需要相机权限';
      content = '请在设置中开启相机权限，以便拍照识别消防隐患';
    } else if (scope === 'scope.writePhotosAlbum') {
      title = '需要相册权限';
      content = '请在设置中开启相册权限，以便选择图片进行识别';
    }

    wx.showModal({
      title: title,
      content: content,
      showCancel: true,
      confirmText: '去设置',
      success: (res) => {
        if (res.confirm) {
          wx.openSetting();
        }
      }
    });
  },

  /**
   * 点击拍照/选图按钮
   * 先检查权限，然后选择图片
   */
  onChooseImage: function () {
    // 检查相机和相册权限
    Promise.all([
      this.checkPermission('scope.camera'),
      this.checkPermission('scope.writePhotosAlbum')
    ]).then((results) => {
      const [cameraGranted, albumGranted] = results;

      if (!cameraGranted && !albumGranted) {
        wx.showToast({
          title: '需要相机或相册权限',
          icon: 'none',
          duration: 2000
        });
        return;
      }

      // 构建sourceType数组
      const sourceType = [];
      if (cameraGranted) sourceType.push('camera');
      if (albumGranted) sourceType.push('album');

      // 选择图片
      wx.chooseImage({
        count: 1,
        sizeType: ['original', 'compressed'],
        sourceType: sourceType,
        success: (res) => {
          console.log('选择图片成功', res);
          const tempFilePath = res.tempFilePaths[0];

          // 更新页面状态，显示预览
          this.setData({
            selectedImage: {
              filePath: tempFilePath,
              tempFilePath: tempFilePath
            },
            showPreview: true
          });
        },
        fail: (err) => {
          console.error('选择图片失败', err);
          if (err.errMsg !== 'chooseImage:fail cancel') {
            wx.showToast({
              title: '选择图片失败',
              icon: 'none',
              duration: 2000
            });
          }
        }
      });
    });
  },

  /**
   * 点击示例图片按钮
   * 使用示例图片进行演示
   */
  onUseDemoImage: function () {
    // 优先使用本地示例图片，然后使用网络图片
    const localDemoPath = '/assets/demo.jpg';
    const networkDemoUrl = 'https://via.placeholder.com/400x300/ff6b35/ffffff?text=消防隐患+示例图片';

    // 尝试访问本地文件
    wx.getFileSystemManager().access({
      path: localDemoPath,
      success: () => {
        // 本地文件存在，使用本地图片
        console.log('使用本地示例图片');
        this.setData({
          selectedImage: {
            filePath: localDemoPath,
            tempFilePath: localDemoPath
          },
          showPreview: true
        });
      },
      fail: () => {
        // 本地文件不存在，使用网络示例图片
        console.log('使用网络示例图片');
        wx.showToast({
          title: '使用网络示例图片',
          icon: 'none',
          duration: 1500
        });

        this.setData({
          selectedImage: {
            filePath: networkDemoUrl,
            tempFilePath: networkDemoUrl
          },
          showPreview: true
        });
      }
    });
  },

  /**
   * 点击开始分析按钮
   * 跳转到result页面进行分析
   */
  onStartAnalysis: function () {
    if (!this.data.selectedImage) {
      wx.showToast({
        title: '请先选择图片',
        icon: 'none'
      });
      return;
    }

    if (this.data.isAnalyzing) {
      return; // 防止重复点击
    }

    this.setData({
      isAnalyzing: true
    });

    // 跳转到result页面，传递文件路径
    wx.navigateTo({
      url: pages.result + '?filePath=' + encodeURIComponent(this.data.selectedImage.filePath),
      success: () => {
        // 重置状态
        this.setData({
          selectedImage: null,
          showPreview: false,
          isAnalyzing: false
        });
      },
      fail: () => {
        this.setData({
          isAnalyzing: false
        });
        wx.showToast({
          title: '跳转失败',
          icon: 'none'
        });
      }
    });
  },

  /**
   * 重新选择图片
   */
  onReChooseImage: function () {
    this.setData({
      selectedImage: null,
      showPreview: false
    });
  },

  /**
   * 点击查看历史按钮
   * 跳转到history页面
   */
  onViewHistory: function () {
    wx.navigateTo({
      url: pages.history
    });
  },

  onOpenAgent: function () {
    wx.navigateTo({
      url: pages.agent
    });
  }
});
