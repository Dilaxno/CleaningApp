#!/usr/bin/env python3
"""
Security Monitoring Script for CleanEnroll Application
Monitors for security events and potential threats
"""

import logging
import os
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('security.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class SecurityMonitor:
    def __init__(self):
        self.redis_client = self._get_redis_client()
        self.db_engine = self._get_db_engine()
        
    def _get_redis_client(self):
        """Get Redis client for monitoring rate limiting"""
        try:
            redis_url = os.getenv("REDIS_URL")
            if redis_url:
                return redis.from_url(redis_url)
            else:
                return redis.Redis(
                    host=os.getenv("REDIS_HOST", "localhost"),
                    port=int(os.getenv("REDIS_PORT", 6379)),
                    db=int(os.getenv("REDIS_DB", 0))
                )
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return None
    
    def _get_db_engine(self):
        """Get database engine for monitoring"""
        try:
            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                logger.error("DATABASE_URL not configured")
                return None
            return create_engine(database_url)
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return None
    
    def check_rate_limiting_abuse(self) -> List[Dict]:
        """Check for rate limiting abuse patterns"""
        if not self.redis_client:
            return []
        
        suspicious_ips = []
        try:
            # Get all rate limiting keys
            keys = self.redis_client.keys("rate_limit:*")
            
            for key in keys:
                try:
                    count = int(self.redis_client.get(key) or 0)
                    ttl = self.redis_client.ttl(key)
                    
                    # Extract IP from key
                    key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                    parts = key_str.split(':')
                    if len(parts) >= 3:
                        ip = parts[2]
                        
                        # Flag high request counts
                        if count > 100:  # Adjust threshold as needed
                            suspicious_ips.append({
                                'ip': ip,
                                'count': count,
                                'ttl': ttl,
                                'key': key_str,
                                'timestamp': datetime.utcnow().isoformat()
                            })
                except Exception as e:
                    logger.warning(f"Error processing rate limit key {key}: {e}")
                    
        except Exception as e:
            logger.error(f"Error checking rate limiting abuse: {e}")
        
        return suspicious_ips
    
    def check_failed_login_attempts(self) -> List[Dict]:
        """Check for failed login attempts in database"""
        if not self.db_engine:
            return []
        
        suspicious_attempts = []
        try:
            with self.db_engine.connect() as conn:
                # Check for multiple failed attempts from same IP
                query = text("""
                    SELECT 
                        COUNT(*) as attempt_count,
                        MAX(created_at) as last_attempt
                    FROM failed_login_attempts 
                    WHERE created_at > NOW() - INTERVAL '1 hour'
                    GROUP BY ip_address
                    HAVING COUNT(*) > 10
                    ORDER BY attempt_count DESC
                """)
                
                result = conn.execute(query)
                for row in result:
                    suspicious_attempts.append({
                        'attempt_count': row.attempt_count,
                        'last_attempt': row.last_attempt.isoformat() if row.last_attempt else None,
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    
        except Exception as e:
            logger.error(f"Error checking failed login attempts: {e}")
        
        return suspicious_attempts
    
    def check_unusual_file_uploads(self) -> List[Dict]:
        """Check for unusual file upload patterns"""
        if not self.db_engine:
            return []
        
        suspicious_uploads = []
        try:
            with self.db_engine.connect() as conn:
                # Check for large number of uploads from single user
                query = text("""
                    SELECT 
                        user_id,
                        COUNT(*) as upload_count,
                        SUM(file_size) as total_size,
                        MAX(created_at) as last_upload
                    FROM file_uploads 
                    WHERE created_at > NOW() - INTERVAL '1 hour'
                    GROUP BY user_id
                    HAVING COUNT(*) > 50 OR SUM(file_size) > 100000000
                    ORDER BY upload_count DESC
                """)
                
                result = conn.execute(query)
                for row in result:
                    suspicious_uploads.append({
                        'user_id': row.user_id,
                        'upload_count': row.upload_count,
                        'total_size': row.total_size,
                        'last_upload': row.last_upload.isoformat() if row.last_upload else None,
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    
        except Exception as e:
            logger.error(f"Error checking file uploads: {e}")
        
        return suspicious_uploads
    
    def check_otp_abuse(self) -> List[Dict]:
        """Check for OTP request abuse"""
        if not self.redis_client:
            return []
        
        suspicious_otp = []
        try:
            # Get all OTP keys
            keys = self.redis_client.keys("otp:*")
            
            # Count OTP requests per email
            email_counts = {}
            for key in keys:
                try:
                    key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                    email = key_str.replace('otp:', '').replace('recovery_', '')
                    
                    if email in email_counts:
                        email_counts[email] += 1
                    else:
                        email_counts[email] = 1
                        
                except Exception as e:
                    logger.warning(f"Error processing OTP key {key}: {e}")
            
            # Flag emails with too many OTP requests
            for email, count in email_counts.items():
                if count > 5:  # Adjust threshold as needed
                    suspicious_otp.append({
                        'email': email,
                        'otp_count': count,
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    
        except Exception as e:
            logger.error(f"Error checking OTP abuse: {e}")
        
        return suspicious_otp
    
    def generate_security_report(self) -> Dict:
        """Generate comprehensive security report"""
        report = {
            'timestamp': datetime.utcnow().isoformat(),
            'rate_limiting_abuse': self.check_rate_limiting_abuse(),
            'failed_login_attempts': self.check_failed_login_attempts(),
            'unusual_file_uploads': self.check_unusual_file_uploads(),
            'otp_abuse': self.check_otp_abuse()
        }
        
        # Count total issues
        total_issues = (
            len(report['rate_limiting_abuse']) +
            len(report['failed_login_attempts']) +
            len(report['unusual_file_uploads']) +
            len(report['otp_abuse'])
        )
        
        report['total_security_issues'] = total_issues
        report['severity'] = 'HIGH' if total_issues > 10 else 'MEDIUM' if total_issues > 5 else 'LOW'
        
        return report
    
    def run_monitoring_cycle(self):
        """Run a single monitoring cycle"""
        logger.info("Starting security monitoring cycle")
        
        report = self.generate_security_report()
        
        # Log summary
        logger.info(f"Security scan complete: {report['total_security_issues']} issues found (Severity: {report['severity']})")
        
        # Log detailed issues if any found
        if report['total_security_issues'] > 0:
            logger.warning(f"Security issues detected: {json.dumps(report, indent=2)}")
            
            # Alert on high severity
            if report['severity'] == 'HIGH':
                logger.critical("HIGH SEVERITY SECURITY ISSUES DETECTED - IMMEDIATE ATTENTION REQUIRED")
        
        return report

def main():
    """Main monitoring loop"""
    monitor = SecurityMonitor()
    
    logger.info("Security monitoring started")
    
    try:
        while True:
            try:
                monitor.run_monitoring_cycle()
                time.sleep(300)  # Run every 5 minutes
            except KeyboardInterrupt:
                logger.info("Security monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring cycle: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
                
    except Exception as e:
        logger.critical(f"Critical error in security monitoring: {e}")

if __name__ == "__main__":
    main()