"""
星火智造云打印 — 二维码生成工具
为每个打印机节点生成唯一二维码，用户扫码后进入手机上传页面。
"""

import logging
import io
from pathlib import Path
from typing import Optional

import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import SolidFillColorMask
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer

from config import settings

logger = logging.getLogger(__name__)


def generate_node_qrcode(
    node_id: str,
    frontend_base_url: str = "https://starfire.example.com",
    save_path: Optional[str] = None,
) -> str:
    """
    为指定打印机节点生成二维码图片

    Args:
        node_id:   打印机节点 ID
        frontend_base_url: 前端部署地址
        save_path: 保存路径 (默认保存到 uploads/qrcodes/)

    Returns:
        生成的二维码图片路径

    使用示例:
        >>> path = generate_node_qrcode("abc123", "https://print.mycompany.com")
        >>> print(path)
        uploads/qrcodes/node_abc123.png
    """
    # 二维码内容: 前端 URL + 节点 ID 参数
    qr_content = f"{frontend_base_url}/#/?node={node_id}"

    # 创建 QR 码实例
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_content)
    qr.make(fit=True)

    # 生成图片 (使用圆角样式)
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=SolidFillColorMask(
            back_color=(255, 255, 255),
            front_color=(30, 64, 175),  # 深蓝色
        ),
    )

    # 保存
    if save_path is None:
        save_dir = settings.UPLOAD_DIR / "qrcodes"
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / f"node_{node_id}.png"

    img.save(save_path)
    logger.info(f"节点 {node_id} 二维码已生成: {save_path}")

    return str(save_path)
