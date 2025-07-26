"""
Security metrics collection and reporting system.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import hashlib

from ..constants import get_config_dir
from .logger import get_logger

logger = get_logger(__name__)


class SecurityMetricsCollector:
    """Collect and analyze security metrics for the application."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the security metrics collector.
        
        Args:
            db_path: Path to SQLite database for metrics storage
        """
        if db_path is None:
            metrics_dir = get_config_dir() / 'security_metrics'
            metrics_dir.mkdir(parents=True, exist_ok=True)
            db_path = metrics_dir / 'metrics.db'
        
        self.db_path = db_path
        self._lock = threading.RLock()
        self._init_database()
        
        # In-memory cache for recent events
        self._event_cache: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._cache_size = 1000  # Maximum events to keep in cache
        
        logger.debug(f"Initialized security metrics collector at {db_path}")
    
    def _init_database(self):
        """Initialize the SQLite database schema."""
        with self._lock:
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                # Create security events table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS security_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL NOT NULL,
                        event_type TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        details TEXT,
                        user TEXT,
                        pid INTEGER,
                        uid INTEGER,
                        source_ip TEXT,
                        hash TEXT UNIQUE
                    )
                """)
                
                # Create indexes for efficient querying
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_timestamp 
                    ON security_events(timestamp)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_event_type 
                    ON security_events(event_type)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_severity 
                    ON security_events(severity)
                """)
                
                # Create metrics summary table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS metrics_summary (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL,
                        metric_type TEXT NOT NULL,
                        metric_value REAL NOT NULL,
                        UNIQUE(date, metric_type)
                    )
                """)
                
                conn.commit()
                conn.close()
                
            except Exception as e:
                logger.error(f"Failed to initialize metrics database: {e}")
    
    def record_event(self, event_type: str, severity: str, 
                     details: Optional[Dict[str, Any]] = None,
                     user: Optional[str] = None,
                     pid: Optional[int] = None,
                     uid: Optional[int] = None,
                     source_ip: Optional[str] = None) -> bool:
        """
        Record a security event.
        
        Args:
            event_type: Type of security event
            severity: Event severity (info, warning, error, critical)
            details: Additional event details
            user: User associated with event
            pid: Process ID
            uid: User ID
            source_ip: Source IP address (if applicable)
            
        Returns:
            True if event was recorded successfully
        """
        with self._lock:
            try:
                timestamp = datetime.now().timestamp()
                
                # Create event hash to prevent duplicates
                event_data = f"{timestamp}{event_type}{severity}{details}"
                event_hash = hashlib.sha256(event_data.encode()).hexdigest()
                
                # Add to cache
                event_dict = {
                    'timestamp': timestamp,
                    'event_type': event_type,
                    'severity': severity,
                    'details': json.dumps(details) if details else None,
                    'user': user or os.environ.get('USER', 'unknown'),
                    'pid': pid or os.getpid(),
                    'uid': uid or (os.getuid() if hasattr(os, 'getuid') else None),
                    'source_ip': source_ip,
                    'hash': event_hash
                }
                
                self._event_cache[event_type].append(event_dict)
                
                # Trim cache if needed
                if len(self._event_cache[event_type]) > self._cache_size:
                    self._event_cache[event_type] = self._event_cache[event_type][-self._cache_size:]
                
                # Store in database
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR IGNORE INTO security_events 
                    (timestamp, event_type, severity, details, user, pid, uid, source_ip, hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_dict['timestamp'],
                    event_dict['event_type'],
                    event_dict['severity'],
                    event_dict['details'],
                    event_dict['user'],
                    event_dict['pid'],
                    event_dict['uid'],
                    event_dict['source_ip'],
                    event_dict['hash']
                ))
                
                conn.commit()
                conn.close()
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to record security event: {e}")
                return False
    
    def get_event_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get summary of security events for the specified time period.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Dictionary with event summary statistics
        """
        with self._lock:
            try:
                cutoff_time = (datetime.now() - timedelta(hours=hours)).timestamp()
                
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                # Get event counts by type
                cursor.execute("""
                    SELECT event_type, COUNT(*) 
                    FROM security_events 
                    WHERE timestamp > ?
                    GROUP BY event_type
                """, (cutoff_time,))
                
                event_counts = dict(cursor.fetchall())
                
                # Get event counts by severity
                cursor.execute("""
                    SELECT severity, COUNT(*) 
                    FROM security_events 
                    WHERE timestamp > ?
                    GROUP BY severity
                """, (cutoff_time,))
                
                severity_counts = dict(cursor.fetchall())
                
                # Get total events
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM security_events 
                    WHERE timestamp > ?
                """, (cutoff_time,))
                
                total_events = cursor.fetchone()[0]
                
                # Get top users by event count
                cursor.execute("""
                    SELECT user, COUNT(*) as count
                    FROM security_events 
                    WHERE timestamp > ?
                    GROUP BY user
                    ORDER BY count DESC
                    LIMIT 10
                """, (cutoff_time,))
                
                top_users = cursor.fetchall()
                
                conn.close()
                
                return {
                    'period_hours': hours,
                    'total_events': total_events,
                    'events_by_type': event_counts,
                    'events_by_severity': severity_counts,
                    'top_users': top_users,
                    'timestamp': datetime.now().isoformat()
                }
                
            except Exception as e:
                logger.error(f"Failed to get event summary: {e}")
                return {}
    
    def get_trending_threats(self, hours: int = 24, 
                           threshold: float = 2.0) -> List[Dict[str, Any]]:
        """
        Identify trending security threats based on event frequency.
        
        Args:
            hours: Time window for analysis
            threshold: Multiplier for baseline to identify spikes
            
        Returns:
            List of trending threat indicators
        """
        with self._lock:
            try:
                current_time = datetime.now()
                recent_cutoff = (current_time - timedelta(hours=hours)).timestamp()
                baseline_cutoff = (current_time - timedelta(hours=hours*2)).timestamp()
                
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                # Get recent event counts
                cursor.execute("""
                    SELECT event_type, COUNT(*) as count
                    FROM security_events 
                    WHERE timestamp > ?
                    GROUP BY event_type
                """, (recent_cutoff,))
                
                recent_counts = dict(cursor.fetchall())
                
                # Get baseline counts
                cursor.execute("""
                    SELECT event_type, COUNT(*) as count
                    FROM security_events 
                    WHERE timestamp > ? AND timestamp <= ?
                    GROUP BY event_type
                """, (baseline_cutoff, recent_cutoff))
                
                baseline_counts = dict(cursor.fetchall())
                
                conn.close()
                
                # Identify trending threats
                trending = []
                for event_type, recent_count in recent_counts.items():
                    baseline_count = baseline_counts.get(event_type, 0)
                    
                    if baseline_count > 0:
                        spike_ratio = recent_count / baseline_count
                        if spike_ratio >= threshold:
                            trending.append({
                                'event_type': event_type,
                                'recent_count': recent_count,
                                'baseline_count': baseline_count,
                                'spike_ratio': spike_ratio,
                                'severity': 'high' if spike_ratio > 5 else 'medium'
                            })
                    elif recent_count > 10:  # New threat type
                        trending.append({
                            'event_type': event_type,
                            'recent_count': recent_count,
                            'baseline_count': 0,
                            'spike_ratio': float('inf'),
                            'severity': 'high'
                        })
                
                # Sort by spike ratio
                trending.sort(key=lambda x: x['spike_ratio'], reverse=True)
                
                return trending
                
            except Exception as e:
                logger.error(f"Failed to get trending threats: {e}")
                return []
    
    def generate_security_report(self, output_path: Optional[Path] = None) -> str:
        """
        Generate a comprehensive security report.
        
        Args:
            output_path: Path to save the report (optional)
            
        Returns:
            Report content as string
        """
        try:
            # Get report data with explicit typing
            summary_24h: Dict[str, Any] = self.get_event_summary(24)
            summary_7d: Dict[str, Any] = self.get_event_summary(24 * 7)
            summary_30d: Dict[str, Any] = self.get_event_summary(24 * 30)
            trending_threats: List[Dict[str, Any]] = self.get_trending_threats()
            
            report_data = {
                'generated_at': datetime.now().isoformat(),
                'summary_24h': summary_24h,
                'summary_7d': summary_7d,
                'summary_30d': summary_30d,
                'trending_threats': trending_threats,
                'database_path': str(self.db_path)
            }
            
            # Format report
            report_lines = [
                "# Security Metrics Report",
                f"Generated: {report_data['generated_at']}",
                "",
                "## Executive Summary",
                "",
                "### Last 24 Hours",
                f"- Total Events: {summary_24h.get('total_events', 0)}",
                f"- Critical Events: {summary_24h.get('events_by_severity', {}).get('critical', 0)}",
                f"- Warning Events: {summary_24h.get('events_by_severity', {}).get('warning', 0)}",
                "",
                "### Last 7 Days",
                f"- Total Events: {summary_7d.get('total_events', 0)}",
                "",
                "### Last 30 Days",
                f"- Total Events: {summary_30d.get('total_events', 0)}",
                "",
                "## Trending Threats",
                ""
            ]
            
            if trending_threats:
                for threat in trending_threats[:5]:
                    report_lines.extend([
                        f"### {threat['event_type']}",
                        f"- Severity: {threat['severity']}",
                        f"- Recent Count: {threat['recent_count']}",
                        f"- Spike Ratio: {threat['spike_ratio']:.2f}x",
                        ""
                    ])
            else:
                report_lines.append("No trending threats detected.")
            
            report_lines.extend([
                "",
                "## Event Distribution (Last 24 Hours)",
                ""
            ])
            
            for event_type, count in summary_24h.get('events_by_type', {}).items():
                report_lines.append(f"- {event_type}: {count}")
            
            report_content = "\n".join(report_lines)
            
            # Save report if path provided
            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(report_content)
                logger.info(f"Security report saved to {output_path}")
            
            return report_content
            
        except Exception as e:
            logger.error(f"Failed to generate security report: {e}")
            return "Error generating security report"
    
    def cleanup_old_events(self, days: int = 90):
        """
        Clean up old events from the database.
        
        Args:
            days: Number of days to retain events
        """
        with self._lock:
            try:
                cutoff_time = (datetime.now() - timedelta(days=days)).timestamp()
                
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                cursor.execute("""
                    DELETE FROM security_events 
                    WHERE timestamp < ?
                """, (cutoff_time,))
                
                deleted_count = cursor.rowcount
                
                conn.commit()
                conn.close()
                
                logger.info(f"Cleaned up {deleted_count} old security events")
                
            except Exception as e:
                logger.error(f"Failed to cleanup old events: {e}")


# Global metrics collector instance
_metrics_collector: Optional[SecurityMetricsCollector] = None
_metrics_lock = threading.Lock()


def get_metrics_collector() -> SecurityMetricsCollector:
    """Get or create the global metrics collector instance."""
    global _metrics_collector
    
    with _metrics_lock:
        if _metrics_collector is None:
            _metrics_collector = SecurityMetricsCollector()
        return _metrics_collector


def record_security_metric(event_type: str, severity: str = "info",
                          details: Optional[Dict[str, Any]] = None) -> bool:
    """
    Convenience function to record a security metric.
    
    Args:
        event_type: Type of security event
        severity: Event severity
        details: Additional details
        
    Returns:
        True if recorded successfully
    """
    collector = get_metrics_collector()
    return collector.record_event(event_type, severity, details) 