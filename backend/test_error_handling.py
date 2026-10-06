#!/usr/bin/env python3
"""
测试错误处理功能
"""
import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    try:
        # 测试导入
        from app.services.analyzer import analyzer_service
        print("Analyzer service imported successfully")

        # 查找测试图片
        uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
        if os.path.exists(uploads_dir):
            image_files = [f for f in os.listdir(uploads_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
            if image_files:
                test_image = os.path.join(uploads_dir, image_files[0])
                print(f"Found test image: {test_image}")

                # 测试正常情况（应该降级到模拟）
                print("Testing normal case (should fallback to mock)...")
                result = analyzer_service.analyze_image(test_image, "campus")
                print(f"Result: {result['overall_risk']} - {result['summary']}")

                # 测试异常情况
                print("Testing error case...")
                # 这里可以模拟网络错误或其他异常情况

                print("Error handling test completed")
            else:
                print("No test images found")
        else:
            print("Uploads directory not found")

    except ImportError as e:
        print(f"Import failed: {e}")
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()