"""
数据迁移脚本
将 backend/data 目录下的数据迁移到项目根目录的 data 目录
"""

import shutil
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def migrate_data_to_root():
    """将 backend/data 迁移到项目根目录的 data 目录"""

    # 获取路径
    backend_dir = Path(__file__).parent.parent  # backend/
    project_root = backend_dir.parent  # 项目根目录

    legacy_data_dir = backend_dir / "data"  # backend/data
    target_data_dir = project_root / "data"  # data

    logger.info(f"项目根目录: {project_root}")
    logger.info(f"旧数据目录: {legacy_data_dir}")
    logger.info(f"目标数据目录: {target_data_dir}")

    if not legacy_data_dir.exists():
        logger.info("✅ 未发现旧数据目录，无需迁移")
        return

    # 确保目标目录存在
    target_data_dir.mkdir(parents=True, exist_ok=True)

    # 迁移项目数据
    legacy_projects = legacy_data_dir / "projects"
    target_projects = target_data_dir / "projects"

    if legacy_projects.exists():
        logger.info(f"\n📁 迁移项目数据...")
        target_projects.mkdir(parents=True, exist_ok=True)

        for project_dir in legacy_projects.iterdir():
            if project_dir.is_dir():
                target_project = target_projects / project_dir.name
                if target_project.exists():
                    logger.warning(f"  ⚠️  目标项目目录已存在，跳过: {project_dir.name}")
                else:
                    shutil.copytree(project_dir, target_project)
                    logger.info(f"  ✅ 已迁移项目: {project_dir.name}")

    # 迁移数据库文件
    legacy_db = legacy_data_dir / "autoclip.db"
    target_db = target_data_dir / "autoclip.db"

    if legacy_db.exists():
        logger.info(f"\n💾 迁移数据库文件...")
        if target_db.exists():
            # 比较文件大小
            legacy_size = legacy_db.stat().st_size
            target_size = target_db.stat().st_size

            if legacy_size > target_size:
                logger.warning(f"  ⚠️  旧数据库文件更大 ({legacy_size} > {target_size})，备份后替换")
                backup_db = target_db.with_suffix('.db.backup')
                shutil.copy2(target_db, backup_db)
                shutil.copy2(legacy_db, target_db)
                logger.info(f"  ✅ 数据库已更新，备份保存为: {backup_db.name}")
            else:
                logger.info(f"  ℹ️  目标数据库已是最新，跳过")
        else:
            shutil.copy2(legacy_db, target_db)
            logger.info(f"  ✅ 数据库已迁移")

    # 迁移临时文件
    legacy_temp = legacy_data_dir / "temp"
    target_temp = target_data_dir / "temp"

    if legacy_temp.exists():
        logger.info(f"\n🗑️  清理临时文件...")
        try:
            shutil.rmtree(legacy_temp)
            logger.info(f"  ✅ 已清理旧临时目录")
        except Exception as e:
            logger.error(f"  ❌ 清理临时目录失败: {e}")

    # 迁移其他文件
    logger.info(f"\n📦 检查其他文件...")
    for item in legacy_data_dir.iterdir():
        if item.name in ["projects", "autoclip.db", "temp"]:
            continue

        target_item = target_data_dir / item.name
        if target_item.exists():
            logger.warning(f"  ⚠️  目标文件已存在，跳过: {item.name}")
        else:
            if item.is_file():
                shutil.copy2(item, target_item)
                logger.info(f"  ✅ 已迁移文件: {item.name}")
            elif item.is_dir():
                shutil.copytree(item, target_item)
                logger.info(f"  ✅ 已迁移目录: {item.name}")

    # 询问是否删除旧目录
    logger.info(f"\n" + "=" * 60)
    logger.info(f"迁移完成！")
    logger.info(f"=" * 60)
    logger.info(f"\n旧数据目录仍然保留在: {legacy_data_dir}")
    logger.info(f"如需删除，请手动执行:")
    logger.info(f"  rm -rf {legacy_data_dir}")
    logger.info(f"\n或者运行以下Python代码:")
    logger.info(f'  import shutil; shutil.rmtree(r"{legacy_data_dir}")')


if __name__ == "__main__":
    print("=" * 60)
    print("AutoClip 数据迁移工具")
    print("=" * 60)
    print()

    try:
        migrate_data_to_root()
    except Exception as e:
        logger.error(f"\n❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
