"""
Database utility functions
Performance analysis and query optimization tools
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class DatabaseUtils:
    """Utility class for database operations and performance analysis"""

    @staticmethod
    def explain_query(db: Session, query_str: str, analyze: bool = True) -> List[str]:
        """
        Analyze SQL query performance using EXPLAIN ANALYZE

        Args:
            db: Database session
            query_str: SQL query string to analyze
            analyze: If True, run EXPLAIN ANALYZE (executes query), otherwise just EXPLAIN

        Returns:
            List of explanation lines

        Example:
            >>> utils = DatabaseUtils()
            >>> results = utils.explain_query(db, "SELECT * FROM recognition_results WHERE confidence > 0.8")
            >>> for line in results:
            ...     print(line)
        """
        try:
            prefix = "EXPLAIN ANALYZE" if analyze else "EXPLAIN"
            explain_query = f"{prefix} {query_str}"

            result = db.execute(text(explain_query))
            explanation = [row[0] for row in result.fetchall()]

            logger.info(f"Query explanation ({prefix}):\n" + "\n".join(explanation))
            return explanation

        except Exception as e:
            logger.error(f"Error explaining query: {e}")
            raise

    @staticmethod
    def get_table_sizes(db: Session) -> Dict[str, Dict[str, Any]]:
        """
        Get size information for all tables in the database

        Args:
            db: Database session

        Returns:
            Dictionary mapping table names to size information

        Example:
            >>> utils = DatabaseUtils()
            >>> sizes = utils.get_table_sizes(db)
            >>> print(f"Table: {sizes['recognition_results']['table_size']}")
        """
        query = text(
            """
            SELECT
                schemaname || '.' || tablename AS table_name,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
                pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS index_size,
                pg_total_relation_size(schemaname||'.'||tablename) AS total_bytes
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
        """
        )

        result = db.execute(query)
        table_sizes = {}

        for row in result:
            table_name = row[0].split(".")[1]  # Remove schema prefix
            table_sizes[table_name] = {
                "total_size": row[1],
                "table_size": row[2],
                "index_size": row[3],
                "total_bytes": row[4],
            }

        return table_sizes

    @staticmethod
    def get_index_usage(
        db: Session, table_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get index usage statistics for tables

        Args:
            db: Database session
            table_name: Specific table name, or None for all tables

        Returns:
            List of dictionaries with index usage information

        Example:
            >>> utils = DatabaseUtils()
            >>> usage = utils.get_index_usage(db, 'recognition_results')
            >>> for idx in usage:
            ...     print(f"{idx['index_name']}: {idx['index_scans']} scans")
        """
        where_clause = f"AND indexrelname LIKE '{table_name}%'" if table_name else ""

        query = text(
            f"""
            SELECT
                schemaname,
                tablename,
                indexrelname AS index_name,
                idx_scan AS index_scans,
                idx_tup_read AS tuples_read,
                idx_tup_fetch AS tuples_fetched,
                pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
            FROM pg_stat_user_indexes
            WHERE schemaname = 'public'
            {where_clause}
            ORDER BY idx_scan DESC
        """
        )

        result = db.execute(query)
        indexes = []

        for row in result:
            indexes.append(
                {
                    "schema": row[0],
                    "table": row[1],
                    "index_name": row[2],
                    "index_scans": row[3],
                    "tuples_read": row[4],
                    "tuples_fetched": row[5],
                    "index_size": row[6],
                }
            )

        return indexes

    @staticmethod
    def get_slow_queries(
        db: Session, min_duration_ms: int = 100, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get slow query statistics from pg_stat_statements
        Requires pg_stat_statements extension to be enabled

        Args:
            db: Database session
            min_duration_ms: Minimum query duration in milliseconds
            limit: Maximum number of queries to return

        Returns:
            List of slow queries with statistics

        Example:
            >>> utils = DatabaseUtils()
            >>> slow = utils.get_slow_queries(db, min_duration_ms=500)
            >>> for query in slow:
            ...     print(f"{query['avg_time_ms']:.2f}ms: {query['query'][:50]}")
        """
        try:
            query = text(
                f"""
                SELECT
                    query,
                    calls,
                    total_exec_time / 1000 AS total_time_ms,
                    mean_exec_time / 1000 AS avg_time_ms,
                    max_exec_time / 1000 AS max_time_ms,
                    stddev_exec_time / 1000 AS stddev_time_ms,
                    rows
                FROM pg_stat_statements
                WHERE mean_exec_time > {min_duration_ms}
                ORDER BY mean_exec_time DESC
                LIMIT {limit}
            """
            )

            result = db.execute(query)
            slow_queries = []

            for row in result:
                slow_queries.append(
                    {
                        "query": row[0],
                        "calls": row[1],
                        "total_time_ms": float(row[2]),
                        "avg_time_ms": float(row[3]),
                        "max_time_ms": float(row[4]),
                        "stddev_time_ms": float(row[5]),
                        "rows": row[6],
                    }
                )

            return slow_queries

        except Exception as e:
            logger.warning(f"pg_stat_statements not available: {e}")
            return []

    @staticmethod
    def analyze_table(db: Session, table_name: str) -> None:
        """
        Run ANALYZE on a table to update statistics

        Args:
            db: Database session
            table_name: Name of the table to analyze

        Example:
            >>> utils = DatabaseUtils()
            >>> utils.analyze_table(db, 'recognition_results')
        """
        try:
            db.execute(text(f"ANALYZE {table_name}"))
            db.commit()
            logger.info(f"Successfully analyzed table: {table_name}")
        except Exception as e:
            logger.error(f"Error analyzing table {table_name}: {e}")
            db.rollback()
            raise

    @staticmethod
    def vacuum_table(db: Session, table_name: str, full: bool = False) -> None:
        """
        Run VACUUM on a table to reclaim storage

        Args:
            db: Database session
            table_name: Name of the table to vacuum
            full: If True, run VACUUM FULL (locks table)

        Example:
            >>> utils = DatabaseUtils()
            >>> utils.vacuum_table(db, 'recognition_results')
        """
        try:
            # VACUUM cannot run inside a transaction block
            db.commit()
            db.connection().connection.set_isolation_level(0)  # AUTOCOMMIT mode

            vacuum_cmd = f"VACUUM {'FULL' if full else ''} ANALYZE {table_name}"
            db.execute(text(vacuum_cmd))

            db.connection().connection.set_isolation_level(1)  # Back to READ COMMITTED
            logger.info(f"Successfully vacuumed table: {table_name}")

        except Exception as e:
            logger.error(f"Error vacuuming table {table_name}: {e}")
            raise

    @staticmethod
    def get_cache_hit_ratio(db: Session) -> Dict[str, float]:
        """
        Get PostgreSQL cache hit ratio statistics

        Args:
            db: Database session

        Returns:
            Dictionary with cache hit ratios

        Example:
            >>> utils = DatabaseUtils()
            >>> ratios = utils.get_cache_hit_ratio(db)
            >>> print(f"Cache hit ratio: {ratios['cache_hit_ratio']:.2%}")
        """
        query = text(
            """
            SELECT
                sum(heap_blks_read) AS heap_read,
                sum(heap_blks_hit) AS heap_hit,
                sum(heap_blks_hit) / nullif(sum(heap_blks_hit) + sum(heap_blks_read), 0) AS ratio
            FROM pg_statio_user_tables
        """
        )

        result = db.execute(query).fetchone()

        return {
            "heap_blocks_read": result[0] or 0,
            "heap_blocks_hit": result[1] or 0,
            "cache_hit_ratio": float(result[2] or 0.0),
        }

    @staticmethod
    def get_connection_stats(db: Session) -> Dict[str, Any]:
        """
        Get database connection statistics

        Args:
            db: Database session

        Returns:
            Dictionary with connection statistics

        Example:
            >>> utils = DatabaseUtils()
            >>> stats = utils.get_connection_stats(db)
            >>> print(f"Active connections: {stats['active_connections']}")
        """
        query = text(
            """
            SELECT
                state,
                COUNT(*) as count
            FROM pg_stat_activity
            WHERE datname = current_database()
            GROUP BY state
        """
        )

        result = db.execute(query)
        stats = {"total_connections": 0}

        for row in result:
            state = row[0] or "unknown"
            count = row[1]
            stats[f"{state}_connections"] = count
            stats["total_connections"] += count

        return stats

    @staticmethod
    def create_missing_indexes_report(db: Session) -> List[Dict[str, Any]]:
        """
        Identify potentially missing indexes based on sequential scans

        Args:
            db: Database session

        Returns:
            List of tables that might benefit from additional indexes

        Example:
            >>> utils = DatabaseUtils()
            >>> report = utils.create_missing_indexes_report(db)
            >>> for item in report:
            ...     print(f"Table {item['table']}: {item['seq_scans']} sequential scans")
        """
        query = text(
            """
            SELECT
                schemaname,
                tablename,
                seq_scan,
                seq_tup_read,
                idx_scan,
                seq_tup_read / nullif(seq_scan, 0) AS avg_seq_tup_read,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS table_size
            FROM pg_stat_user_tables
            WHERE schemaname = 'public'
              AND seq_scan > 0
            ORDER BY seq_scan DESC, seq_tup_read DESC
            LIMIT 20
        """
        )

        result = db.execute(query)
        report = []

        for row in result:
            report.append(
                {
                    "schema": row[0],
                    "table": row[1],
                    "seq_scans": row[2],
                    "seq_tuples_read": row[3],
                    "index_scans": row[4] or 0,
                    "avg_seq_tuples_per_scan": float(row[5] or 0),
                    "table_size": row[6],
                }
            )

        return report
