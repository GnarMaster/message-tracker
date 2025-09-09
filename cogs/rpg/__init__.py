import os
import importlib
from .jobs import JobCog

async def setup(bot):
    # 기본 전직 관련 Cog
    await bot.add_cog(JobCog(bot))

    # skills 폴더 자동 탐색 및 로드
    base_path = os.path.dirname(__file__)
    skills_path = os.path.join(base_path, "skills")

    for root, dirs, files in os.walk(skills_path):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                rel_path = os.path.relpath(os.path.join(root, file), base_path)
                module_name = rel_path.replace(os.sep, ".")[:-3]  # .py 제거
                module_import = f"cogs.rpg.{module_name}"

                try:
                    module = importlib.import_module(module_import)
                    if hasattr(module, "setup"):
                        await module.setup(bot)
                        print(f"✅ Loaded skill: {module_import}")
                except Exception as e:
                    print(f"❗ Failed to load skill {module_import}: {e}")

