#!/usr/bin/env python3
"""
ID Manager with Redis/LRU Cache
Persistent ID store to avoid double-counting across sessions
"""

import logging
import json
import time
from collections import OrderedDict
from datetime import datetime, timedelta
import numpy as np

logger = logging.getLogger(__name__)


class LRUCache:
    """
    LRU (Least Recently Used) Cache for in-memory ID storage
    Fallback when Redis is not available
    """

    def __init__(self, capacity=1000, ttl_hours=24):
        """
        Initialize LRU cache

        Args:
            capacity: Maximum number of entries
            ttl_hours: Time-to-live in hours
        """
        self.capacity = capacity
        self.ttl_seconds = ttl_hours * 3600
        self.cache = OrderedDict()
        self.timestamps = {}

    def get(self, key):
        """Get value from cache"""
        if key not in self.cache:
            return None

        # Check TTL
        if time.time() - self.timestamps[key] > self.ttl_seconds:
            self.delete(key)
            return None

        # Move to end (most recently used)
        self.cache.move_to_end(key)
        return self.cache[key]

    def set(self, key, value):
        """Set value in cache"""
        if key in self.cache:
            self.cache.move_to_end(key)
        else:
            if len(self.cache) >= self.capacity:
                # Remove least recently used
                oldest_key = next(iter(self.cache))
                self.delete(oldest_key)

            self.cache[key] = value

        self.timestamps[key] = time.time()

    def delete(self, key):
        """Delete key from cache"""
        if key in self.cache:
            del self.cache[key]
            del self.timestamps[key]

    def exists(self, key):
        """Check if key exists"""
        return self.get(key) is not None

    def keys(self):
        """Get all keys"""
        # Clean expired entries first
        current_time = time.time()
        expired = [k for k, t in self.timestamps.items()
                  if current_time - t > self.ttl_seconds]
        for k in expired:
            self.delete(k)

        return list(self.cache.keys())

    def size(self):
        """Get cache size"""
        return len(self.cache)


