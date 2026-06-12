"""
星火智造云打印 — 文件存储服务
负责文件的安全保存、读取和清理。
"""

import uuid
import shutil
import logging
from pathlib import Path
from fastapi import UploadFile

from config import settings

logger = logging.getLogger(__name__)

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".png", ".jpg", ".jpeg"}


class FileService:
    """文件持久化管理"""

    @staticmethod
    def is_allowed(filename: str) -> bool:
        """检查文件类型是否在白名单内"""
        ext = Path(filename).suffix.lower()
        return ext in ALLOWED_EXTENSIONS

    @staticmethod
    async def save(upload_file: UploadFile) -> tuple[str, str]:
        """
        将上传文件保存到磁盘

        Args:
            upload_file: FastAPI UploadFile 对象

        Returns:
            (保存后的文件路径, 安全文件名)
            - 文件路径: 供数据库存储
            - 安全文件名: UUID + 原始扩展名

        Raises:
            ValueError: 文件类型不允许
        """
        original_name = upload_file.filename or "untitled"
        ext = Path(original_name).suffix.lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"不支持的文件类型 '{ext}'。允许的类型: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # 生成唯一文件名: {uuid}.{ext}
        safe_name = f"{uuid.uuid4().hex}{ext}"
        save_path = settings.UPLOAD_DIR / safe_name

        # 异步写入文件
        chunk_size = 1024 * 1024  # 1MB 分块
        with open(save_path, "wb") as buffer:
            while chunk := await upload_file.read(chunk_size):
                if len(chunk) == 0:
                    break
                buffer.write(chunk)

        logger.info(f"文件已保存: {save_path} (原文件名: {original_name})")
        return str(save_path), original_name

    @staticmethod
    def delete(file_path: str) -> bool:
        """删除文件 (任务完成或失败后的清理)"""
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                logger.info(f"文件已删除: {file_path}")
                return True
        except Exception as e:
            logger.error(f"删除文件失败: {file_path}, 错误: {e}")
        return False

    @staticmethod
    def get_size_mb(file_path: str) -> float:
        """获取文件大小 (MB)"""
        path = Path(file_path)
        if path.exists():
            return path.stat().st_size / (1024 * 1024)
        return 0.0
