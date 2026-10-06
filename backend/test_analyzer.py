#!/usr/bin/env python3
"""
AI 分析器测试脚本
"""
import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    try:
        # 检查环境变量
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("WARNING: 未设置 OPENAI_API_KEY 环境变量，将使用模拟模式")
            use_mock = True
        else:
            print("OK: 找到 OPENAI_API_KEY 环境变量")
            use_mock = False

        # 查找测试图片
        uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
        if not os.path.exists(uploads_dir):
            print("ERROR: uploads directory not found")
            sys.exit(1)

        image_files = [f for f in os.listdir(uploads_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
        if not image_files:
            print("ERROR: no image files found in uploads directory")
            sys.exit(1)

        test_image = os.path.join(uploads_dir, image_files[0])
        print(f"Image: {test_image}")

        # 测试分析功能
        print("Testing image analysis...")

        if use_mock:
            # 使用模拟实现
            print("Using mock analysis mode")

            # 创建模拟分析器
            class MockAnalyzer:
                def analyze_image(self, file_path, scene="campus"):
                    return {
                        "overall_risk": "低",
                        "summary": "模拟分析：该区域消防设施完好，无明显安全隐患。",
                        "items": [
                            {
                                "type": "消防设施完好",
                                "risk": "低",
                                "desc": "消防灭火器、消防栓等设施状态良好",
                                "suggest": "继续保持良好的消防安全习惯"
                            }
                        ]
                    }

            analyzer = MockAnalyzer()
        else:
            # 使用真实OpenAI API
            from app.services.analyzer import analyzer_service as analyzer
            print("Using OpenAI GPT-4 Vision analysis mode")

        # 执行分析
        result = analyzer.analyze_image(test_image, "campus")

        # 显示结果
        print("Analysis Results:")
        print(f"   Overall Risk: {result['overall_risk']}")
        print(f"   Summary: {result['summary']}")
        print(f"   Items Count: {len(result['items'])}")

        if result['items']:
            print("   Hazard Details:")
            for i, item in enumerate(result['items'], 1):
                print(f"     {i}. {item['type']} ({item['risk']}): {item['desc']}")
                if 'suggest' in item:
                    print(f"        Suggestion: {item['suggest']}")

        print("Analyzer test completed!")

        # 显示使用说明
        print("\nUsage Instructions:")
        if use_mock:
            print("   Currently using mock analysis. For real AI analysis, set environment variable:")
            print("   export OPENAI_API_KEY='your-openai-api-key'")
            print("   Then reinstall dependencies: pip install -r requirements.txt")
        else:
            print("   Currently using OpenAI GPT-4 Vision for real AI analysis")
            print("   Please ensure your account has sufficient API credits")

    except ImportError as e:
        print(f"Import failed: {e}")
        print("Please install dependencies: pip install -r requirements.txt")
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()