class RedisIDManager:
    """
    ID Manager with Redis backend
    Falls back to LRU cache if Redis unavailable
    """

    def __init__(self, host='localhost', port=6379, db=0,
                 ttl_hours=24, use_redis=True):
        """
        Initialize ID Manager

        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            ttl_hours: Time-to-live for IDs (hours)
            use_redis: Try to use Redis, fallback to LRU if failed
        """
        self.ttl_hours = ttl_hours
        self.ttl_seconds = ttl_hours * 3600
        self.redis_client = None
        self.using_redis = False

        # Try to connect to Redis
        if use_redis:
            try:
                import redis
                self.redis_client = redis.Redis(
                    host=host,
                    port=port,
                    db=db,
                    decode_responses=True,
                    socket_connect_timeout=2
                )
                # Test connection
                self.redis_client.ping()
                self.using_redis = True
                logger.info(f"✅ ID Manager: Redis connected ({host}:{port})")
            except Exception as e:
                logger.warning(f"⚠️  Redis unavailable: {e}")
                logger.info("   Using in-memory LRU cache instead")

        # Fallback to LRU cache
        if not self.using_redis:
            self.cache = LRUCache(capacity=10000, ttl_hours=ttl_hours)
            logger.info("✅ ID Manager: LRU cache (10000 capacity)")

    def _make_key(self, person_id, camera_id='default'):
        """Create Redis/cache key"""
        return f"person:{camera_id}:{person_id}"

    def _make_embedding_key(self, person_id, camera_id='default'):
        """Create embedding key"""
        return f"embedding:{camera_id}:{person_id}"

    def store_person(self, person_id, metadata, camera_id='default'):
        """
        Store person ID with metadata

        Args:
            person_id: Unique person identifier
            metadata: Dict with person info (count, timestamp, etc.)
            camera_id: Camera identifier
        """
        key = self._make_key(person_id, camera_id)
        value = json.dumps(metadata)

        if self.using_redis:
            self.redis_client.setex(
                key,
                self.ttl_seconds,
                value
            )
        else:
            self.cache.set(key, value)

    def get_person(self, person_id, camera_id='default'):
        """
        Get person metadata

        Returns:
            dict or None
        """
        key = self._make_key(person_id, camera_id)

        if self.using_redis:
            value = self.redis_client.get(key)
        else:
            value = self.cache.get(key)

        if value is None:
            return None

        return json.loads(value)

    def exists(self, person_id, camera_id='default'):
        """Check if person exists in cache"""
        key = self._make_key(person_id, camera_id)

        if self.using_redis:
            return self.redis_client.exists(key) > 0
        else:
            return self.cache.exists(key)

    def store_embedding(self, person_id, embedding, camera_id='default'):
        """
        Store person embedding (ReID features)

        Args:
            person_id: Unique identifier
            embedding: numpy array of features
            camera_id: Camera identifier
        """
        key = self._make_embedding_key(person_id, camera_id)

        # Serialize numpy array
        embedding_bytes = embedding.tobytes()
        shape_str = ','.join(map(str, embedding.shape))
        dtype_str = str(embedding.dtype)
        value = f"{shape_str}|{dtype_str}|{embedding_bytes.hex()}"

        if self.using_redis:
            self.redis_client.setex(
                key,
                self.ttl_seconds,
                value
            )
        else:
            self.cache.set(key, value)

    def get_embedding(self, person_id, camera_id='default'):
        """
        Get person embedding

        Returns:
            numpy array or None
        """
        key = self._make_embedding_key(person_id, camera_id)

        if self.using_redis:
            value = self.redis_client.get(key)
        else:
            value = self.cache.get(key)

        if value is None:
            return None

        # Deserialize numpy array
        try:
            shape_str, dtype_str, hex_data = value.split('|')
            shape = tuple(map(int, shape_str.split(',')))
            dtype = np.dtype(dtype_str)
            embedding_bytes = bytes.fromhex(hex_data)
            embedding = np.frombuffer(embedding_bytes, dtype=dtype).reshape(shape)
            return embedding
        except Exception as e:
            logger.error(f"Error deserializing embedding: {e}")
            return None

    def get_all_embeddings(self, camera_id='default'):
        """
        Get all stored embeddings for similarity search

        Returns:
            dict: {person_id: embedding}
        """
        embeddings = {}

        if self.using_redis:
            # Scan for embedding keys
            pattern = f"embedding:{camera_id}:*"
            for key in self.redis_client.scan_iter(match=pattern):
                person_id = key.split(':')[-1]
                embedding = self.get_embedding(person_id, camera_id)
                if embedding is not None:
                    embeddings[person_id] = embedding
        else:
            # Get from LRU cache
            prefix = f"embedding:{camera_id}:"
            for key in self.cache.keys():
                if key.startswith(prefix):
                    person_id = key.split(':')[-1]
                    embedding = self.get_embedding(person_id, camera_id)
                    if embedding is not None:
                        embeddings[person_id] = embedding

        return embeddings

    def update_person_seen(self, person_id, camera_id='default'):
        """
        Update last seen timestamp for person
        Extends TTL
        """
        metadata = self.get_person(person_id, camera_id)
        if metadata:
            metadata['last_seen'] = datetime.now().isoformat()
            metadata['seen_count'] = metadata.get('seen_count', 0) + 1
            self.store_person(person_id, metadata, camera_id)

    def search_similar_embedding(self, query_embedding, threshold=0.75, camera_id='default'):
        """
        Search for similar embeddings in database

        Args:
            query_embedding: numpy array to search for
            threshold: Cosine similarity threshold (0-1)
            camera_id: Camera identifier

        Returns:
            (person_id, similarity) tuple or (None, 0)
        """
        all_embeddings = self.get_all_embeddings(camera_id)

        if len(all_embeddings) == 0:
            return None, 0.0

        # Normalize query
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-12)

        best_match = None
        best_similarity = 0.0

        for person_id, stored_embedding in all_embeddings.items():
            # Normalize stored
            stored_norm = stored_embedding / (np.linalg.norm(stored_embedding) + 1e-12)

            # Cosine similarity
            similarity = np.dot(query_norm, stored_norm)

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = person_id

        if best_similarity >= threshold:
            return best_match, best_similarity

        return None, best_similarity

    def get_stats(self, camera_id='default'):
        """
        Get cache statistics

        Returns:
            dict with stats
        """
        if self.using_redis:
            pattern = f"person:{camera_id}:*"
            count = sum(1 for _ in self.redis_client.scan_iter(match=pattern))

            info = self.redis_client.info('memory')
            memory_used = info.get('used_memory_human', 'N/A')

            return {
                'backend': 'Redis',
                'person_count': count,
                'memory_used': memory_used,
                'ttl_hours': self.ttl_hours
            }
        else:
            return {
                'backend': 'LRU Cache',
                'person_count': self.cache.size(),
                'capacity': self.cache.capacity,
                'ttl_hours': self.ttl_hours
            }

    def clear_expired(self):
        """Clear expired entries (maintenance)"""
        if not self.using_redis:
            # LRU cache auto-clears on access
            _ = self.cache.keys()  # Triggers cleanup
        # Redis auto-expires with TTL


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\nTesting ID Manager...")

    # Test with Redis (will fallback to LRU if unavailable)
    manager = RedisIDManager(use_redis=True, ttl_hours=24)

    # Test person storage
    manager.store_person(
        person_id=1,
        metadata={
            'count_number': 1,
            'first_seen': datetime.now().isoformat(),
            'camera': 'cam_0'
        },
        camera_id='cam_0'
    )

    # Test retrieval
    person = manager.get_person(1, 'cam_0')
    print(f"\n✅ Person stored and retrieved: {person}")

    # Test embedding
    dummy_embedding = np.random.randn(512)
    manager.store_embedding(1, dummy_embedding, 'cam_0')

    retrieved = manager.get_embedding(1, 'cam_0')
    print(f"✅ Embedding stored: {retrieved is not None and retrieved.shape == (512,)}")

    # Test similarity search
    query = dummy_embedding + np.random.randn(512) * 0.01  # Very similar
    match_id, similarity = manager.search_similar_embedding(query, threshold=0.5, camera_id='cam_0')
    print(f"✅ Similarity search: Found person {match_id} with {similarity:.3f} similarity")

    # Test stats
    stats = manager.get_stats('cam_0')
    print(f"\n✅ Stats: {stats}")

    print("\n✅ ID Manager test complete!")

