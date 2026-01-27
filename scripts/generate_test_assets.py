"""生成测试资源文件脚本

使用方法：
    uv run python scripts/generate_test_assets.py

功能：
    - 生成所有测试所需的图片和音频文件
    - 保存到 test_assets/ 目录
    - 适合初始化项目或 CI/CD 环境
"""

from pathlib import Path

from llm_spec.core.config import PROJECT_ROOT
from llm_spec.providers.openai import OpenAIClient


def main():
    """生成所有测试资源"""
    print("开始生成测试资源...")

    # 初始化 OpenAI 客户端
    client = OpenAIClient()

    # 创建目录
    images_dir = PROJECT_ROOT / "test_assets/images"
    audio_dir = PROJECT_ROOT / "test_assets/audio"
    images_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)

    # 1. 生成测试图片
    print("\n1. 生成测试图片 (test_base.png)...")
    test_image_path = images_dir / "test_base.png"
    if test_image_path.exists():
        print(f"   已存在，跳过")
    else:
        from PIL import Image
        import io

        image_bytes, _ = client.generate_image(
            prompt="A simple white square on black background",
            model="dall-e-2",
            n=1,
            size="256x256",
        )

        # 转换为 RGBA 格式 (image edit API 要求)
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGBA")
        img.save(test_image_path, "PNG")
        print(f"   已生成: {test_image_path} (RGBA format)")

    # 2. 生成英文音频
    print("\n2. 生成英文音频 (hello_en.mp3)...")
    audio_en_path = audio_dir / "hello_en.mp3"
    if audio_en_path.exists():
        print(f"   已存在，跳过")
    else:
        audio_data, _ = client.validate_speech(
            input_text="Hello, this is a test of the emergency broadcast system.",
            model="gpt-4o-mini-tts",
            voice="alloy",
        )
        audio_en_path.write_bytes(audio_data)
        print(f"   已生成: {audio_en_path}")

    # 3. 生成中文音频
    print("\n3. 生成中文音频 (hello_zh.mp3)...")
    audio_zh_path = audio_dir / "hello_zh.mp3"
    if audio_zh_path.exists():
        print(f"   已存在，跳过")
    else:
        audio_data, _ = client.validate_speech(
            input_text="你好，这是一个测试。",
            model="gpt-4o-mini-tts",
            voice="alloy",
        )
        audio_zh_path.write_bytes(audio_data)
        print(f"   已生成: {audio_zh_path}")

    # 打印摘要
    print("\n" + "=" * 60)
    print("资源生成完成！")
    print(f"总文件数: {len(list((PROJECT_ROOT / 'test_assets').rglob('*.*')))}")
    print(
        f"总大小: {sum(f.stat().st_size for f in (PROJECT_ROOT / 'test_assets').rglob('*.*')) / 1024:.2f} KB"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
