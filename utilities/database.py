#!/usr/bin/env python3
"""
Database Module for Historical Data Storage
PostgreSQL for long-term analytics, Redis for real-time state
"""

import logging
from datetime import datetime
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manage PostgreSQL database for historical person tracking data
    Fallback to SQLite if PostgreSQL unavailable
    """

    def __init__(self, use_postgres=True, postgres_url=None):
        """
        Initialize database manager

        Args:
            use_postgres: Try to use PostgreSQL
            postgres_url: PostgreSQL connection string
                         Format: postgresql://user:pass@host:port/dbname
        """
        self.engine = None
        self.using_postgres = False

        # Try PostgreSQL first
        if use_postgres:
            try:
                from sqlalchemy import create_engine

                if postgres_url is None:
                    postgres_url = 'postgresql://postgres:postgres@localhost:5432/person_tracking'

                self.engine = create_engine(
                    postgres_url,
                    pool_pre_ping=True,
                    connect_args={'connect_timeout': 3}
                )

                # Test connection
                with self.engine.connect() as conn:
                    conn.execute("SELECT 1")

                self.using_postgres = True
                logger.info(f"✅ Database: PostgreSQL connected")

            except Exception as e:
                logger.warning(f"⚠️  PostgreSQL unavailable: {e}")
                logger.info("   Using SQLite instead")

        # Fallback to SQLite
        if not self.using_postgres:
            try:
                from sqlalchemy import create_engine

                db_path = Path('data/person_tracking.db')
                db_path.parent.mkdir(parents=True, exist_ok=True)

                self.engine = create_engine(f'sqlite:///{db_path}')
                logger.info(f"✅ Database: SQLite ({db_path})")

            except Exception as e:
                logger.error(f"❌ Database init failed: {e}")
                return

        # Create tables
        self._create_tables()

    def _create_tables(self):
        """Create database tables"""
        if self.engine is None:
            return

        from sqlalchemy import text

        # Persons table
        persons_table = """
        CREATE TABLE IF NOT EXISTS persons (
            id SERIAL PRIMARY KEY,
            person_id INTEGER NOT NULL,
            camera_id VARCHAR(50) NOT NULL,
            first_seen TIMESTAMP NOT NULL,
            last_seen TIMESTAMP,
            seen_count INTEGER DEFAULT 1,
            image_path VARCHAR(500),
            confidence FLOAT,
            detection_quality FLOAT,
            embedding_stored BOOLEAN DEFAULT FALSE,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(person_id, camera_id, DATE(first_seen))
        );
        """

        # Events table (detailed tracking)
        events_table = """
        CREATE TABLE IF NOT EXISTS tracking_events (
            id SERIAL PRIMARY KEY,
            person_id INTEGER NOT NULL,
            camera_id VARCHAR(50) NOT NULL,
            event_type VARCHAR(50) NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            bbox_x1 FLOAT,
            bbox_y1 FLOAT,
            bbox_x2 FLOAT,
            bbox_y2 FLOAT,
            confidence FLOAT,
            track_id INTEGER,
            camera_motion_detected BOOLEAN DEFAULT FALSE,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

        # Camera stats table
        camera_stats_table = """
        CREATE TABLE IF NOT EXISTS camera_stats (
            id SERIAL PRIMARY KEY,
            camera_id VARCHAR(50) NOT NULL,
            date DATE NOT NULL,
            total_unique INTEGER DEFAULT 0,
            max_density INTEGER DEFAULT 0,
            avg_fps FLOAT,
            uptime_seconds INTEGER,
            detections_count INTEGER DEFAULT 0,
            tracking_errors INTEGER DEFAULT 0,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(camera_id, date)
        );
        """

        # Indices
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_persons_camera_date ON persons(camera_id, DATE(first_seen));",
            "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON tracking_events(timestamp);",
            "CREATE INDEX IF NOT EXISTS idx_events_camera ON tracking_events(camera_id);",
            "CREATE INDEX IF NOT EXISTS idx_stats_camera_date ON camera_stats(camera_id, date);"
        ]

        try:
            with self.engine.connect() as conn:
                # For SQLite, convert SERIAL to INTEGER and JSONB to TEXT
                if not self.using_postgres:
                    persons_table = persons_table.replace('SERIAL', 'INTEGER').replace('JSONB', 'TEXT')
                    events_table = events_table.replace('SERIAL', 'INTEGER').replace('JSONB', 'TEXT')
                    camera_stats_table = camera_stats_table.replace('SERIAL', 'INTEGER').replace('JSONB', 'TEXT')

                conn.execute(text(persons_table))
                conn.execute(text(events_table))
                conn.execute(text(camera_stats_table))

                for idx in indices:
                    try:
                        conn.execute(text(idx))
                    except:
                        pass  # Index may already exist

                conn.commit()

            logger.info("✅ Database tables created/verified")

        except Exception as e:
            logger.error(f"❌ Table creation failed: {e}")

    def insert_person(self, person_id, camera_id, metadata):
        """
        Insert or update person record

        Args:
            person_id: Unique person ID
            camera_id: Camera identifier
            metadata: Dict with person info
        """
        if self.engine is None:
            return

        from sqlalchemy import text

        query = """
        INSERT INTO persons (
            person_id, camera_id, first_seen, last_seen, seen_count,
            image_path, confidence, detection_quality, embedding_stored, metadata
        ) VALUES (
            :person_id, :camera_id, :first_seen, :last_seen, :seen_count,
            :image_path, :confidence, :detection_quality, :embedding_stored, :metadata
        )
        ON CONFLICT (person_id, camera_id, DATE(first_seen)) 
        DO UPDATE SET
            last_seen = :last_seen,
            seen_count = persons.seen_count + 1,
            metadata = :metadata
        """

        # For SQLite, use different syntax
        if not self.using_postgres:
            query = """
            INSERT OR REPLACE INTO persons (
                person_id, camera_id, first_seen, last_seen, seen_count,
                image_path, confidence, detection_quality, embedding_stored, metadata
            ) VALUES (
                :person_id, :camera_id, :first_seen, :last_seen, :seen_count,
                :image_path, :confidence, :detection_quality, :embedding_stored, :metadata
            )
            """

        try:
            with self.engine.connect() as conn:
                conn.execute(text(query), {
                    'person_id': person_id,
                    'camera_id': camera_id,
                    'first_seen': metadata.get('first_seen', datetime.now()),
                    'last_seen': metadata.get('last_seen', datetime.now()),
                    'seen_count': metadata.get('seen_count', 1),
                    'image_path': metadata.get('image_path'),
                    'confidence': metadata.get('confidence'),
                    'detection_quality': metadata.get('detection_quality'),
                    'embedding_stored': metadata.get('embedding_stored', False),
                    'metadata': json.dumps(metadata) if not self.using_postgres else metadata
                })
                conn.commit()

        except Exception as e:
            logger.error(f"Error inserting person: {e}")

    def insert_event(self, person_id, camera_id, event_type, bbox=None, **kwargs):
        """
        Insert tracking event

        Args:
            person_id: Person ID
            camera_id: Camera ID
            event_type: 'detected', 'counted', 'lost', etc.
            bbox: [x1, y1, x2, y2] or None
            **kwargs: Additional metadata
        """
        if self.engine is None:
            return

        from sqlalchemy import text

        query = """
        INSERT INTO tracking_events (
            person_id, camera_id, event_type, timestamp,
            bbox_x1, bbox_y1, bbox_x2, bbox_y2,
            confidence, track_id, camera_motion_detected, metadata
        ) VALUES (
            :person_id, :camera_id, :event_type, :timestamp,
            :bbox_x1, :bbox_y1, :bbox_x2, :bbox_y2,
            :confidence, :track_id, :camera_motion_detected, :metadata
        )
        """

        params = {
            'person_id': person_id,
            'camera_id': camera_id,
            'event_type': event_type,
            'timestamp': kwargs.get('timestamp', datetime.now()),
            'bbox_x1': bbox[0] if bbox else None,
            'bbox_y1': bbox[1] if bbox else None,
            'bbox_x2': bbox[2] if bbox else None,
            'bbox_y2': bbox[3] if bbox else None,
            'confidence': kwargs.get('confidence'),
            'track_id': kwargs.get('track_id'),
            'camera_motion_detected': kwargs.get('camera_motion', False),
            'metadata': json.dumps(kwargs) if not self.using_postgres else kwargs
        }

        try:
            with self.engine.connect() as conn:
                conn.execute(text(query), params)
                conn.commit()

        except Exception as e:
            logger.error(f"Error inserting event: {e}")

    def update_camera_stats(self, camera_id, stats):
        """
        Update daily camera statistics

        Args:
            camera_id: Camera identifier
            stats: Dict with statistics
        """
        if self.engine is None:
            return

        from sqlalchemy import text

        query = """
        INSERT INTO camera_stats (
            camera_id, date, total_unique, max_density, avg_fps,
            uptime_seconds, detections_count, tracking_errors, metadata
        ) VALUES (
            :camera_id, :date, :total_unique, :max_density, :avg_fps,
            :uptime_seconds, :detections_count, :tracking_errors, :metadata
        )
        ON CONFLICT (camera_id, date)
        DO UPDATE SET
            total_unique = :total_unique,
            max_density = GREATEST(camera_stats.max_density, :max_density),
            avg_fps = :avg_fps,
            uptime_seconds = camera_stats.uptime_seconds + :uptime_seconds,
            detections_count = camera_stats.detections_count + :detections_count,
            metadata = :metadata
        """

        if not self.using_postgres:
            query = """
            INSERT OR REPLACE INTO camera_stats (
                camera_id, date, total_unique, max_density, avg_fps,
                uptime_seconds, detections_count, tracking_errors, metadata
            ) VALUES (
                :camera_id, :date, :total_unique, :max_density, :avg_fps,
                :uptime_seconds, :detections_count, :tracking_errors, :metadata
            )
            """

        try:
            with self.engine.connect() as conn:
                conn.execute(text(query), {
                    'camera_id': camera_id,
                    'date': stats.get('date', datetime.now().date()),
                    'total_unique': stats.get('total_unique', 0),
                    'max_density': stats.get('max_density', 0),
                    'avg_fps': stats.get('avg_fps', 0.0),
                    'uptime_seconds': stats.get('uptime_seconds', 0),
                    'detections_count': stats.get('detections_count', 0),
                    'tracking_errors': stats.get('tracking_errors', 0),
                    'metadata': json.dumps(stats) if not self.using_postgres else stats
                })
                conn.commit()

        except Exception as e:
            logger.error(f"Error updating camera stats: {e}")

    def get_daily_stats(self, camera_id, date=None):
        """
        Get statistics for a specific day

        Args:
            camera_id: Camera identifier
            date: Date (default: today)

        Returns:
            dict with stats or None
        """
        if self.engine is None:
            return None

        from sqlalchemy import text

        if date is None:
            date = datetime.now().date()

        query = """
        SELECT * FROM camera_stats
        WHERE camera_id = :camera_id AND date = :date
        """

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), {
                    'camera_id': camera_id,
                    'date': date
                }).fetchone()

                if result:
                    return dict(result._mapping)
                return None

        except Exception as e:
            logger.error(f"Error getting daily stats: {e}")
            return None

    def close(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\nTesting Database Manager...")

    # Test (will use SQLite fallback if PostgreSQL unavailable)
    db = DatabaseManager(use_postgres=True)

    # Test person insertion
    db.insert_person(
        person_id=1,
        camera_id='cam_0',
        metadata={
            'first_seen': datetime.now(),
            'image_path': '/path/to/image.jpg',
            'confidence': 0.95
        }
    )
    print("✅ Person inserted")

    # Test event insertion
    db.insert_event(
        person_id=1,
        camera_id='cam_0',
        event_type='counted',
        bbox=[100, 100, 200, 300],
        confidence=0.95,
        track_id=5
    )
    print("✅ Event inserted")

    # Test stats update
    db.update_camera_stats(
        camera_id='cam_0',
        stats={
            'total_unique': 10,
            'max_density': 5,
            'avg_fps': 12.5,
            'uptime_seconds': 3600,
            'detections_count': 150
        }
    )
    print("✅ Stats updated")

    # Test retrieval
    stats = db.get_daily_stats('cam_0')
    print(f"✅ Stats retrieved: {stats is not None}")

    db.close()
    print("\n✅ Database test complete!")

