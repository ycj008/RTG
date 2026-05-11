"""
工具模块：SQLite 数据库操作
管理 ground_truth.db：存储 RTK 手持打点数据和 Z 轴残差补丁。
"""

import sqlite3
import logging
import os
from typing import Optional, List, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class GroundTruthDB:
    """
    RTK 打点数据库。

    表结构：
    - survey_points : RTK 手持打点（贝位中心线、堆场原点等）
    - z_patches     : Z 轴垂直偏差补丁（A 车建图阶段写入）
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # 内部：数据库初始化
    # ------------------------------------------------------------------
    def _init_db(self) -> None:
        """创建数据表（若不存在）。"""
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS survey_points (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    yard_id     TEXT    NOT NULL,
                    point_type  TEXT    NOT NULL,    -- 'origin' | 'bay' | 'magnet'
                    bay_no      INTEGER,             -- 贝位编号（point_type='bay' 时有效）
                    lat         REAL    NOT NULL,    -- WGS84 纬度（°）
                    lon         REAL    NOT NULL,    -- WGS84 经度（°）
                    alt         REAL    NOT NULL,    -- 椭球高（m）
                    local_x     REAL,               -- 堆场坐标 X（米）
                    local_y     REAL,               -- 堆场坐标 Y（米）
                    local_z     REAL,               -- 堆场坐标 Z（米）
                    frame_count INTEGER DEFAULT 10, -- 采样帧数（均值）
                    created_at  TEXT    DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE IF NOT EXISTS z_patches (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    yard_id     TEXT    NOT NULL,
                    bay_no      INTEGER NOT NULL,
                    delta_z     REAL    NOT NULL,   -- Z 轴偏差（米），正=天线偏高
                    created_at  TEXT    DEFAULT (datetime('now','localtime'))
                );
            """)
        logger.info("数据库初始化完成: %s", self.db_path)

    @contextmanager
    def _connect(self):
        """提供安全的数据库连接上下文。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # 打点数据写入 / 读取
    # ------------------------------------------------------------------
    def insert_survey_point(
        self,
        yard_id: str,
        point_type: str,
        lat: float,
        lon: float,
        alt: float,
        bay_no: Optional[int] = None,
        local_x: Optional[float] = None,
        local_y: Optional[float] = None,
        local_z: Optional[float] = None,
        frame_count: int = 10,
    ) -> int:
        """
        插入一条 RTK 打点记录。

        :return: 新插入行的 id
        """
        sql = """
            INSERT INTO survey_points
                (yard_id, point_type, bay_no, lat, lon, alt,
                 local_x, local_y, local_z, frame_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._connect() as conn:
            cur = conn.execute(sql, (
                yard_id, point_type, bay_no, lat, lon, alt,
                local_x, local_y, local_z, frame_count,
            ))
            row_id = cur.lastrowid
        logger.debug("写入打点: yard=%s type=%s bay=%s id=%d",
                     yard_id, point_type, bay_no, row_id)
        return row_id

    def get_survey_points(
        self,
        yard_id: str,
        point_type: Optional[str] = None,
    ) -> List[sqlite3.Row]:
        """
        查询打点记录。

        :param yard_id:    堆场 ID
        :param point_type: 可选过滤类型 'origin' / 'bay' / 'magnet'
        """
        if point_type:
            sql = ("SELECT * FROM survey_points "
                   "WHERE yard_id=? AND point_type=? ORDER BY bay_no")
            params = (yard_id, point_type)
        else:
            sql = "SELECT * FROM survey_points WHERE yard_id=? ORDER BY bay_no"
            params = (yard_id,)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return rows

    # ------------------------------------------------------------------
    # Z 轴残差补丁
    # ------------------------------------------------------------------
    def upsert_z_patch(self, yard_id: str, bay_no: int, delta_z: float) -> None:
        """
        写入或更新某贝位的 Z 轴偏差补丁。

        :param delta_z: 正值表示天线实测高于设计值
        """
        sql = """
            INSERT INTO z_patches (yard_id, bay_no, delta_z)
            VALUES (?, ?, ?)
            ON CONFLICT(yard_id, bay_no) DO UPDATE SET delta_z=excluded.delta_z
        """
        # SQLite ON CONFLICT 需要唯一索引，先建索引
        with self._connect() as conn:
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_z_patches
                ON z_patches(yard_id, bay_no)
            """)
            conn.execute(sql, (yard_id, bay_no, delta_z))
        logger.debug("写入 Z 补丁: yard=%s bay=%d delta_z=%.4f m",
                     yard_id, bay_no, delta_z)

    def get_z_patch(self, yard_id: str, bay_no: int) -> float:
        """
        查询单个贝位的 Z 轴偏差补丁。

        :return: delta_z（米），若无记录返回 0.0
        """
        sql = ("SELECT delta_z FROM z_patches "
               "WHERE yard_id=? AND bay_no=?")
        with self._connect() as conn:
            row = conn.execute(sql, (yard_id, bay_no)).fetchone()
        return float(row["delta_z"]) if row else 0.0

    def get_all_z_patches(self, yard_id: str) -> dict:
        """
        获取某堆场所有贝位的 Z 补丁，返回 {bay_no: delta_z} 字典。
        """
        sql = "SELECT bay_no, delta_z FROM z_patches WHERE yard_id=?"
        with self._connect() as conn:
            rows = conn.execute(sql, (yard_id,)).fetchall()
        return {row["bay_no"]: float(row["delta_z"]) for row in rows}

